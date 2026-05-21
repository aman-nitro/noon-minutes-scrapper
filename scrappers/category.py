from loguru import logger

from core.noon_session import NoonMinutesSession
from constants.noon import NOON_BASE_URL


class NoonCategoryScraper:
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = NoonMinutesSession()
        await self.session.start()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def fetch_all_category(self)-> dict | None:
        url = f"{NOON_BASE_URL}/_svc/catalog/slider-navigation/default_category_slider_ae"

        try:
            logger.info(f"[INFO] Fetching category data from {url}")
            r = await self.session.get(url)
            return r.json()

        except Exception as e:
            logger.error(f"[ERROR] {e}")
            return None
    
    async def scrape(self):
        categories =  await self.fetch_all_category()
        links = []

        if not categories:
            logger.error("Failed to fetch categories.")
            return links

        for category in categories.get("groups", []):
            parent_category = category.get('code')
            title = category.get('title')
            items = category.get("items", [])

            for item in items:
                links.append({
                    "category": parent_category,
                    "category_name": title,
                    "sub_category": item.get('code'),
                    "sub_category_name": item.get("link")
                })
        
        return links


    
