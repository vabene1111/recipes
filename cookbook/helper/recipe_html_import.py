import json
import re
from json.decoder import JSONDecodeError

from bs4 import BeautifulSoup
from bs4.element import Tag
from cookbook.helper import recipe_url_import as helper
from recipe_scrapers._utils import get_host_name, normalize_string


def get_recipe_from_source(text, url, space):
    def build_node(k, v):
        if isinstance(v, dict):
            node = {
                'name': k,
                'value': k,
                'children': get_children_dict(v)
            }
        elif isinstance(v, list):
            node = {
                'name': k,
                'value': k,
                'children': get_children_list(v)
            }
        else:
            node = {
                'name': k + ": " + normalize_string(str(v)),
                'value': normalize_string(str(v))
            }
        return node

    def get_children_dict(children):
        kid_list = []
        for k, v in children.items():
            kid_list.append(build_node(k, v))
        return kid_list

    def get_children_list(children):
        kid_list = []
        for kid in children:
            if type(kid) == list:
                node = {
                    'name': "unknown list",
                    'value': "unknown list",
                    'children': get_children_list(kid)
                }
                kid_list.append(node)
            elif type(kid) == dict:
                for k, v in kid.items():
                    kid_list.append(build_node(k, v))
            else:
                kid_list.append({
                    'name': normalize_string(str(kid)),
                    'value': normalize_string(str(kid))
                })
        return kid_list

    recipe_json = {
                'name': '',
                'description': '',
                'image': '',
                'keywords': [],
                'recipeIngredient': [],
                'recipeInstructions': '',
                'servings': '',
                'prepTime': '',
                'cookTime': ''
                }
    recipe_tree = []
    temp_tree = []
    parse_list = []
    html_data = []
    images = []

    try:
        parse_list.append(remove_graph(json.loads(text)))
    except JSONDecodeError:
        soup = BeautifulSoup(text, "html.parser")
        html_data = get_from_html(soup)
        images += get_images_from_source(soup, url)
        for el in soup.find_all('script', type='application/ld+json'):
            parse_list.append(remove_graph(el))
        for el in soup.find_all(type='application/json'):
            parse_list.append(remove_graph(el))

    # if a url was not provided, try to find one in the first document
    if not url:
        if 'url' in parse_list[0]:
            url = parse_list[0]['url']


    # first try finding ld+json as its most common
    for el in parse_list:

        if isinstance(el, Tag):
            try:
                el = json.loads(el.string)
            except TypeError:
                continue

        for k, v in el.items():
            if isinstance(v, dict):
                node = {
                    'name': k,
                    'value': k,
                    'children': get_children_dict(v)
                }
            elif isinstance(v, list):
                node = {
                    'name': k,
                    'value': k,
                    'children': get_children_list(v)
                }
            else:
                node = {
                    'name': k + ": " + normalize_string(str(v)),
                    'value': normalize_string(str(v))
                }
            temp_tree.append(node)

        if '@type' in el and el['@type'] == 'Recipe':
            recipe_json = helper.find_recipe_json(el, None, space)
            recipe_tree += [{'name': 'ld+json', 'children': temp_tree}]
        else:
            recipe_tree += [{'name': 'json', 'children': temp_tree}]
        temp_tree = []

    return recipe_json, recipe_tree, html_data, images


def get_from_html(soup):
    INVISIBLE_ELEMS = ('style', 'script', 'head', 'title')
    html = []
    for s in soup.strings:
        if ((s.parent.name not in INVISIBLE_ELEMS) and (len(s.strip()) > 0)):
            html.append(s)
    return html

# todo - look for site info in the soup
def get_images_from_source(soup, url):
    sources = ['src', 'srcset', 'data-src']
    images = []
    img_tags = soup.find_all('img')
    if url:
        site = get_host_name(url)
        prot = url.split(':')[0]

    urls = []
    for img in img_tags:
        for src in sources:
            try:
                urls.append(img[src])
            except KeyError:
                pass

    for u in urls:
        u = u.split('?')[0]
        filename = re.search(r'/([\w_-]+[.](jpg|jpeg|gif|png))$', u)
        if filename:
            if (('http' not in u) and (url)):
                # sometimes an image source can be relative
                # if it is provide the base url
                u = '{}://{}{}'.format(prot, site, u)
            if 'http' in u:
                images.append(u)
    return images

def remove_graph(el):
    # recipes type might be wrapped in @graph type
    if isinstance(el, Tag):
        try:
            el = json.loads(el.string)
        except TypeError:
            pass
    if '@graph' in el:
        for x in el['@graph']:
            if '@type' in x and x['@type'] == 'Recipe':
                el = x
    return el