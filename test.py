import asyncio
import json

from scrappers.product import NoonProductScraper


async def main():

    async with NoonProductScraper() as scraper:
        results = await scraper.scrape_tag("")

        print(results)

        # with open("output/results.json", "w") as f:
        #     json.dump(results, f, indent=4)


if __name__ == "__main__":
    asyncio.run(main())