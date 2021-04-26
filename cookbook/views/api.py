import io
import json
import re
import uuid

import requests
from PIL import Image
from annoying.decorators import ajax_request
from annoying.functions import get_object_or_None
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import FieldError, ValidationError
from django.core.files import File
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils.translation import gettext as _
from icalendar import Calendar, Event
from recipe_scrapers import scrape_me, WebsiteNotImplementedError, NoSchemaFoundInWildMode
from rest_framework import decorators, viewsets
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.schemas.utils import is_list_view
from rest_framework.viewsets import ViewSetMixin

from cookbook.helper.ingredient_parser import parse
from cookbook.helper.permission_helper import (CustomIsAdmin, CustomIsGuest,
                                               CustomIsOwner, CustomIsShare,
                                               CustomIsShared, CustomIsUser,
                                               group_required)
from cookbook.helper.recipe_search import search_recipes
from cookbook.helper.recipe_url_import import get_from_html, get_from_scraper, find_recipe_json
from cookbook.models import (CookLog, Food, Ingredient, Keyword, MealPlan,
                             MealType, Recipe, RecipeBook, ShoppingList,
                             ShoppingListEntry, ShoppingListRecipe, Step,
                             Storage, Sync, SyncLog, Unit, UserPreference,
                             ViewLog, RecipeBookEntry, Supermarket, ImportLog)
from cookbook.provider.dropbox import Dropbox
from cookbook.provider.local import Local
from cookbook.provider.nextcloud import Nextcloud
from cookbook.serializer import (FoodSerializer, IngredientSerializer,
                                 KeywordSerializer, MealPlanSerializer,
                                 MealTypeSerializer, RecipeBookSerializer,
                                 RecipeImageSerializer, RecipeSerializer,
                                 ShoppingListAutoSyncSerializer,
                                 ShoppingListEntrySerializer,
                                 ShoppingListRecipeSerializer,
                                 ShoppingListSerializer, StepSerializer,
                                 StorageSerializer, SyncLogSerializer,
                                 SyncSerializer, UnitSerializer,
                                 UserNameSerializer, UserPreferenceSerializer,
                                 ViewLogSerializer, CookLogSerializer, RecipeBookEntrySerializer,
                                 RecipeOverviewSerializer, SupermarketSerializer, ImportLogSerializer)
from recipes.settings import DEMO


class StandardFilterMixin(ViewSetMixin):

    def get_queryset(self):
        queryset = self.queryset
        query = self.request.query_params.get('query', None)
        if query is not None:
            queryset = queryset.filter(name__icontains=query)

        updated_at = self.request.query_params.get('updated_at', None)
        if updated_at is not None:
            try:
                queryset = queryset.filter(updated_at__gte=updated_at)
            except FieldError:
                pass
            except ValidationError:
                raise APIException(_('Parameter updated_at incorrectly formatted'))

        limit = self.request.query_params.get('limit', None)
        random = self.request.query_params.get('random', False)
        if limit is not None:
            if random:
                queryset = queryset.order_by("?")[:int(limit)]
            else:
                queryset = queryset[:int(limit)]
        return queryset


class UserNameViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list:
    optional parameters

    - **filter_list**: array of user id's to get names for
    """
    queryset = User.objects
    serializer_class = UserNameSerializer
    permission_classes = [CustomIsGuest]
    http_method_names = ['get']

    def get_queryset(self):
        queryset = self.queryset.filter(userpreference__space=self.request.space)
        try:
            filter_list = self.request.query_params.get('filter_list', None)
            if filter_list is not None:
                queryset = queryset.filter(pk__in=json.loads(filter_list))
        except ValueError:
            raise APIException('Parameter filter_list incorrectly formatted')

        return queryset


class UserPreferenceViewSet(viewsets.ModelViewSet):
    queryset = UserPreference.objects
    serializer_class = UserPreferenceSerializer
    permission_classes = [CustomIsOwner, ]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class StorageViewSet(viewsets.ModelViewSet):
    # TODO handle delete protect error and adjust test
    queryset = Storage.objects
    serializer_class = StorageSerializer
    permission_classes = [CustomIsAdmin, ]

    def get_queryset(self):
        return self.queryset.filter(space=self.request.space)


class SyncViewSet(viewsets.ModelViewSet):
    queryset = Sync.objects
    serializer_class = SyncSerializer
    permission_classes = [CustomIsAdmin, ]

    def get_queryset(self):
        return self.queryset.filter(space=self.request.space)


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SyncLog.objects
    serializer_class = SyncLogSerializer
    permission_classes = [CustomIsAdmin, ]

    def get_queryset(self):
        return self.queryset.filter(sync__space=self.request.space)


class SupermarketViewSet(viewsets.ModelViewSet, StandardFilterMixin):
    queryset = Supermarket.objects
    serializer_class = SupermarketSerializer
    permission_classes = [CustomIsUser]

    def get_queryset(self):
        self.queryset = self.queryset.filter(space=self.request.space)
        return super().get_queryset()


class KeywordViewSet(viewsets.ModelViewSet, StandardFilterMixin):
    """
       list:
       optional parameters

       - **query**: search keywords for a string contained
                    in the keyword name (case in-sensitive)
       - **limit**: limits the amount of returned results
       """
    queryset = Keyword.objects
    serializer_class = KeywordSerializer
    permission_classes = [CustomIsUser]

    def get_queryset(self):
        self.queryset = self.queryset.filter(space=self.request.space)
        return super().get_queryset()


class UnitViewSet(viewsets.ModelViewSet, StandardFilterMixin):
    queryset = Unit.objects
    serializer_class = UnitSerializer
    permission_classes = [CustomIsUser]

    def get_queryset(self):
        self.queryset = self.queryset.filter(space=self.request.space)
        return super().get_queryset()


class FoodViewSet(viewsets.ModelViewSet, StandardFilterMixin):
    queryset = Food.objects
    serializer_class = FoodSerializer
    permission_classes = [CustomIsUser]

    def get_queryset(self):
        self.queryset = self.queryset.filter(space=self.request.space)
        return super().get_queryset()


class RecipeBookViewSet(viewsets.ModelViewSet, StandardFilterMixin):
    queryset = RecipeBook.objects
    serializer_class = RecipeBookSerializer
    permission_classes = [CustomIsOwner]

    def get_queryset(self):
        self.queryset = self.queryset.filter(created_by=self.request.user).filter(space=self.request.space)
        return super().get_queryset()


class RecipeBookEntryViewSet(viewsets.ModelViewSet, viewsets.GenericViewSet):
    queryset = RecipeBookEntry.objects
    serializer_class = RecipeBookEntrySerializer
    permission_classes = [CustomIsOwner]

    def get_queryset(self):
        return self.queryset.filter(book__created_by=self.request.user).filter(book__space=self.request.space)


class MealPlanViewSet(viewsets.ModelViewSet):
    """
    list:
    optional parameters

    - **from_date**: filter from (inclusive) a certain date onward
    - **to_date**: filter upward to (inclusive) certain date

    """
    queryset = MealPlan.objects
    serializer_class = MealPlanSerializer
    permission_classes = [CustomIsOwner]

    def get_queryset(self):
        queryset = self.queryset.filter(
            Q(created_by=self.request.user)
            | Q(shared=self.request.user)
        ).filter(space=self.request.space).distinct().all()

        from_date = self.request.query_params.get('from_date', None)
        if from_date is not None:
            queryset = queryset.filter(date__gte=from_date)

        to_date = self.request.query_params.get('to_date', None)
        if to_date is not None:
            queryset = queryset.filter(date__lte=to_date)
        return queryset


class MealTypeViewSet(viewsets.ModelViewSet):
    """
    returns list of meal types created by the
    requesting user ordered by the order field.
    """
    queryset = MealType.objects
    serializer_class = MealTypeSerializer
    permission_classes = [CustomIsOwner]

    def get_queryset(self):
        queryset = self.queryset.order_by('order', 'id').filter(created_by=self.request.user).filter(
            space=self.request.space).all()
        return queryset


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects
    serializer_class = IngredientSerializer
    permission_classes = [CustomIsUser]

    def get_queryset(self):
        return self.queryset.filter(step__recipe__space=self.request.space)


class StepViewSet(viewsets.ModelViewSet):
    queryset = Step.objects
    serializer_class = StepSerializer
    permission_classes = [CustomIsUser]

    def get_queryset(self):
        return self.queryset.filter(recipe__space=self.request.space)


class RecipePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


# TODO move to separate class to cleanup
class RecipeSchema(AutoSchema):

    def get_path_parameters(self, path, method):
        if not is_list_view(path, method, self.view):
            return []

        parameters = super().get_path_parameters(path, method)
        parameters.append({
            "name": 'query', "in": "query", "required": False,
            "description": 'Query string matched (fuzzy) against recipe name. In the future also fulltext search.',
            'schema': {'type': 'string', },
        })
        parameters.append({
            "name": 'keywords', "in": "query", "required": False,
            "description": 'Id of keyword a recipe should have. For multiple repeat parameter.',
            'schema': {'type': 'string', },
        })
        parameters.append({
            "name": 'foods', "in": "query", "required": False,
            "description": 'Id of food a recipe should have. For multiple repeat parameter.',
            'schema': {'type': 'string', },
        })
        parameters.append({
            "name": 'books', "in": "query", "required": False,
            "description": 'Id of book a recipe should have. For multiple repeat parameter.',
            'schema': {'type': 'string', },
        })
        parameters.append({
            "name": 'keywords_or', "in": "query", "required": False,
            "description": 'If recipe should have all (AND) or any (OR) of the provided keywords.',
            'schema': {'type': 'string', },
        })
        parameters.append({
            "name": 'foods_or', "in": "query", "required": False,
            "description": 'If recipe should have all (AND) or any (OR) any of the provided foods.',
            'schema': {'type': 'string', },
        })
        parameters.append({
            "name": 'books_or', "in": "query", "required": False,
            "description": 'If recipe should be in all (AND) or any (OR) any of the provided books.',
            'schema': {'type': 'string', },
        })
        parameters.append({
            "name": 'internal', "in": "query", "required": False,
            "description": 'true or false. If only internal recipes should be returned or not.',
            'schema': {'type': 'string', },
        })
        parameters.append({
            "name": 'random', "in": "query", "required": False,
            "description": 'true or false. returns the results in randomized order.',
            'schema': {'type': 'string', },
        })
        return parameters


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects
    serializer_class = RecipeSerializer
    # TODO split read and write permission for meal plan guest
    permission_classes = [CustomIsShare | CustomIsGuest]

    pagination_class = RecipePagination

    schema = RecipeSchema()

    def get_queryset(self):
        share = self.request.query_params.get('share', None)
        if not (share and self.detail):
            self.queryset = self.queryset.filter(space=self.request.space)

        self.queryset = search_recipes(self.queryset, self.request.GET)

        return super().get_queryset()

    # TODO write extensive tests for permissions
    def get_serializer_class(self):
        if self.action == 'list':
            return RecipeOverviewSerializer
        return self.serializer_class

    @decorators.action(
        detail=True,
        methods=['PUT'],
        serializer_class=RecipeImageSerializer,
        parser_classes=[MultiPartParser],
    )
    def image(self, request, pk):
        obj = self.get_object()

        if obj.get_space() != request.space:
            raise PermissionDenied(detail='You do not have the required permission to perform this action', code=403)

        serializer = self.serializer_class(
            obj, data=request.data, partial=True
        )

        if DEMO:
            raise PermissionDenied(detail='Not available in demo', code=None)

        if serializer.is_valid():
            serializer.save()
            img = Image.open(obj.image)

            basewidth = 720
            wpercent = (basewidth / float(img.size[0]))
            hsize = int((float(img.size[1]) * float(wpercent)))
            img = img.resize((basewidth, hsize), Image.ANTIALIAS)

            im_io = io.BytesIO()
            img.save(im_io, 'PNG', quality=70)
            obj.image = File(im_io, name=f'{uuid.uuid4()}_{obj.pk}.png')
            obj.save()

            return Response(serializer.data)
        return Response(serializer.errors, 400)


class ShoppingListRecipeViewSet(viewsets.ModelViewSet):
    queryset = ShoppingListRecipe.objects
    serializer_class = ShoppingListRecipeSerializer
    permission_classes = [CustomIsOwner | CustomIsShared]

    def get_queryset(self):
        return self.queryset.filter(
            Q(shoppinglist__created_by=self.request.user) | Q(shoppinglist__shared=self.request.user)).filter(
            shoppinglist__space=self.request.space).all()


class ShoppingListEntryViewSet(viewsets.ModelViewSet):
    queryset = ShoppingListEntry.objects
    serializer_class = ShoppingListEntrySerializer
    permission_classes = [CustomIsOwner | CustomIsShared]

    def get_queryset(self):
        return self.queryset.filter(
            Q(shoppinglist__created_by=self.request.user) | Q(shoppinglist__shared=self.request.user)).filter(
            shoppinglist__space=self.request.space).all()


class ShoppingListViewSet(viewsets.ModelViewSet):
    queryset = ShoppingList.objects
    serializer_class = ShoppingListSerializer
    permission_classes = [CustomIsOwner | CustomIsShared]

    def get_queryset(self):
        return self.queryset.filter(Q(created_by=self.request.user) | Q(shared=self.request.user)).filter(
            space=self.request.space).distinct()

    def get_serializer_class(self):
        try:
            autosync = self.request.query_params.get('autosync', False)
            if autosync:
                return ShoppingListAutoSyncSerializer
        except AttributeError:  # Needed for the openapi schema to determine a serializer without a request
            pass
        return self.serializer_class


class ViewLogViewSet(viewsets.ModelViewSet):
    queryset = ViewLog.objects
    serializer_class = ViewLogSerializer
    permission_classes = [CustomIsOwner]

    def get_queryset(self):
        self.queryset = self.queryset.filter(created_by=self.request.user).filter(space=self.request.space).all()
        if self.request.method == 'GET':
            return self.queryset[:5]
        else:
            return self.queryset


class CookLogViewSet(viewsets.ModelViewSet):
    queryset = CookLog.objects
    serializer_class = CookLogSerializer
    permission_classes = [CustomIsOwner]

    def get_queryset(self):
        self.queryset = self.queryset.filter(created_by=self.request.user).filter(space=self.request.space).all()
        if self.request.method == 'GET':
            return self.queryset[:5]
        else:
            return self.queryset


class ImportLogViewSet(viewsets.ModelViewSet):
    queryset = ImportLog.objects
    serializer_class = ImportLogSerializer
    permission_classes = [CustomIsUser]

    def get_queryset(self):
        return self.queryset.filter(space=self.request.space).all()


# -------------- non django rest api views --------------------

def get_recipe_provider(recipe):
    if recipe.storage.method == Storage.DROPBOX:
        return Dropbox
    elif recipe.storage.method == Storage.NEXTCLOUD:
        return Nextcloud
    elif recipe.storage.method == Storage.LOCAL:
        return Local
    else:
        raise Exception('Provider not implemented')


def update_recipe_links(recipe):
    if not recipe.link:
        # TODO response validation in apis
        recipe.link = get_recipe_provider(recipe).get_share_link(recipe)

    recipe.save()


@group_required('user')
def get_external_file_link(request, recipe_id):
    recipe = get_object_or_404(Recipe, pk=recipe_id, space=request.space)
    if not recipe.link:
        update_recipe_links(recipe)

    return HttpResponse(recipe.link)


@group_required('guest')
def get_recipe_file(request, recipe_id):
    recipe = get_object_or_404(Recipe, pk=recipe_id, space=request.space)
    if recipe.storage:
        return FileResponse(get_recipe_provider(recipe).get_file(recipe))
    else:
        return FileResponse()


@group_required('user')
def sync_all(request):
    if DEMO:
        messages.add_message(
            request, messages.ERROR, _('This feature is not available in the demo version!')
        )
        return redirect('index')

    monitors = Sync.objects.filter(active=True).filter(space=request.user.userpreference.space)

    error = False
    for monitor in monitors:
        if monitor.storage.method == Storage.DROPBOX:
            ret = Dropbox.import_all(monitor)
            if not ret:
                error = True
        if monitor.storage.method == Storage.NEXTCLOUD:
            ret = Nextcloud.import_all(monitor)
            if not ret:
                error = True
        if monitor.storage.method == Storage.LOCAL:
            ret = Local.import_all(monitor)
            if not ret:
                error = True

    if not error:
        messages.add_message(
            request, messages.SUCCESS, _('Sync successful!')
        )
        return redirect('list_recipe_import')
    else:
        messages.add_message(
            request, messages.ERROR, _('Error synchronizing with Storage')
        )
        return redirect('list_recipe_import')


@group_required('user')
@ajax_request
def log_cooking(request, recipe_id):
    recipe = get_object_or_None(Recipe, id=recipe_id)
    if recipe:
        log = CookLog.objects.create(created_by=request.user, recipe=recipe)
        servings = request.GET['s'] if 's' in request.GET else None
        if servings and re.match(r'^([1-9])+$', servings):
            log.servings = int(servings)

        rating = request.GET['r'] if 'r' in request.GET else None
        if rating and re.match(r'^([1-9])+$', rating):
            log.rating = int(rating)
        log.save()
        return {'msg': 'updated successfully'}

    return {'error': 'recipe does not exist'}


@group_required('user')
def get_plan_ical(request, from_date, to_date):
    queryset = MealPlan.objects.filter(
        Q(created_by=request.user) | Q(shared=request.user)
    ).filter(space=request.user.userpreference.space).distinct().all()

    if from_date is not None:
        queryset = queryset.filter(date__gte=from_date)

    if to_date is not None:
        queryset = queryset.filter(date__lte=to_date)

    cal = Calendar()

    for p in queryset:
        event = Event()
        event['uid'] = p.id
        event.add('dtstart', p.date)
        event.add('dtend', p.date)
        event['summary'] = f'{p.meal_type.name}: {p.get_label()}'
        event['description'] = p.note
        cal.add_component(event)

    response = FileResponse(io.BytesIO(cal.to_ical()))
    response["Content-Disposition"] = f'attachment; filename=meal_plan_{from_date}-{to_date}.ics'  # noqa: E501

    return response


@group_required('user')
def recipe_from_url(request):
    url = request.POST['url']

    try:
        scrape = scrape_me(url)
    except WebsiteNotImplementedError:
        try:
            scrape = scrape_me(url, wild_mode=True)
        except NoSchemaFoundInWildMode:
            return JsonResponse(
                {
                    'error': True,
                    'msg': _('The requested site provided malformed data and cannot be read.')  # noqa: E501
                },
                status=400)
    except ConnectionError:
        return JsonResponse(
            {
                'error': True,
                'msg': _('The requested page could not be found.')
            },
            status=400
        )
    return JsonResponse(get_from_scraper(scrape, request.space))


@group_required('user')
def recipe_from_url_old(request):
    url = request.POST['url']

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Safari/537.36'
        # noqa: E501
    }
    try:
        response = requests.get(url, headers=headers)
    except requests.exceptions.ConnectionError:
        return JsonResponse(
            {
                'error': True,
                'msg': _('The requested page could not be found.')
            },
            status=400
        )

    if response.status_code == 403:
        return JsonResponse(
            {
                'error': True,
                'msg': _('The requested page refused to provide any information (Status Code 403).')  # noqa: E501
            },
            status=400
        )
    return get_from_html(response.text, url, request.space)


@group_required('user')
def recipe_from_json(request):
    mjson = request.POST['json']

    md_json = json.loads(mjson)
    for ld_json_item in md_json:
        # recipes type might be wrapped in @graph type
        if '@graph' in ld_json_item:
            for x in md_json['@graph']:
                if '@type' in x and x['@type'] == 'Recipe':
                    md_json = x

        if ('@type' in md_json
                and md_json['@type'] == 'Recipe'):
            return JsonResponse(find_recipe_json(md_json, '', request.space))

    return JsonResponse(
        {
            'error': True,
            'msg': _('Could not parse correctly...')
        },
        status=400
    )


@group_required('user')
def ingredient_from_string(request):
    text = request.POST['text']
    amount, unit, food, note = parse(text)

    return JsonResponse(
        {
            'amount': amount,
            'unit': unit,
            'food': food,
        },
        status=200
    )
