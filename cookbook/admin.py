from django.conf import settings
from django.contrib import admin
from django.contrib.postgres.search import SearchVector
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from django_scopes import scopes_disabled

from .models import (Comment, CookLog, Food, Ingredient, InviteLink, Keyword,
                     MealPlan, MealType, NutritionInformation, Recipe,
                     RecipeBook, RecipeBookEntry, RecipeImport, ShareLink,
                     ShoppingList, ShoppingListEntry, ShoppingListRecipe,
                     Space, Step, Storage, Sync, SyncLog, Unit, UserPreference,
                     ViewLog, Supermarket, SupermarketCategory, SupermarketCategoryRelation, ImportLog, TelegramBot)


class CustomUserAdmin(UserAdmin):
    def has_add_permission(self, request, obj=None):
        return False


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

admin.site.unregister(Group)


class SpaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'message')


admin.site.register(Space, SpaceAdmin)


class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('name', 'space', 'theme', 'nav_color', 'default_page', 'search_style',)

    @staticmethod
    def name(obj):
        return obj.user.get_user_name()


admin.site.register(UserPreference, UserPreferenceAdmin)


class StorageAdmin(admin.ModelAdmin):
    list_display = ('name', 'method')


admin.site.register(Storage, StorageAdmin)


class SyncAdmin(admin.ModelAdmin):
    list_display = ('storage', 'path', 'active', 'last_checked')


admin.site.register(Sync, SyncAdmin)


class SupermarketCategoryInline(admin.TabularInline):
    model = SupermarketCategoryRelation


class SupermarketAdmin(admin.ModelAdmin):
    inlines = (SupermarketCategoryInline,)


admin.site.register(Supermarket, SupermarketAdmin)
admin.site.register(SupermarketCategory)


class SyncLogAdmin(admin.ModelAdmin):
    list_display = ('sync', 'status', 'msg', 'created_at')


admin.site.register(SyncLog, SyncLogAdmin)

admin.site.register(Keyword)


class StepAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'order')


admin.site.register(Step, StepAdmin)


@admin.action(description='Rebuild index for selected recipes')
def rebuild_index(modeladmin, request, queryset):
    with scopes_disabled():
        search_vector = (
            SearchVector('name', weight='A')
            + SearchVector('description', weight='B'))
        queryset.update(search_vector=search_vector)


class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'internal', 'created_by', 'storage')

    @staticmethod
    def created_by(obj):
        return obj.created_by.get_user_name()

    if settings.DATABASES['default']['ENGINE'] in ['django.db.backends.postgresql_psycopg2', 'django.db.backends.postgresql']:
        actions = [rebuild_index]


admin.site.register(Recipe, RecipeAdmin)

admin.site.register(Unit)
admin.site.register(Food)


class IngredientAdmin(admin.ModelAdmin):
    list_display = ('food', 'amount', 'unit')


admin.site.register(Ingredient, IngredientAdmin)


class CommentAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'name', 'created_at')

    @staticmethod
    def name(obj):
        return obj.created_by.get_user_name()


admin.site.register(Comment, CommentAdmin)


class RecipeImportAdmin(admin.ModelAdmin):
    list_display = ('name', 'storage', 'file_path')


admin.site.register(RecipeImport, RecipeImportAdmin)


class RecipeBookAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_name')

    @staticmethod
    def user_name(obj):
        return obj.created_by.get_user_name()


admin.site.register(RecipeBook, RecipeBookAdmin)


class RecipeBookEntryAdmin(admin.ModelAdmin):
    list_display = ('book', 'recipe')


admin.site.register(RecipeBookEntry, RecipeBookEntryAdmin)


class MealPlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe', 'meal_type', 'date')

    @staticmethod
    def user(obj):
        return obj.created_by.get_user_name()


admin.site.register(MealPlan, MealPlanAdmin)


class MealTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'order')


admin.site.register(MealType, MealTypeAdmin)


class ViewLogAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'created_by', 'created_at')


admin.site.register(ViewLog, ViewLogAdmin)


class InviteLinkAdmin(admin.ModelAdmin):
    list_display = (
        'username', 'group', 'valid_until',
        'created_by', 'created_at', 'used_by'
    )


admin.site.register(InviteLink, InviteLinkAdmin)


class CookLogAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'created_by', 'created_at', 'rating', 'servings')


admin.site.register(CookLog, CookLogAdmin)


class ShoppingListRecipeAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipe', 'servings')


admin.site.register(ShoppingListRecipe, ShoppingListRecipeAdmin)


class ShoppingListEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'food', 'unit', 'list_recipe', 'checked')


admin.site.register(ShoppingListEntry, ShoppingListEntryAdmin)


class ShoppingListAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_by', 'created_at')


admin.site.register(ShoppingList, ShoppingListAdmin)


class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'created_by', 'uuid', 'created_at',)


admin.site.register(ShareLink, ShareLinkAdmin)


class NutritionInformationAdmin(admin.ModelAdmin):
    list_display = ('id',)


admin.site.register(NutritionInformation, NutritionInformationAdmin)


class ImportLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'running', 'created_by', 'created_at',)


admin.site.register(ImportLog, ImportLogAdmin)


class TelegramBotAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_by',)


admin.site.register(TelegramBot, TelegramBotAdmin)
