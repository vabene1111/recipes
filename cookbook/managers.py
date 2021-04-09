from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.search import (
    SearchQuery, SearchRank, SearchVector, TrigramSimilarity,
)
from django.db import models


# TODO add search highlighting
# TODO add language support
# TODO add schedule index rebuild
# TODO add admin function to rebuild index
class RecipeSearchManager(models.Manager):

    def search(self, search_text, space):
        search_query = SearchQuery(
            search_text, config='english'
        )
        search_vectors = (
            SearchVector('search_vector')
            + SearchVector(StringAgg('steps__ingredients__food__name', delimiter=' '), weight='A', config='english')
            + SearchVector(StringAgg('keywords__name', delimiter=' '), weight='A', config='english'))
        search_rank = SearchRank(search_vectors, search_query)
        # trigram_similarity = TrigramSimilarity(
        #     'headline', search_text
        # )
        return (
            self.get_queryset()
            .annotate(search=search_vectors, rank=search_rank)
            .filter(search=search_query)
            .order_by('-rank'))
