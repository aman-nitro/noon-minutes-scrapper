import asyncio
import json

from scrappers.product import NoonProductScraper


async def main():

    async with NoonProductScraper() as scraper:
        results = await scraper.scrape_tag("")

        print(results)

       


if __name__ == "__main__":
    asyncio.run(main())