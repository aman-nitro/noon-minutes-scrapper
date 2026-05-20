import asyncio
import json
import os
import sys
import argparse
from loguru import logger

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.noon_session import NoonMinutesSession
from proxy.proxy_manager import get_global_manager

SEARCH_URL = "https://minutes.noon.com/_svc/catalog/search"


def init_fallback_proxies():
    """Ensure the global proxy manager has proxies loaded from proxy/proxies.py."""
    pm = get_global_manager()
    status = pm.get_status()
    if status.get("total_proxies", 0) == 0:
        logger.info("No proxies loaded in global manager, attempting fallback from proxy/proxies.py...")
        try:
            from proxy.proxies import proxy_urls
            total_proxies = []
            for values in proxy_urls.values():
                if values:
                    total_proxies.extend(values)
            loaded = pm.load_proxies_from_url_list(total_proxies)
            logger.info(f"Successfully loaded {loaded} fallback proxies.")
        except Exception as e:
            logger.error(f"Failed to load fallback proxies: {e}")
    else:
        logger.info(f"Global proxy manager already has {status['total_proxies']} proxies loaded.")


def extract_products_and_brands(data: dict):
    """
    Extract products and brands from the response JSON structure.
    Tolerates changes in modules types by checking for 'product' in all data objects or direct 'products' lists.
    """
    page_products = []
    page_brands = {}

    results = data.get("results", []) or []
    for r in results:
        modules = r.get("modules", []) or []
        for m in modules:
            # Pattern 1: products directly inside 'products' list of the module
            products_list = m.get("products")
            if isinstance(products_list, list):
                for p in products_list:
                    if isinstance(p, dict) and "sku" in p:
                        page_products.append(p)
                        brand_name = p.get("brand")
                        brand_code = p.get("brandCode") or p.get("brand_code")
                        if brand_name:
                            page_brands[brand_name] = {
                                "name": brand_name,
                                "code": brand_code
                            }
            
            # Pattern 2: products inside 'data' list of the module
            items = m.get("data")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    p = item.get("product")
                    if isinstance(p, dict) and "sku" in p:
                        page_products.append(p)
                        brand_name = p.get("brand")
                        brand_code = p.get("brandCode") or p.get("brand_code")
                        
                        if brand_name:
                            page_brands[brand_name] = {
                                "name": brand_name,
                                "code": brand_code
                            }
                    elif "sku" in item:
                        # Sometimes the item itself is the product
                        page_products.append(item)
                        brand_name = item.get("brand")
                        brand_code = item.get("brandCode") or item.get("brand_code")
                        if brand_name:
                            page_brands[brand_name] = {
                                "name": brand_name,
                                "code": brand_code
                            }
    return page_products, page_brands


async def fetch_page_with_retry(category: str, page: int, retries: int = 3) -> dict | None:
    """Fetch a search page using NoonMinutesSession with retry logic and proxy rotation on failure."""
    params = {
        "f[category]": category,
        "page": page
    }

    for attempt in range(1, retries + 1):
        try:
            async with NoonMinutesSession() as session:
                r = await session.get(SEARCH_URL, params=params)
                if r.status_code == 200:
                    return r.json()
                else:
                    logger.warning(
                        f"Attempt {attempt}/{retries} for page {page} returned status {r.status_code}"
                    )
        except Exception as e:
            logger.warning(
                f"Attempt {attempt}/{retries} for page {page} raised exception: {e}"
            )
        
        # Exponential backoff
        await asyncio.sleep(2.0 * attempt)

    return None


async def scrape_category(category: str, output_dir: str):
    """Fetch all products and brands for the given category page by page."""
    logger.info(f"Starting crawl for category: {category}")
    
    # Initialize fallback proxies before entering any session context
    init_fallback_proxies()

    # Fetch first page to find pagination details
    first_page = await fetch_page_with_retry(category, 1)
    if not first_page:
        logger.error("Failed to fetch page 1. Aborting category crawl.")
        return

    nb_pages = first_page.get("nbPages", 1)
    nb_hits = first_page.get("nbHits", 0)
    logger.info(f"Discovered {nb_hits} total hits across {nb_pages} pages.")

    all_products = []
    all_brands = {}

    # Process page 1
    p_list, b_dict = extract_products_and_brands(first_page)
    all_products.extend(p_list)
    all_brands.update(b_dict)
    logger.info(f"Page 1/{nb_pages}: Extracted {len(p_list)} products.")

    # Fetch remaining pages
    for page in range(2, nb_pages + 1):
        # Polite spacing between requests
        await asyncio.sleep(1.0)
        
        page_data = await fetch_page_with_retry(category, page)
        if not page_data:
            logger.error(f"Skipping page {page} due to persistent fetch failures.")
            continue

        p_list, b_dict = extract_products_and_brands(page_data)
        all_products.extend(p_list)
        all_brands.update(b_dict)
        logger.info(f"Page {page}/{nb_pages}: Extracted {len(p_list)} products. (Total products: {len(all_products)})")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save outputs
    products_file = os.path.join(output_dir, f"noon_minutes_products_{category}.json")
    brands_file = os.path.join(output_dir, f"noon_minutes_brands_{category}.json")

    with open(products_file, "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)

    # Save brands as list of unique objects
    unique_brands_list = list(all_brands.values())
    with open(brands_file, "w", encoding="utf-8") as f:
        json.dump(unique_brands_list, f, indent=2, ensure_ascii=False)

    logger.info("══════════════════════════════")
    logger.info("CRAWL SUMMARY (MINUTES)")
    logger.info(f"Category: {category}")
    logger.info(f"Total Pages Crawled: {nb_pages}")
    logger.info(f"Total Products Saved: {len(all_products)} -> {products_file}")
    logger.info(f"Total Brands Saved: {len(unique_brands_list)} -> {brands_file}")
    logger.info("══════════════════════════════")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch products and brands from Noon Minutes search service.")
    parser.add_argument(
        "--category",
        type=str,
        default="water_ice",
        help="Category code to search (default: water_ice)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save output files (default: output)"
    )
    args = parser.parse_args()

    try:
        asyncio.run(scrape_category(args.category, args.output_dir))
    except KeyboardInterrupt:
        logger.warning("Crawl interrupted by user.")
