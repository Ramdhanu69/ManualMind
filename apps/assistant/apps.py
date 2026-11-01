from django.apps import AppConfig


class AssistantConfig(AppConfig):
    name = "apps.assistant"

    def ready(self) -> None:
        from apps.assistant.providers import check_provider_config

        check_provider_config()
