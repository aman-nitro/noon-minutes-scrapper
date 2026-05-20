#It is not as simple as noon, we will be needing to do this with the help of selenium and a headless browser, as the search results are rendered client side and the API is not stable enough to be scraped directly. This script will be used to fetch the search results for a list of keywords and save them in a JSON file.
import asyncio
import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiofiles
import requests  # Clean HTTP/1.1 connection pipeline
from loguru import logger

# ───────────────────────── CONFIG ─────────────────────────

BASE_SEARCH_URL = "https://minutes.noon.com/_svc/catalog/search"

OUTPUT_DIR = "keyword_rankings_minutes"
RESULTS_FILE = os.path.join(OUTPUT_DIR, "rankings.jsonl")

# Minutes-specific headers
HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'baggage': 'sentry-environment=production,sentry-release=mx-minutes-marketplace%402.26.0,sentry-public_key=225f4e76bf877875d48c1e162e8b8c89,sentry-trace_id=58c82021c0eb45e1b53ef8b765920fc4,sentry-sampled=true,sentry-sample_rand=0.08294159900802667,sentry-sample_rate=0.1',
    'cache-control': 'no-cache, max-age=0, must-revalidate, no-store',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://minutes.noon.com/uae-en/',
    'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    'x-border-enabled': 'true',
    'x-cms': 'v2',
    'x-ecom-zonecode': 'AE_DXB-S3',
    'x-experience': 'nooninstant',
    'x-lat': '252174001',
    'x-lng': '552798481',
    'x-locale': 'en-ae',
    'x-mp': 'nooninstant',
    'x-mp-country': 'ae',
    'x-nooninstant-zonecode': 'W00091092A',
    'x-platform': 'mweb',
    'x-rocket-enabled': 'true',
    'x-visitor-id': '4d8ab649-b3c2-43a3-be65-589b50966789',
}

# ───────────────────────── SEARCH EXECUTOR ─────────────────────────

def run_sync_request(params: dict) -> Optional[dict]:
    """Runs a standard sequential HTTP/1.1 request via requests inside a thread worker."""
    try:
        response = requests.get(
            url=BASE_SEARCH_URL,
            headers=HEADERS,
            params=params,
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        logger.warning(f"[HTTP {response.status_code}] Dropped by backend validation.")
        return None
    except Exception as e:
        logger.error(f"[REQUEST EXCEPTION] Thread worker pipeline failed -> {e}")
        return None

async def search_keyword(keyword: str, page: int = 1, limit: int = 50) -> Optional[Dict]:
    params = {
        "q": keyword,
        "page": page,
        "limit": limit,
    }
    logger.debug(f"[SEARCH] Indexing catalog targets for keyword='{keyword}' │ page={page}")
    
    return await asyncio.to_thread(run_sync_request, params)

# ───────────────────────── PARSER & EXTRACTION ─────────────────────────

def extract_rankings(keyword: str, search_data: Dict, page: int = 1) -> List[Dict]:
    rankings = []
    
    # Minutes uses "products" instead of "hits"
    hits = search_data.get("products", []) or search_data.get("hits", [])

    for idx, product in enumerate(hits, start=1):
        global_rank = ((page - 1) * 50) + idx

        rank_data = {
            "timestamp": datetime.now().isoformat(),
            "keyword": keyword,
            "page": page,
            "position_on_page": idx,
            "global_rank": global_rank,
            "product_id": product.get("id") or product.get("sku"),
            "product_name": product.get("title") or product.get("name"), 
            "product_sku": product.get("sku"),
            "brand": product.get("brand") or product.get("brand_name"),
            "price": product.get("price") or product.get("offer_price"),
            "original_price": product.get("original_price") or product.get("was_price"),
            "discount_percent": product.get("discount_percent") or product.get("discount"),
            "rating": product.get("rating") or product.get("average_rating"),
            "review_count": product.get("review_count") or product.get("number_of_reviews"),
            "in_stock": product.get("is_in_stock") or product.get("in_stock") or product.get("is_available"),
            "url": product.get("url") or product.get("slug"),
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
    keywords = ["banana", "milk", "bread"]

    for keyword in keywords:
        search_data = await search_keyword(keyword=keyword, page=1)
        if not search_data:
            logger.error(f"Timeline indexing skipped for vector: '{keyword}' due to connection drops.")
            continue

        # Minutes API uses different field names
        total_hits = (
            search_data.get("nbHits") or 
            search_data.get("total_products") or 
            search_data.get("totalProducts") or 
            len(search_data.get("products", [])) or 
            0
        )
        total_pages = search_data.get("nbPages") or search_data.get("totalPages") or 1

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