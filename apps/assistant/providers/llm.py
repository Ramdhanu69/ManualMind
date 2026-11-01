"""LLM providers. Every one returns a parsed JSON object or raises ProviderError."""

from __future__ import annotations

import json
import re

from apps.assistant.providers.http import ProviderError, post_json

CONTEXT_PASSAGE = re.compile(
    r"\[chunk_id=(?P<chunk_id>\d+)[^\]]*\]\n(?P<text>.*?)(?=\n\[chunk_id=|\Z)",
    re.DOTALL,
)


def _parse_json_object(raw: str, label: str) -> dict:
    """Parse a JSON object, tolerating the fenced code blocks some models emit."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ProviderError(f"{label} did not return JSON")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderError(f"{label} returned malformed JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProviderError(f"{label} returned JSON that is not an object")
    return parsed


class OpenAICompatibleLLM:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, temperature: float, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        label = f"LLM '{self.model}'"
        body = post_json(
            f"{self.base_url}/chat/completions",
            {
                "model": self.model,
                "temperature": self.temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            self.timeout,
            label,
        )
        try:
            return _parse_json_object(body["choices"][0]["message"]["content"], label)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{label} returned an unexpected payload") from exc


class GeminiLLM:
    name = "gemini"

    def __init__(self, api_key: str, model: str, temperature: float, timeout: int):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        label = f"Gemini '{self.model}'"
        body = post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": self.temperature,
                    "responseMimeType": "application/json",
                },
            },
            {"x-goog-api-key": self.api_key},
            self.timeout,
            label,
        )
        try:
            parts = body["candidates"][0]["content"]["parts"]
            return _parse_json_object("".join(part.get("text", "") for part in parts), label)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{label} returned an unexpected payload") from exc


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, temperature: float, timeout: int):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        label = f"Anthropic '{self.model}'"
        body = post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "model": self.model,
                "max_tokens": 2048,
                "temperature": self.temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            self.timeout,
            label,
        )
        try:
            blocks = body["content"]
            text = "".join(block.get("text", "") for block in blocks)
            return _parse_json_object(text, label)
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"{label} returned an unexpected payload") from exc


class FakeLLM:
    """Builds a schema-valid answer from the passages it was given.

    Used by the test suite so the pipeline, gates and citation verifier can be
    exercised end to end without an API key.
    """

    name = "fake"
    model = "fake-llm"

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        passages = [
            (int(match.group("chunk_id")), match.group("text").strip())
            for match in CONTEXT_PASSAGE.finditer(user)
        ]
        if not passages:
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "answer": "",
                "citations": [],
                "record_before_escalation": [],
            }
        chunk_id, text = passages[0]
        quote = text[:200]
        return {
            "status": "ANSWERED",
            "answer": f"According to the manual: {quote}",
            "citations": [{"chunk_id": chunk_id, "quote": quote}],
            "record_before_escalation": [],
        }
