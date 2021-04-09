import re
import uuid
from datetime import date, timedelta

from annoying.fields import AutoOneToOneField
from django.contrib import auth
from django.contrib.auth.models import Group, User
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from django_scopes import ScopedManager

from recipes.settings import (COMMENT_PREF_DEFAULT, FRACTION_PREF_DEFAULT,
                              STICKY_NAV_PREF_DEFAULT)
from cookbook.managers import RecipeSearchManager


def get_user_name(self):
    if not (name := f"{self.first_name} {self.last_name}") == " ":
        return name
    else:
        return self.username


auth.models.User.add_to_class('get_user_name', get_user_name)


def get_model_name(model):
    return ('_'.join(re.findall('[A-Z][^A-Z]*', model.__name__))).lower()


class PermissionModelMixin:

    @staticmethod
    def get_space_key():
        return ('space',)

    def get_space_kwarg(self):
        return '__'.join(self.get_space_key())

    def get_owner(self):
        if getattr(self, 'created_by', None):
            return self.created_by
        if getattr(self, 'user', None):
            return self.user
        return None

    def get_shared(self):
        if getattr(self, 'shared', None):
            return self.shared.all()
        return []

    def get_space(self):
        p = '.'.join(self.get_space_key())
        if getattr(self, p, None):
            return getattr(self, p)
        raise NotImplementedError('get space for method not implemented and standard fields not available')


class Space(models.Model):
    name = models.CharField(max_length=128, default='Default')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    message = models.CharField(max_length=512, default='', blank=True)
    max_recipes = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class UserPreference(models.Model, PermissionModelMixin):
    # Themes
    BOOTSTRAP = 'BOOTSTRAP'
    DARKLY = 'DARKLY'
    FLATLY = 'FLATLY'
    SUPERHERO = 'SUPERHERO'

    THEMES = (
        (BOOTSTRAP, 'Bootstrap'),
        (DARKLY, 'Darkly'),
        (FLATLY, 'Flatly'),
        (SUPERHERO, 'Superhero')
    )

    # Nav colors
    PRIMARY = 'PRIMARY'
    SECONDARY = 'SECONDARY'
    SUCCESS = 'SUCCESS'
    INFO = 'INFO'
    WARNING = 'WARNING'
    DANGER = 'DANGER'
    LIGHT = 'LIGHT'
    DARK = 'DARK'

    COLORS = (
        (PRIMARY, 'Primary'),
        (SECONDARY, 'Secondary'),
        (SUCCESS, 'Success'), (INFO, 'Info'),
        (WARNING, 'Warning'),
        (DANGER, 'Danger'),
        (LIGHT, 'Light'),
        (DARK, 'Dark')
    )

    # Default Page
    SEARCH = 'SEARCH'
    PLAN = 'PLAN'
    BOOKS = 'BOOKS'

    PAGES = (
        (SEARCH, _('Search')),
        (PLAN, _('Meal-Plan')),
        (BOOKS, _('Books')),
    )

    # Search Style
    SMALL = 'SMALL'
    LARGE = 'LARGE'
    NEW = 'NEW'

    SEARCH_STYLE = ((SMALL, _('Small')), (LARGE, _('Large')), (NEW, _('New')))

    user = AutoOneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    theme = models.CharField(choices=THEMES, max_length=128, default=FLATLY)
    nav_color = models.CharField(
        choices=COLORS, max_length=128, default=PRIMARY
    )
    default_unit = models.CharField(max_length=32, default='g')
    use_fractions = models.BooleanField(default=FRACTION_PREF_DEFAULT)
    default_page = models.CharField(
        choices=PAGES, max_length=64, default=SEARCH
    )
    search_style = models.CharField(
        choices=SEARCH_STYLE, max_length=64, default=LARGE
    )
    show_recent = models.BooleanField(default=True)
    plan_share = models.ManyToManyField(
        User, blank=True, related_name='plan_share_default'
    )
    ingredient_decimals = models.IntegerField(default=2)
    comments = models.BooleanField(default=COMMENT_PREF_DEFAULT)
    shopping_auto_sync = models.IntegerField(default=5)
    sticky_navbar = models.BooleanField(default=STICKY_NAV_PREF_DEFAULT)

    space = models.ForeignKey(Space, on_delete=models.CASCADE, null=True)
    objects = ScopedManager(space='space')

    def __str__(self):
        return str(self.user)


