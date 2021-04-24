import bleach
import markdown as md
from bleach_allowlist import markdown_attrs, markdown_tags
from cookbook.helper.mdx_attributes import MarkdownFormatExtension
from cookbook.helper.mdx_urlize import UrlizeExtension
from cookbook.models import Space, get_model_name
from django import template
from django.db.models import Avg
from django.urls import NoReverseMatch, reverse
from recipes import settings
from gettext import gettext as _

register = template.Library()


@register.filter()
def get_class_name(value):
    return value.__class__.__name__


@register.filter()
def get_class(value):
    return value.__class__


@register.simple_tag
def delete_url(model, pk):
    try:
        return reverse(f'delete_{get_model_name(model)}', args=[pk])
    except NoReverseMatch:
        return None


@register.filter()
def markdown(value):
    tags = markdown_tags + [
        'pre', 'table', 'td', 'tr', 'th', 'tbody', 'style', 'thead'
    ]
    parsed_md = md.markdown(
        value,
        extensions=[
            'markdown.extensions.fenced_code', 'tables',
            UrlizeExtension(), MarkdownFormatExtension()
        ]
    )
    markdown_attrs['*'] = markdown_attrs['*'] + ['class']
    return bleach.clean(parsed_md, tags, markdown_attrs)


@register.simple_tag
def recipe_rating(recipe, user):
    if not user.is_authenticated:
        return ''
    rating = recipe.cooklog_set \
        .filter(created_by=user) \
        .aggregate(Avg('rating'))
    if rating['rating__avg']:

        rating_stars = '<span style="display: inline-block;">'
        for i in range(int(rating['rating__avg'])):
            rating_stars = rating_stars + '<i class="fas fa-star fa-xs"></i>'

        if rating['rating__avg'] % 1 >= 0.5:
            rating_stars = rating_stars + '<i class="fas fa-star-half-alt fa-xs"></i>'  # noqa: E501

        rating_stars += '</span>'

        return rating_stars
    else:
        return ''


@register.simple_tag
def recipe_last(recipe, user):
    if not user.is_authenticated:
        return ''
    last = recipe.cooklog_set.filter(created_by=user).last()
    if last:
        return last.created_at
    else:
        return ''


@register.simple_tag
def page_help(page_name):
    help_pages = {
        'edit_storage': 'https://vabene1111.github.io/recipes/features/external_recipes/',
        'view_shopping': 'https://vabene1111.github.io/recipes/features/shopping/',
        'view_import': 'https://vabene1111.github.io/recipes/features/import_export/',
        'view_export': 'https://vabene1111.github.io/recipes/features/import_export/',
    }

    link = help_pages.get(page_name, '')

    if link != '':
        return f'<li class="nav-item"><a class="nav-link" target="_blank" rel="nofollow noreferrer" href="{link}"><i class="far fa-question-circle"></i>&zwnj;<span class="d-lg-none"> {_("Help")}</span></a></li>'
    else:
        return None


@register.simple_tag
def message_of_the_day():
    return Space.objects.first().message


@register.simple_tag
def is_debug():
    return settings.DEBUG


@register.simple_tag()
def markdown_link():
    return f"{_('You can use markdown to format this field. See the ')}<a target='_blank' href='{reverse('docs_markdown')}'>{_('docs here')}</a>"


@register.simple_tag
def base_path(request, path_type):
    if path_type == 'base':
        return request._current_scheme_host + request.META.get('HTTP_X_SCRIPT_NAME', '')
    elif path_type == 'script':
        return request.META.get('HTTP_X_SCRIPT_NAME', '')
