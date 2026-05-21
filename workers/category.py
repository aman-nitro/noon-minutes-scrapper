import asyncio
from loguru import logger

import utils.dramatiq
from scrappers.category import NoonCategoryScraper
from controllers.category import NoonCategoryController
from utils.db import SessionLocal


# @dramatiq.actor(max_retries=3)
def scrape_noon_categories():
    logger.info("Brand scrapping is started....")
    asyncio.run(run_category_scraper())


async def run_category_scraper():
    categories = []
    async with NoonCategoryScraper() as scraper:
        categories  = await scraper.scrape()

    if not categories:
        logger.error("No categories found to save in the database.")
        return categories

    logger.info(f"Total categ fetched are: {len(categories)}")
    db = SessionLocal()

    for cat in categories:
        try:
            record = {
                "categoryId": cat.get('category'),
                "categoryName": cat.get('category_name'),
                "subCategoryId": cat.get('sub_category'),
                "subCategoryName": cat.get('sub_category_name')
            }
            await NoonCategoryController.create(db=db, **record)

        except Exception as err:
            logger.exception(f'Error occurred while creating entry in database: {err}')

    logger.info(f"Categories saved in the database!!")