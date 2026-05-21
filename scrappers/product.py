import asyncio

from loguru import logger
from core.noon_session import NoonMinutesSession, BASE_URL

CATALOG_URL = f"{BASE_URL}/_svc/catalog"


class NoonMinutesProductScraper:
    def __init__(self):
        self.session: NoonMinutesSession | None = None

    async def __aenter__(self):
        self.session = NoonMinutesSession()
        await self.session.start()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def fetch_page(self, category: str, page: int) -> dict | None:
        url = f"{CATALOG_URL}{category}"
        try:
            r = await self.session.get(url, params={"page": page})
            logger.info(f"[page {page}] {r.status_code}")
            if r.status_code == 200:
                return r.json()
            
            logger.warning(f"[page {page}] non-200: {r.text[:200]}")
        except Exception as e:
            logger.error(f"[page {page}] error: {e}")
        return None

    def _parse_page(self, data: dict) -> tuple[list[dict], dict[str, dict]]:
        products: list[dict] = []
        brands: dict[str, dict] = {}

        for result in data.get("results", []):
            for module in result.get("modules", []):

                for product in module.get("products") or []:
                    if isinstance(product, dict) and "sku" in product:
                        products.append(product)
                        self._collect_brand(product, brands)

                for item in module.get("data") or []:
                    if not isinstance(item, dict):
                        continue
                    nested = item.get("product")
                    if isinstance(nested, dict) and "sku" in nested:
                        products.append(nested)
                        self._collect_brand(nested, brands)
                    elif "sku" in item:
                        products.append(item)
                        self._collect_brand(item, brands)

        return products, brands

    def _collect_brand(self, product: dict, brands: dict):
        name = product.get("brand")
        if name:
            brands[name] = {
                "name": name,
                "code": product.get("brandCode") or product.get("brand_code"),
            }

    @staticmethod
    def _is_valid_category(category: str) -> bool:
        if not category:
            return False
        if not category.startswith("/"):
            logger.warning(f"[scrape] Skipping invalid category path: {category!r}")
            return False
        return True

    async def scrape(self, category: str) -> tuple[list[dict], dict[str, dict]]:
        empty: tuple[list[dict], dict[str, dict]] = ([], {})

        if not self._is_valid_category(category):
            return empty

        logger.info(f"Starting scrape → {category}")

        all_products: list[dict] = []
        all_brands: dict[str, dict] = {}

        first = await self.fetch_page(category, 1)
        if not first:
            logger.error("Could not fetch page 1. Stopping.")
            return empty

        total_pages = first.get("nbPages", 1)
        total_hits  = first.get("nbHits", 0)
        logger.info(f"Total: {total_hits} products across {total_pages} pages")

        products, brands = self._parse_page(first)
        all_products.extend(products)
        all_brands.update(brands)
        logger.info(f"Page 1/{total_pages}: {len(products)} products (running total: {len(all_products)})")

        for page in range(2, total_pages + 1):
            await asyncio.sleep(0.5)
            data = await self.fetch_page(category, page)
            if not data:
                logger.warning(f"Skipping page {page} — fetch failed")
                continue
            products, brands = self._parse_page(data)
            all_products.extend(products)
            all_brands.update(brands)
            logger.info(f"Page {page}/{total_pages}: {len(products)} products (running total: {len(all_products)})")

        logger.success(f"Done. {len(all_products)} products, {len(all_brands)} brands collected.")
        return all_products, all_brands