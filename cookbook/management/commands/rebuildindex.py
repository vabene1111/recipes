from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.core.management.base import BaseCommand
from django_scopes import scopes_disabled
from django.utils.translation import gettext_lazy as _

from cookbook.models import Recipe


# can be executed at the command line with 'python manage.py rebuildindex'
class Command(BaseCommand):
    help = _('Rebuilds full text search index on Recipe')

    def handle(self, *args, **options):
        if settings.DATABASES['default']['ENGINE'] not in ['django.db.backends.postgresql_psycopg2', 'django.db.backends.postgresql']:
            self.stdout.write(self.style.WARNING(_('Only Postgress databases use full text search, no index to rebuild')))

        try:
            with scopes_disabled():
                search_vector = (
                    SearchVector('name__unaccent', weight='A')
                    + SearchVector('description__unaccent', weight='B'))
                Recipe.objects.all().update(search_vector=search_vector)

                self.stdout.write(self.style.SUCCESS(_('Recipe index rebuild complete.')))
        except:
            self.stdout.write(self.style.ERROR(_('Recipe index rebuild failed.')))