class Storage(models.Model, PermissionModelMixin):
    DROPBOX = 'DB'
    NEXTCLOUD = 'NEXTCLOUD'
    LOCAL = 'LOCAL'
    STORAGE_TYPES = ((DROPBOX, 'Dropbox'), (NEXTCLOUD, 'Nextcloud'), (LOCAL, 'Local'))

    name = models.CharField(max_length=128)
    method = models.CharField(
        choices=STORAGE_TYPES, max_length=128, default=DROPBOX
    )
    username = models.CharField(max_length=128, blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)
    token = models.CharField(max_length=512, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    path = models.CharField(blank=True, default='', max_length=256)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.name


class Sync(models.Model, PermissionModelMixin):
    storage = models.ForeignKey(Storage, on_delete=models.PROTECT)
    path = models.CharField(max_length=512, default="")
    active = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.path


class SupermarketCategory(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=128, validators=[MinLengthValidator(1)])
    description = models.TextField(blank=True, null=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.name

    class Meta:
        unique_together = (('space', 'name'),)


class Supermarket(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=128, validators=[MinLengthValidator(1)])
    description = models.TextField(blank=True, null=True)
    categories = models.ManyToManyField(SupermarketCategory, through='SupermarketCategoryRelation')

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.name

    class Meta:
        unique_together = (('space', 'name'),)


class SupermarketCategoryRelation(models.Model, PermissionModelMixin):
    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE, related_name='category_to_supermarket')
    category = models.ForeignKey(SupermarketCategory, on_delete=models.CASCADE, related_name='category_to_supermarket')
    order = models.IntegerField(default=0)

    objects = ScopedManager(space='supermarket__space')

    @staticmethod
    def get_space_key():
        return 'supermarket', 'space'

    class Meta:
        ordering = ('order',)


class SyncLog(models.Model, PermissionModelMixin):
    sync = models.ForeignKey(Sync, on_delete=models.CASCADE)
    status = models.CharField(max_length=32)
    msg = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ScopedManager(space='sync__space')

    def __str__(self):
        return f"{self.created_at}:{self.sync} - {self.status}"


class Keyword(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=64)
    icon = models.CharField(max_length=16, blank=True, null=True)
    description = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        if self.icon:
            return f"{self.icon} {self.name}"
        else:
            return f"{self.name}"

    class Meta:
        unique_together = (('space', 'name'),)


class Unit(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=128, validators=[MinLengthValidator(1)])
    description = models.TextField(blank=True, null=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.name

    class Meta:
        unique_together = (('space', 'name'),)


class Food(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=128, validators=[MinLengthValidator(1)])
    recipe = models.ForeignKey('Recipe', null=True, blank=True, on_delete=models.SET_NULL)
    supermarket_category = models.ForeignKey(SupermarketCategory, null=True, blank=True, on_delete=models.SET_NULL)
    ignore_shopping = models.BooleanField(default=False)
    description = models.TextField(default='', blank=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.name

    class Meta:
        unique_together = (('space', 'name'),)


class Ingredient(models.Model, PermissionModelMixin):
    food = models.ForeignKey(Food, on_delete=models.PROTECT, null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True)
    amount = models.DecimalField(default=0, decimal_places=16, max_digits=32)
    note = models.CharField(max_length=256, null=True, blank=True)
    is_header = models.BooleanField(default=False)
    no_amount = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    objects = ScopedManager(space='step__recipe__space')

    @staticmethod
    def get_space_key():
        return 'step', 'recipe', 'space'

    def get_space(self):
        return self.step_set.first().recipe_set.first().space

    def __str__(self):
        return str(self.amount) + ' ' + str(self.unit) + ' ' + str(self.food)

    class Meta:
        ordering = ['order', 'pk']


class Step(models.Model, PermissionModelMixin):
    TEXT = 'TEXT'
    TIME = 'TIME'

    name = models.CharField(max_length=128, default='', blank=True)
    type = models.CharField(
        choices=((TEXT, _('Text')), (TIME, _('Time')),),
        default=TEXT,
        max_length=16
    )
    instruction = models.TextField(blank=True)
    ingredients = models.ManyToManyField(Ingredient, blank=True)
    time = models.IntegerField(default=0, blank=True)
    order = models.IntegerField(default=0)
    show_as_header = models.BooleanField(default=True)

    objects = ScopedManager(space='recipe__space')

    @staticmethod
    def get_space_key():
        return 'recipe', 'space'

    def get_space(self):
        return self.recipe_set.first().space

    def get_instruction_render(self):
        from cookbook.helper.template_helper import render_instructions
        return render_instructions(self)

    class Meta:
        ordering = ['order', 'pk']


class NutritionInformation(models.Model, PermissionModelMixin):
    fats = models.DecimalField(default=0, decimal_places=16, max_digits=32)
    carbohydrates = models.DecimalField(
        default=0, decimal_places=16, max_digits=32
    )
    proteins = models.DecimalField(default=0, decimal_places=16, max_digits=32)
    calories = models.DecimalField(default=0, decimal_places=16, max_digits=32)
    source = models.CharField(
        max_length=512, default="", null=True, blank=True
    )

    objects = ScopedManager(space='recipe__space')

    @staticmethod
    def get_space_key():
        return 'recipe', 'space'

    def get_space(self):
        return self.recipe_set.first().space

    def __str__(self):
        return 'Nutrition'


# TODO adjust model based on DB capabilities
# options to have multiple recipe models based on DB capability (to drive search)
# required_db_features, required-db-vendor
# https://docs.djangoproject.com/en/3.1/ref/models/options/#required-db-vendor
class Recipe(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=128)
    description = models.CharField(max_length=512, blank=True, null=True)
    servings = models.IntegerField(default=1)
    servings_text = models.CharField(default='', blank=True, max_length=32)
    image = models.ImageField(upload_to='recipes/', blank=True, null=True)
    storage = models.ForeignKey(
        Storage, on_delete=models.PROTECT, blank=True, null=True
    )
    file_uid = models.CharField(max_length=256, default="", blank=True)
    file_path = models.CharField(max_length=512, default="", blank=True)
    link = models.CharField(max_length=512, null=True, blank=True)
    cors_link = models.CharField(max_length=1024, null=True, blank=True)
    keywords = models.ManyToManyField(Keyword, blank=True)
    steps = models.ManyToManyField(Step, blank=True)
    working_time = models.IntegerField(default=0)
    waiting_time = models.IntegerField(default=0)
    internal = models.BooleanField(default=False)
    nutrition = models.ForeignKey(
        NutritionInformation, blank=True, null=True, on_delete=models.CASCADE
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    search_vector = SearchVectorField(null=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(_manager_class=RecipeSearchManager, space='space')

    def __str__(self):
        return self.name

    class Meta():
        indexes = (GinIndex(fields=["search_vector"]),)


class Comment(models.Model, PermissionModelMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    text = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ScopedManager(space='recipe__space')

    @staticmethod
    def get_space_key():
        return 'recipe', 'space'

    def __str__(self):
        return self.text


class RecipeImport(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=128)
    storage = models.ForeignKey(Storage, on_delete=models.PROTECT)
    file_uid = models.CharField(max_length=256, default="")
    file_path = models.CharField(max_length=512, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.name


class RecipeBook(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=16, blank=True, null=True)
    shared = models.ManyToManyField(User, blank=True, related_name='shared_with')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.name


class RecipeBookEntry(models.Model, PermissionModelMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    book = models.ForeignKey(RecipeBook, on_delete=models.CASCADE)

    objects = ScopedManager(space='book__space')

    @staticmethod
    def get_space_key():
        return 'book', 'space'

    def __str__(self):
        return self.recipe.name

    def get_owner(self):
        try:
            return self.book.created_by
        except AttributeError:
            return None

    class Meta:
        unique_together = (('recipe', 'book'),)


class MealType(models.Model, PermissionModelMixin):
    name = models.CharField(max_length=128)
    order = models.IntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.name


class MealPlan(models.Model, PermissionModelMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, blank=True, null=True)
    servings = models.DecimalField(default=1, max_digits=8, decimal_places=4)
    title = models.CharField(max_length=64, blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    shared = models.ManyToManyField(User, blank=True, related_name='plan_share')
    meal_type = models.ForeignKey(MealType, on_delete=models.CASCADE)
    note = models.TextField(blank=True)
    date = models.DateField()

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def get_label(self):
        if self.title:
            return self.title
        return str(self.recipe)

    def get_meal_name(self):
        return self.meal_type.name

    def __str__(self):
        return f'{self.get_label()} - {self.date} - {self.meal_type.name}'


class ShoppingListRecipe(models.Model, PermissionModelMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, null=True, blank=True)
    servings = models.DecimalField(default=1, max_digits=8, decimal_places=4)

    objects = ScopedManager(space='recipe__space')

    @staticmethod
    def get_space_key():
        return 'recipe', 'space'

    def get_space(self):
        return self.recipe.space

    def __str__(self):
        return f'Shopping list recipe {self.id} - {self.recipe}'

    def get_owner(self):
        try:
            return self.shoppinglist_set.first().created_by
        except AttributeError:
            return None


class ShoppingListEntry(models.Model, PermissionModelMixin):
    list_recipe = models.ForeignKey(ShoppingListRecipe, on_delete=models.CASCADE, null=True, blank=True)
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(default=0, decimal_places=16, max_digits=32)
    order = models.IntegerField(default=0)
    checked = models.BooleanField(default=False)

    objects = ScopedManager(space='shoppinglist__space')

    @staticmethod
    def get_space_key():
        return 'shoppinglist', 'space'

    def get_space(self):
        return self.shoppinglist_set.first().space

    def __str__(self):
        return f'Shopping list entry {self.id}'

    def get_shared(self):
        return self.shoppinglist_set.first().shared.all()

    def get_owner(self):
        try:
            return self.shoppinglist_set.first().created_by
        except AttributeError:
            return None


class ShoppingList(models.Model, PermissionModelMixin):
    uuid = models.UUIDField(default=uuid.uuid4)
    note = models.TextField(blank=True, null=True)
    recipes = models.ManyToManyField(ShoppingListRecipe, blank=True)
    entries = models.ManyToManyField(ShoppingListEntry, blank=True)
    shared = models.ManyToManyField(User, blank=True, related_name='list_share')
    supermarket = models.ForeignKey(Supermarket, null=True, blank=True, on_delete=models.SET_NULL)
    finished = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return f'Shopping list {self.id}'


class ShareLink(models.Model, PermissionModelMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return f'{self.recipe} - {self.uuid}'


def default_valid_until():
    return date.today() + timedelta(days=14)


class InviteLink(models.Model, PermissionModelMixin):
    uuid = models.UUIDField(default=uuid.uuid4)
    username = models.CharField(blank=True, max_length=64)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    valid_until = models.DateField(default=default_valid_until)
    used_by = models.ForeignKey(
        User, null=True, on_delete=models.CASCADE, related_name='used_by'
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return f'{self.uuid}'


class TelegramBot(models.Model, PermissionModelMixin):
    token = models.CharField(max_length=256)
    name = models.CharField(max_length=128, default='', blank=True)
    chat_id = models.CharField(max_length=128, default='', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    webhook_token = models.UUIDField(default=uuid.uuid4)

    objects = ScopedManager(space='space')
    space = models.ForeignKey(Space, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name}"


class CookLog(models.Model, PermissionModelMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    rating = models.IntegerField(null=True)
    servings = models.IntegerField(default=0)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.recipe.name


class ViewLog(models.Model, PermissionModelMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    objects = ScopedManager(space='space')

    def __str__(self):
        return self.recipe.name


class ImportLog(models.Model, PermissionModelMixin):
    type = models.CharField(max_length=32)
    running = models.BooleanField(default=True)
    msg = models.TextField(default="")
    keyword = models.ForeignKey(Keyword, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    objects = ScopedManager(space='space')
    space = models.ForeignKey(Space, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.created_at}:{self.type}"
