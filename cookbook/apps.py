from django.apps import AppConfig


class CookbookConfig(AppConfig):
    name = 'cookbook'

    def ready(self):
        import cookbook.signals  # noqa
