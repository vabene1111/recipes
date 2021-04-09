from django.contrib.postgres.search import SearchVector
from django.db.models.signals import post_save
from django.dispatch import receiver

from cookbook.models import Recipe


@receiver(post_save, sender=Recipe)
def update_recipe_search_vector(sender, instance=None, created=False, **kwargs):
    if not instance:
        return

    if hasattr(instance, '_dirty'):
        return

    instance.search_vector = (
        SearchVector('name', weight='A', config='english')
        + SearchVector('description', weight='B', config='english')
    )

    try:
        instance._dirty = True
        instance.save()
    finally:
        del instance._dirty
