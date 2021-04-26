"""
Source: https://djangosnippets.org/snippets/1703/
"""
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin

from cookbook.models import ShareLink
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS


def get_allowed_groups(groups_required):
    """
    Builds a list of all groups equal or higher to the provided groups
    This means checking for guest will also allow admins to access
    :param groups_required: list or tuple of groups
    :return: tuple of groups
    """
    groups_allowed = tuple(groups_required)
    if 'guest' in groups_required:
        groups_allowed = groups_allowed + ('user', 'admin')
    if 'user' in groups_required:
        groups_allowed = groups_allowed + ('admin',)
    return groups_allowed


def has_group_permission(user, groups):
    """
    Tests if a given user is member of a certain group (or any higher group)
    Superusers always bypass permission checks.
    Unauthenticated users cant be member of any group thus always return false.
    :param user: django auth user object
    :param groups: list or tuple of groups the user should be checked for
    :return: True if user is in allowed groups, false otherwise
    """
    if not user.is_authenticated:
        return False
    groups_allowed = get_allowed_groups(groups)
    if user.is_authenticated:
        if bool(user.groups.filter(name__in=groups_allowed)):
            return True
    return False


def is_object_owner(user, obj):
    """
    Tests if a given user is the owner of a given object
    test performed by checking user against the objects user
    and create_by field (if exists)
    superusers bypass all checks, unauthenticated users cannot own anything
    :param user django auth user object
    :param obj any object that should be tested
    :return: true if user is owner of object, false otherwise
    """
    if not user.is_authenticated:
        return False
    try:
        return obj.get_owner() == user
    except:
        return False


def is_object_shared(user, obj):
    """
    Tests if a given user is shared for a given object
    test performed by checking user against the objects shared table
    superusers bypass all checks, unauthenticated users cannot own anything
    :param user django auth user object
    :param obj any object that should be tested
    :return: true if user is shared for object, false otherwise
    """
    # TODO this could be improved/cleaned up by adding
    #      share checks for relevant objects
    if not user.is_authenticated:
        return False
    return user in obj.get_shared()


def share_link_valid(recipe, share):
    """
    Verifies the validity of a share uuid
    :param recipe: recipe object
    :param share: share uuid
    :return: true if a share link with the given recipe and uuid exists
    """
    try:
        return True if ShareLink.objects.filter(recipe=recipe, uuid=share).exists() else False
    except ValidationError:
        return False


# Django Views

def group_required(*groups_required):
    """
    Decorator that tests the requesting user to be member
    of at least one of the provided groups or higher level groups
    :param groups_required: list of required groups
    :return: true if member of group, false otherwise
    """

    def in_groups(u):
        return has_group_permission(u, groups_required)

    return user_passes_test(in_groups, login_url='view_no_perm')


class GroupRequiredMixin(object):
    """
        groups_required - list of strings, required param
    """

    groups_required = None

    def dispatch(self, request, *args, **kwargs):
        if not has_group_permission(request.user, self.groups_required):
            messages.add_message(request, messages.ERROR, _('You are not logged in and therefore cannot view this page!'))
            return HttpResponseRedirect(reverse_lazy('account_login') + '?next=' + request.path)

        try:
            obj = self.get_object()
            if obj.get_space() != request.space:
                messages.add_message(request, messages.ERROR, _('You do not have the required permissions to view this page!'))
                return HttpResponseRedirect(reverse_lazy('index'))
        except AttributeError:
            pass

        return super(GroupRequiredMixin, self).dispatch(request, *args, **kwargs)


class OwnerRequiredMixin(object):

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.add_message(request, messages.ERROR, _('You are not logged in and therefore cannot view this page!'))
            return HttpResponseRedirect(reverse_lazy('account_login') + '?next=' + request.path)
        else:
            if not is_object_owner(request.user, self.get_object()):
                messages.add_message(request, messages.ERROR, _('You cannot interact with this object as it is not owned by you!'))
                return HttpResponseRedirect(reverse('index'))

        try:
            obj = self.get_object()
            if obj.get_space() != request.space:
                messages.add_message(request, messages.ERROR, _('You do not have the required permissions to view this page!'))
                return HttpResponseRedirect(reverse_lazy('index'))
        except AttributeError:
            pass

        return super(OwnerRequiredMixin, self).dispatch(request, *args, **kwargs)


# Django Rest Framework Permission classes

class CustomIsOwner(permissions.BasePermission):
    """
    Custom permission class for django rest framework views
    verifies user has ownership over object
    (either user or created_by or user is request user)
    """
    message = _('You cannot interact with this object as it is not owned by you!')  # noqa: E501

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return is_object_owner(request.user, obj)


# TODO function duplicate/too similar name
class CustomIsShared(permissions.BasePermission):
    """
    Custom permission class for django rest framework views
    verifies user is shared for the object he is trying to access
    """
    message = _('You cannot interact with this object as it is not owned by you!')  # noqa: E501

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return is_object_shared(request.user, obj)


class CustomIsGuest(permissions.BasePermission):
    """
    Custom permission class for django rest framework views
    verifies the user is member of at least the group: guest
    """
    message = _('You do not have the required permissions to view this page!')

    def has_permission(self, request, view):
        return has_group_permission(request.user, ['guest'])

    def has_object_permission(self, request, view, obj):
        return has_group_permission(request.user, ['guest'])


class CustomIsUser(permissions.BasePermission):
    """
    Custom permission class for django rest framework views
    verifies the user is member of at least the group: user
    """
    message = _('You do not have the required permissions to view this page!')

    def has_permission(self, request, view):
        return has_group_permission(request.user, ['user'])


class CustomIsAdmin(permissions.BasePermission):
    """
    Custom permission class for django rest framework views
    verifies the user is member of at least the group: admin
    """
    message = _('You do not have the required permissions to view this page!')

    def has_permission(self, request, view):
        return has_group_permission(request.user, ['admin'])


class CustomIsShare(permissions.BasePermission):
    """
    Custom permission class for django rest framework views
    verifies the requesting user provided a valid share link
    """
    message = _('You do not have the required permissions to view this page!')

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS and 'pk' in view.kwargs

    def has_object_permission(self, request, view, obj):
        share = request.query_params.get('share', None)
        if share:
            return share_link_valid(obj, share)
        return False
