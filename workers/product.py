import asyncio
from loguru import logger

from scrappers.product import NoonMinutesProductScraper
from controllers.category import NoonCategoryController
from controllers.product import NoonProductController
from controllers.brand import NoonBrandController

from utils.db import SessionLocal

BATCH_SIZE = 1000


def scrape_noon_products():
    logger.info("Product scraping started...")
    asyncio.run(run_product_scraper())


async def run_product_scraper():
    async with SessionLocal() as db:
        categories = await NoonCategoryController.get_all(db=db)
        logger.info(f"Total categories fetched: {len(categories)}")

        for category in categories:
            logger.info(f"Scraping category: {category.subCategoryName}")

            try:
                products = []   
                brands = []
                async with NoonMinutesProductScraper() as product_scraper:
                    products, brands = await product_scraper.scrape(category=category.subCategoryName)
                
                if not products:
                    logger.warning(f"No products found for category: {category.subCategoryName}")
                    continue

                logger.info(f"Fetched {len(brands)} brands")
                logger.info(f"Fetched {len(products)} products")

                for brand in brands:
                    try:
                        await NoonBrandController.create(db, name=brand)
                    except Exception as err:
                        logger.exception(f"Error saving brand: {err}")

                for product in products:
                    try:
                        merchant_name = product.get("store_name", "sample")
                        product_data = {
                            "name": product.get("title"),
                            "brandId": product.get('brand'),
                            "sku": product.get("sku"),
                            "product_url": product.get("url", ""),
                            "imageUrl": product.get("transparent_image_url"),
                            "price": product.get("price") or 0,
                            "inventory": product.get("maxQty") or 0,
                            "categoryId": category.categoryId,
                            "subCategoryId": category.subCategoryId,
                            "merchant_name": merchant_name or "",
                        }

                        await NoonProductController.upsert(db, **product_data)

                    except Exception as err:
                        logger.exception(f"Error processing product: {err}")
            

            except Exception as err:
                logger.exception(f"Error scraping category: {err}")
            
            await db.commit()

