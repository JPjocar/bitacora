from django.apps import AppConfig


class AssetsConfig(AppConfig):
    name = "apps.assets"

    def ready(self):
        from . import checks  # noqa: F401
