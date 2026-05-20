from loguru import logger

from core.noon_session import NoonMinutesSession
from constants.noon import NOON_BASE_URL

PAGE_LIMIT = 100


class NoonCategoryScraper:

    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = NoonMinutesSession()
        await self.session.start()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def get_category_request(self)-> dict | None:
        url = f"{NOON_BASE_URL}/_svc/catalog/slider-navigation/default_category_slider_ae"
        try:
            logger.info(f"[INFO] Fetching category data from {url}")
            r = await self.session.get(url)
            return r.json()

        except Exception as e:
            logger.error(f"[ERROR] {e}")
            return None
    
    async def fetch_all_category(self):
        categories =  await self.get_category_request()
        links = []

        for category in categories.get("groups", []):
            items = category.get("items", [])
            for item in items:
                links.append(item.get("link"))
        
        return links


    
