import re
import threading
from io import BytesIO

from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _

from cookbook.forms import ExportForm, ImportForm, ImportExportBase
from cookbook.helper.permission_helper import group_required
from cookbook.integration.Pepperplate import Pepperplate
from cookbook.integration.cheftap import ChefTap
from cookbook.integration.chowdown import Chowdown
from cookbook.integration.default import Default
from cookbook.integration.domestica import Domestica
from cookbook.integration.mealie import Mealie
from cookbook.integration.mealmaster import MealMaster
from cookbook.integration.nextcloud_cookbook import NextcloudCookbook
from cookbook.integration.paprika import Paprika
from cookbook.integration.recettetek import RecetteTek
from cookbook.integration.recipesage import RecipeSage
from cookbook.integration.rezkonv import RezKonv
from cookbook.integration.safron import Safron
from cookbook.models import Recipe, ImportLog


def get_integration(request, export_type):
    if export_type == ImportExportBase.DEFAULT:
        return Default(request, export_type)
    if export_type == ImportExportBase.PAPRIKA:
        return Paprika(request, export_type)
    if export_type == ImportExportBase.NEXTCLOUD:
        return NextcloudCookbook(request, export_type)
    if export_type == ImportExportBase.MEALIE:
        return Mealie(request, export_type)
    if export_type == ImportExportBase.CHOWDOWN:
        return Chowdown(request, export_type)
    if export_type == ImportExportBase.SAFRON:
        return Safron(request, export_type)
    if export_type == ImportExportBase.CHEFTAP:
        return ChefTap(request, export_type)
    if export_type == ImportExportBase.PEPPERPLATE:
        return Pepperplate(request, export_type)
    if export_type == ImportExportBase.DOMESTICA:
        return Domestica(request, export_type)
    if export_type == ImportExportBase.RECETTETEK:
        return RecetteTek(request, export_type)
    if export_type == ImportExportBase.RECIPESAGE:
        return RecipeSage(request, export_type)
    if export_type == ImportExportBase.REZKONV:
        return RezKonv(request, export_type)
    if export_type == ImportExportBase.MEALMASTER:
        return MealMaster(request, export_type)


@group_required('user')
def import_recipe(request):
    if request.method == "POST":
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                integration = get_integration(request, form.cleaned_data['type'])

                il = ImportLog.objects.create(type=form.cleaned_data['type'], created_by=request.user, space=request.space)
                files = []
                for f in request.FILES.getlist('files'):
                    files.append({'file': BytesIO(f.read()), 'name': f.name})
                t = threading.Thread(target=integration.do_import, args=[files, il, form.cleaned_data['duplicates']])
                t.setDaemon(True)
                t.start()

                return JsonResponse({'import_id': [il.pk]})
            except NotImplementedError:
                return JsonResponse(
                    {
                        'error': True,
                        'msg': _('Importing is not implemented for this provider')
                    },
                    status=400
                )
    else:
        form = ImportForm()

    return render(request, 'import.html', {'form': form})


@group_required('user')
def export_recipe(request):
    if request.method == "POST":
        form = ExportForm(request.POST, space=request.space)
        if form.is_valid():
            try:
                recipes = form.cleaned_data['recipes']
                if form.cleaned_data['all']:
                    recipes = Recipe.objects.filter(space=request.space, internal=True).all()
                integration = get_integration(request, form.cleaned_data['type'])
                return integration.do_export(recipes)
            except NotImplementedError:
                messages.add_message(request, messages.ERROR, _('Exporting is not implemented for this provider'))

    else:
        form = ExportForm(space=request.space)
        recipe = request.GET.get('r')
        if recipe:
            if re.match(r'^([0-9])+$', recipe):
                if recipe := Recipe.objects.filter(pk=int(recipe), space=request.space).first():
                    form = ExportForm(initial={'recipes': recipe}, space=request.space)

    return render(request, 'export.html', {'form': form})


@group_required('user')
def import_response(request, pk):
    return render(request, 'import_response.html', {'pk': pk})
