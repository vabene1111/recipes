from django.apps import AppConfig
from django.conf import settings


class CookbookConfig(AppConfig):
    name = 'cookbook'

    def ready(self):
        # post_save signal is only necessary if using full-text search on postgres
        if settings.DATABASES['default']['ENGINE'] in ['django.db.backends.postgresql_psycopg2', 'django.db.backends.postgresql']:
            import cookbook.signals  # noqa
