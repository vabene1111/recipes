from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.search import (
    SearchQuery, SearchRank, SearchVector, TrigramSimilarity,
)
from django.db import models
from django.db.models import Q
from django.utils import translation

DICTIONARY = {
    # TODO find custom dictionaries - maybe from here https://www.postgresql.org/message-id/CAF4Au4x6X_wSXFwsQYE8q5o0aQZANrvYjZJ8uOnsiHDnOVPPEg%40mail.gmail.com
    # 'hy': 'Armenian',
    # 'ca': 'Catalan',
    # 'cs': 'Czech',
    'nl': 'dutch',
    'en': 'english',
    'fr': 'french',
    'de': 'german',
    'it': 'italian',
    # 'lv': 'Latvian',
    'es': 'spanish',
}


# TODO add search highlighting
# TODO add language support
# TODO add schedule index rebuild
class RecipeSearchManager(models.Manager):
    def search(self, search_text, space):
        language = DICTIONARY.get(translation.get_language(), 'simple')
        search_query = SearchQuery(
            search_text,
            config=language,
            search_type="websearch"
        )
        search_vectors = (
            SearchVector('search_vector')
            + SearchVector(StringAgg('steps__ingredients__food__name', delimiter=' '), weight='B', config=language)
            + SearchVector(StringAgg('keywords__name', delimiter=' '), weight='B', config=language))
        search_rank = SearchRank(search_vectors, search_query)
        # USING TRIGRAM BREAKS WEB SEARCH
        # ADDING MULTIPLE TRIGRAMS CREATES DUPLICATE RESULTS
        # DISTINCT NOT COMPAITBLE WITH ANNOTATE
        # trigram_name = (TrigramSimilarity('name', search_text))
        # trigram_description = (TrigramSimilarity('description', search_text))
        # trigram_food = (TrigramSimilarity('steps__ingredients__food__name', search_text))
        # trigram_keyword = (TrigramSimilarity('keywords__name', search_text))
        # adding additional trigrams created duplicates
        # + TrigramSimilarity('description', search_text)
        # + TrigramSimilarity('steps__ingredients__food__name', search_text)
        # + TrigramSimilarity('keywords__name', search_text)
        return (
            self.get_queryset()
            .annotate(
                search=search_vectors,
                rank=search_rank,
                #trigram=trigram_name+trigram_description+trigram_food+trigram_keyword
                # trigram_name=trigram_name,
                # trigram_description=trigram_description,
                # trigram_food=trigram_food,
                # trigram_keyword=trigram_keyword
            )
            .filter(
                Q(search=search_query)
                # | Q(trigram_name__gt=0.1)
                # | Q(name__icontains=search_text)
                # | Q(trigram_name__gt=0.2)
                # | Q(trigram_description__gt=0.2)
                # | Q(trigram_food__gt=0.2)
                # | Q(trigram_keyword__gt=0.2)
            )
            .order_by('-rank'))
