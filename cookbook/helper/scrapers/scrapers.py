from bs4 import BeautifulSoup
from recipe_scrapers import SCRAPERS, get_domain, _exception_handling
from recipe_scrapers._factory import SchemaScraperFactory
from recipe_scrapers._schemaorg import SchemaOrg

from .cooksillustrated import CooksIllustrated

CUSTOM_SCRAPERS = {
    CooksIllustrated.host(): CooksIllustrated,
}

SCRAPERS = SCRAPERS.update(CUSTOM_SCRAPERS)
#%%
def text_scraper(text, url=None):
    domain = None
    if url:
        domain = get_domain(url)
    if domain in SCRAPERS:
        scraper_class = SCRAPERS[domain]
    else:
        scraper_class = SchemaScraperFactory.SchemaScraper
    
    class TextScraper(scraper_class):
        def __init__(
            self,
            page_data,
            url=None
        ):
            self.wild_mode = False
            self.exception_handling = _exception_handling
            self.meta_http_equiv = False
            self.soup = BeautifulSoup(page_data, "html.parser")
            self.url = url
            try:
                self.schema = SchemaOrg(page_data)
            except JSONDecodeError:
                pass

    return TextScraper(text, url)

# %%
