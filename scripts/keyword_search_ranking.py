import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiofiles
from loguru import logger

# Add root directory to python pathing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.noon_session import NoonMinutesSession
from proxy.proxy_manager import get_global_manager

# ───────────────────────── CONFIG ─────────────────────────

BASE_SEARCH_URL = "https://minutes.noon.com/_svc/catalog/search"

OUTPUT_DIR = "keyword_rankings_minutes"
RESULTS_FILE = os.path.join(OUTPUT_DIR, "rankings.jsonl")


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


# ───────────────────────── SEARCH EXECUTOR ─────────────────────────

async def search_keyword(keyword: str, page: int = 1, limit: int = 50, retries: int = 3) -> Optional[Dict]:
    params = {
        "q": keyword,
        "page": page,
        "limit": limit,
    }
    logger.debug(f"[SEARCH] Indexing catalog targets for keyword='{keyword}' │ page={page}")

    for attempt in range(1, retries + 1):
        try:
            async with NoonMinutesSession() as session:
                r = await session.get(BASE_SEARCH_URL, params=params)
                if r.status_code == 200:
                    return r.json()
                else:
                    logger.warning(
                        f"Attempt {attempt}/{retries} for keyword '{keyword}' page {page} returned status {r.status_code}"
                    )
        except Exception as e:
            logger.warning(
                f"Attempt {attempt}/{retries} for keyword '{keyword}' page {page} raised exception: {e}"
            )
        
        # Exponential backoff
        await asyncio.sleep(2.0 * attempt)
        
    return None


# ───────────────────────── PARSER & EXTRACTION ─────────────────────────

def extract_rankings(keyword: str, search_data: Dict, page: int = 1) -> List[Dict]:
    rankings = []
    
    # Extract products using robust strategy (direct products list or inside data list)
    page_products = []
    results = search_data.get("results", []) or []
    for r in results:
        modules = r.get("modules", []) or []
        for m in modules:
            # Pattern 1: products directly inside 'products' list of the module
            products_list = m.get("products")
            if isinstance(products_list, list):
                for p in products_list:
                    if isinstance(p, dict) and "sku" in p:
                        page_products.append(p)
            
            # Pattern 2: products inside 'data' list of the module
            items = m.get("data")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    p = item.get("product")
                    if isinstance(p, dict) and "sku" in p:
                        page_products.append(p)
                    elif "sku" in item:
                        page_products.append(item)

    limit = search_data.get("search", {}).get("rows") or 50

    for idx, product in enumerate(page_products, start=1):
        global_rank = ((page - 1) * limit) + idx

        rank_data = {
            "timestamp": datetime.now().isoformat(),
            "keyword": keyword,
            "page": page,
            "position_on_page": idx,
            "global_rank": global_rank,
            "product_id": product.get("sku"),
            "product_name": product.get("title") or product.get("name"), 
            "product_sku": product.get("sku"),
            "brand": product.get("brand") or product.get("brandCode"),
            "price": product.get("offerPrice") or product.get("price"),
            "original_price": product.get("strikedPrice") or product.get("price"),
            "discount_percent": product.get("discountPercent"),
            "rating": product.get("rating"),
            "review_count": product.get("reviewCount"),
            "in_stock": product.get("isBuyable") or product.get("is_buyable", True),
            "url": f"https://minutes.noon.com/uae-en/product/{product.get('sku')}" if product.get("sku") else None,
        }
        rankings.append(rank_data)

    return rankings


async def save_ranking(rank_data: Dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    async with aiofiles.open(RESULTS_FILE, "a", encoding="utf-8") as f:
        await f.write(json.dumps(rank_data, ensure_ascii=False) + "\n")


def print_rankings_summary(keyword: str, rankings: List[Dict], total_hits: int, total_pages: int) -> None:
    print(f"\n{'=' * 80}")
    print(f"SEARCH RANKING MATRIX (MINUTES): {keyword.upper()}")
    print(f"{'=' * 80}")
    print(f"Total Hits: {total_hits:,} │ Total Pages: {total_pages} │ Tracked: {len(rankings)}")
    print(f"{'-' * 80}")
    print(f"{'Rank':<6} {'Brand':<20} {'Product Name':<35} {'Price'}")
    print(f"{'-' * 80}")

    for rank in rankings[:10]:
        name = rank["product_name"][:32] if rank.get("product_name") else "N/A"
        brand = rank["brand"][:17] if rank.get("brand") else "N/A"
        price = f"AED {rank['price']}" if rank.get("price") else "N/A"
        print(f"{rank['global_rank']:<6} {brand:<20} {name:<35} {price}")
    print(f"{'=' * 80}\n")


# ───────────────────────── MAIN ENGINE RUNNER ─────────────────────────

async def main():
    logger.info("Initializing stable sequential HTTP/1.1 keyword tracking engine for Minutes...")
    
    # Initialize fallback proxies before entering session context
    init_fallback_proxies()

    keywords = ["banana", "milk", "bread"]

    for keyword in keywords:
        search_data = await search_keyword(keyword=keyword, page=1)
        if not search_data:
            logger.error(f"Timeline indexing skipped for vector: '{keyword}' due to connection drops.")
            continue

        total_hits = (
            search_data.get("nbHits") or 
            0
        )
        total_pages = search_data.get("nbPages") or 1

        rankings = extract_rankings(keyword=keyword, search_data=search_data, page=1)
        
        for rank in rankings:
            await save_ranking(rank)

        print_rankings_summary(keyword, rankings, total_hits, total_pages)
        
        # Human mimic pacing delay between targets
        sleep_duration = random.uniform(2.5, 4.0)
        logger.info(f"Target vector complete. Pacing channel sleeping for {sleep_duration:.2f}s...")
        await asyncio.sleep(sleep_duration)

    logger.success(f"Tracking run complete! Data mapped into JSON Lines directly -> {RESULTS_FILE}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[RUN INTERRUPTED]")