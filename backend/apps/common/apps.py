from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "apps.common"
    label = "common"

    def ready(self):
        from . import openapi  # noqa: F401  (registers OpenAPI extensions)
