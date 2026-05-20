import asyncio
from loguru import logger

from core.noon_session import NoonMinutesSession
from constants.noon import NOON_BASE_URL

PAGE_LIMIT = 100


class NoonProductScraper:

    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = NoonMinutesSession()
        await self.session.start()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def fetch_page(self, tag: str, page: int = 1) -> dict | None:
        url = f"{NOON_BASE_URL}/_svc/catalog/search"
        params = {
            # "f[tag]": tag,
            "limit": PAGE_LIMIT,
            "page": page,
        }

        try:
            r = await self.session.get(url, params=params)
            print(f"Fetched page {page} status={r.status_code}")
            if r.status_code == 200:
                return r.json()

            logger.warning(f"[HTTP {r.status_code}] page={page}")
            return None

        except Exception as e:
            logger.error(f"[ERROR] {e}")
            return None

    async def scrape_tag(self, tag: str=None) -> list[dict]:
        page = 1

        while True:
            print('scrap tag')
            first = await self.fetch_page(tag, page)
            page += 1

            if not first:
                break
        return first