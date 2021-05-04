import datetime
import json
import uuid
from io import BytesIO, StringIO
from zipfile import ZipFile, BadZipFile

from django.core.files import File
from django.http import HttpResponse
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django_scopes import scope

from cookbook.forms import ImportExportBase
from cookbook.models import Keyword, Recipe


class Integration:
    request = None
    keyword = None
    files = None
    export_type = None
    ignored_recipes = []

    def __init__(self, request, export_type):
        """
        Integration for importing and exporting recipes
        :param request: request context of import session (used to link user to created objects)
        """
        self.request = request
        self.export_type = export_type
        self.keyword = Keyword.objects.create(
            name=f'Import {export_type} {date_format(datetime.datetime.now(), "DATETIME_FORMAT")}.{datetime.datetime.now().strftime("%S")}',
            description=f'Imported by {request.user.get_user_name()} at {date_format(datetime.datetime.now(), "DATETIME_FORMAT")}. Type: {export_type}',
            icon='📥',
            space=request.space
        )

    def do_export(self, recipes):
        """
        Perform the export based on a list of recipes
        :param recipes: list of recipe objects
        :return: HttpResponse with a ZIP file that is directly downloaded
        """

        # TODO this is temporary, find a better solution for different export formats when doing other exporters
        if self.export_type != ImportExportBase.RECIPESAGE:
            export_zip_stream = BytesIO()
            export_zip_obj = ZipFile(export_zip_stream, 'w')

            for r in recipes:
                if r.internal and r.space == self.request.space:
                    recipe_zip_stream = BytesIO()
                    recipe_zip_obj = ZipFile(recipe_zip_stream, 'w')

                    recipe_stream = StringIO()
                    filename, data = self.get_file_from_recipe(r)
                    recipe_stream.write(data)
                    recipe_zip_obj.writestr(filename, recipe_stream.getvalue())
                    recipe_stream.close()

                    try:
                        recipe_zip_obj.write(r.image.path, 'image.png')
                    except ValueError:
                        pass

                    recipe_zip_obj.close()
                    export_zip_obj.writestr(str(r.pk) + '.zip', recipe_zip_stream.getvalue())

            export_zip_obj.close()

            response = HttpResponse(export_zip_stream.getvalue(), content_type='application/force-download')
            response['Content-Disposition'] = 'attachment; filename="export.zip"'
            return response
        else:
            json_list = []
            for r in recipes:
                json_list.append(self.get_file_from_recipe(r))

            response = HttpResponse(json.dumps(json_list), content_type='application/force-download')
            response['Content-Disposition'] = 'attachment; filename="recipes.json"'
            return response

    def import_file_name_filter(self, zip_info_object):
        """
        Since zipfile.namelist() returns all files in all subdirectories this function allows filtering of files
        If false is returned the file will be ignored
        By default all files are included
        :param zip_info_object: ZipInfo object
        :return: Boolean if object should be included
        """
        return True

    def do_import(self, files, il, import_duplicates):
        """
        Imports given files
        :param import_duplicates: if true duplicates are imported as well
        :param files: List of in memory files
        :param il: Import Log object to refresh while running
        :return: HttpResponseRedirect to the recipe search showing all imported recipes
        """
        with scope(space=self.request.space):
            self.keyword.name = _('Import') + ' ' + str(il.pk)
            self.keyword.save()

            try:
                self.files = files
                for f in files:
                    if '.zip' in f['name'] or '.paprikarecipes' in f['name']:
                        import_zip = ZipFile(f['file'])
                        for z in import_zip.filelist:
                            if self.import_file_name_filter(z):
                                recipe = self.get_recipe_from_file(BytesIO(import_zip.read(z.filename)))
                                recipe.keywords.add(self.keyword)
                                il.msg += f'{recipe.pk} - {recipe.name} \n'
                                self.handle_duplicates(recipe, import_duplicates)

                        import_zip.close()
                    elif '.json' in f['name'] or '.txt' in f['name']:
                        data_list = self.split_recipe_file(f['file'])
                        for d in data_list:
                            recipe = self.get_recipe_from_file(d)
                            recipe.keywords.add(self.keyword)
                            il.msg += f'{recipe.pk} - {recipe.name} \n'
                            self.handle_duplicates(recipe, import_duplicates)
                    elif '.rtk' in f['name']:
                        import_zip = ZipFile(f['file'])
                        for z in import_zip.filelist:
                            if self.import_file_name_filter(z):
                                data_list = self.split_recipe_file(import_zip.read(z.filename).decode('utf-8'))
                                for d in data_list:
                                    recipe = self.get_recipe_from_file(d)
                                    recipe.keywords.add(self.keyword)
                                    il.msg += f'{recipe.pk} - {recipe.name} \n'
                                    self.handle_duplicates(recipe, import_duplicates)
                        import_zip.close()
                    else:
                        recipe = self.get_recipe_from_file(f['file'])
                        recipe.keywords.add(self.keyword)
                        il.msg += f'{recipe.pk} - {recipe.name} \n'
                        self.handle_duplicates(recipe, import_duplicates)
            except BadZipFile:
                il.msg += 'ERROR ' + _('Importer expected a .zip file. Did you choose the correct importer type for your data ?') + '\n'

            if len(self.ignored_recipes) > 0:
                il.msg += '\n' + _('The following recipes were ignored because they already existed:') + ' ' + ', '.join(self.ignored_recipes) + '\n\n'

            il.keyword = self.keyword
            il.msg += (_('Imported %s recipes.') % Recipe.objects.filter(keywords=self.keyword).count()) + '\n'
            il.running = False
            il.save()

    def handle_duplicates(self, recipe, import_duplicates):
        """
        Checks if a recipe is already present, if so deletes it
        :param recipe: Recipe object
        :param import_duplicates: if duplicates should be imported
        """
        if Recipe.objects.filter(space=self.request.space, name=recipe.name).count() > 1 and not import_duplicates:
            recipe.delete()
            self.ignored_recipes.append(recipe.name)

    @staticmethod
    def import_recipe_image(recipe, image_file):
        """
        Adds an image to a recipe naming it correctly
        :param recipe: Recipe object
        :param image_file: ByteIO stream containing the image
        """
        recipe.image = File(image_file, name=f'{uuid.uuid4()}_{recipe.pk}.png')
        recipe.save()

    def get_recipe_from_file(self, file):
        """
        Takes any file like object and converts it into a recipe
        :param file: ByteIO or any file like object, depends on provider
        :return: Recipe object
        """
        raise NotImplementedError('Method not implemented in integration')

    def split_recipe_file(self, file):
        """
        Takes a file that contains multiple recipes and splits it into a list of strings of various formats (e.g. json, text, ..)
        :param file: ByteIO or any file like object, depends on provider
        :return: list of strings
        """
        raise NotImplementedError('Method not implemented in integration')

    def get_file_from_recipe(self, recipe):
        """
        Takes a recipe object and converts it to a string (depending on the format)
        returns both the filename of the exported file and the file contents
        :param recipe: Recipe object that should be converted
        :returns:
            - name - file name in export
            - data - string content for file to get created in export zip
        """
        raise NotImplementedError('Method not implemented in integration')
