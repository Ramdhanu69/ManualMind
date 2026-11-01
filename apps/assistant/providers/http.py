"""Minimal JSON-over-HTTP client for the model providers.

Uses urllib so that swapping provider SDKs never changes the dependency set.
Error messages name the provider, never the URL, because some providers carry the
API key in the query string.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    """A model provider could not be reached or returned an unusable response."""


def post_json(
    url: str,
    payload: dict,
    headers: dict[str, str],
    timeout: int,
    label: str,
) -> dict:
    """POST JSON and return the parsed response. Retries once on transient failure."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    failure: ProviderError | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            failure = ProviderError(f"{label} returned HTTP {exc.status}: {detail}")
            if exc.status and exc.status < 500:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failure = ProviderError(f"{label} is unreachable: {type(exc).__name__}: {exc}")
        except json.JSONDecodeError as exc:
            failure = ProviderError(f"{label} returned invalid JSON: {exc}")
            break
    raise failure or ProviderError(f"{label} failed for an unknown reason")
