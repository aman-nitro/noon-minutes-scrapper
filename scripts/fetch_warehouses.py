import asyncio
import json
import os
import sys
import time
import uuid
from typing import Dict, List, Optional

from loguru import logger
from curl_cffi.requests import AsyncSession

# Fix system pathing
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/..")

from proxy.proxy_manager import ProxyManager, ProxyConfig
from proxy.proxy_client import ProxyClient
from proxy.proxies import proxy_urls 

# ============================================================
# CONFIG
# ============================================================

OUTPUT_FILE = "minutes_warehouses.json"
MAX_CONCURRENT = 15  # Low concurrency ensures Akamai doesn't trigger bot protection

GEO_URL = "https://minutes.noon.com/_svc/mp-identity-api/serviceable-geo-info/by-location"
SET_LOCATION_URL = "https://minutes.noon.com/_svc/mp-identity-api/address/set-location"
WHOAMI_URL = "https://minutes.noon.com/_vs/st/st-whoami-api-web/whoami"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://minutes.noon.com",
    "referer": "https://minutes.noon.com/uae-en/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "x-platform": "web",
    "x-locale": "en-ae",
    "x-mp-country": "ae",
    "x-mp": "nooninstant",
    "x-experience": "nooninstant",
    "x-cms": "v2",
    "x-border-enabled": "true",
    "cache-control": "no-cache, max-age=0, must-revalidate, no-store",
}

# Targeted residential corridors
URBAN_BOXES = [
    # UAE Residential / Mixed-Residential Coverage Rectangles
# Includes:
# - dense apartments
# - villa communities
# - suburban developments
# - remote inhabited clusters
# - industrial-residential worker zones
# - emerging developments
# - even sparsely populated inhabited areas

    # =========================================================
    # OLD DUBAI
    # =========================================================

    {
        "name": "Deira",
        "min_lat": 25.245,
        "max_lat": 25.290,
        "min_lng": 55.300,
        "max_lng": 55.360
    },

    {
        "name": "Bur Dubai - Karama",
        "min_lat": 25.235,
        "max_lat": 25.270,
        "min_lng": 55.270,
        "max_lng": 55.320
    },

    {
        "name": "Oud Metha",
        "min_lat": 25.225,
        "max_lat": 25.255,
        "min_lng": 55.300,
        "max_lng": 55.340
    },

    {
        "name": "Al Jaddaf",
        "min_lat": 25.210,
        "max_lat": 25.240,
        "min_lng": 55.320,
        "max_lng": 55.360
    },

    # =========================================================
    # COASTAL / CENTRAL DUBAI
    # =========================================================

    {
        "name": "Downtown - Business Bay",
        "min_lat": 25.170,
        "max_lat": 25.220,
        "min_lng": 55.250,
        "max_lng": 55.320
    },

    {
        "name": "City Walk",
        "min_lat": 25.195,
        "max_lat": 25.215,
        "min_lng": 55.255,
        "max_lng": 55.285
    },

    {
        "name": "Jumeirah 1-2-3",
        "min_lat": 25.180,
        "max_lat": 25.250,
        "min_lng": 55.210,
        "max_lng": 55.270
    },

    {
        "name": "Umm Suqeim",
        "min_lat": 25.140,
        "max_lat": 25.190,
        "min_lng": 55.210,
        "max_lng": 55.260
    },

    {
        "name": "Al Safa",
        "min_lat": 25.160,
        "max_lat": 25.210,
        "min_lng": 55.230,
        "max_lng": 55.280
    },

    # =========================================================
    # MARINA CORRIDOR
    # =========================================================

    {
        "name": "Dubai Marina",
        "min_lat": 25.065,
        "max_lat": 25.095,
        "min_lng": 55.120,
        "max_lng": 55.160
    },

    {
        "name": "JBR",
        "min_lat": 25.070,
        "max_lat": 25.095,
        "min_lng": 55.130,
        "max_lng": 55.155
    },

    {
        "name": "JLT",
        "min_lat": 25.060,
        "max_lat": 25.090,
        "min_lng": 55.160,
        "max_lng": 55.190
    },

    {
        "name": "Bluewaters Island",
        "min_lat": 25.075,
        "max_lat": 25.095,
        "min_lng": 55.115,
        "max_lng": 55.135
    },

    {
        "name": "Palm Jumeirah",
        "min_lat": 25.095,
        "max_lat": 25.145,
        "min_lng": 55.120,
        "max_lng": 55.170
    },

    {
        "name": "Discovery Gardens",
        "min_lat": 25.020,
        "max_lat": 25.060,
        "min_lng": 55.150,
        "max_lng": 55.200
    },

    {
        "name": "The Gardens",
        "min_lat": 25.030,
        "max_lat": 25.055,
        "min_lng": 55.140,
        "max_lng": 55.180
    },

    # =========================================================
    # WESTERN SUBURBS
    # =========================================================

    {
        "name": "JVC",
        "min_lat": 25.040,
        "max_lat": 25.090,
        "min_lng": 55.190,
        "max_lng": 55.260
    },

    {
        "name": "JVT",
        "min_lat": 25.030,
        "max_lat": 25.070,
        "min_lng": 55.180,
        "max_lng": 55.240
    },

    {
        "name": "Springs",
        "min_lat": 25.040,
        "max_lat": 25.070,
        "min_lng": 55.160,
        "max_lng": 55.210
    },

    {
        "name": "Meadows",
        "min_lat": 25.045,
        "max_lat": 25.075,
        "min_lng": 55.150,
        "max_lng": 55.200
    },

    {
        "name": "Emirates Hills",
        "min_lat": 25.060,
        "max_lat": 25.085,
        "min_lng": 55.150,
        "max_lng": 55.190
    },

    {
        "name": "Arabian Ranches",
        "min_lat": 25.010,
        "max_lat": 25.070,
        "min_lng": 55.250,
        "max_lng": 55.330
    },

    {
        "name": "Damac Hills",
        "min_lat": 24.990,
        "max_lat": 25.050,
        "min_lng": 55.240,
        "max_lng": 55.310
    },

    {
        "name": "Town Square",
        "min_lat": 24.980,
        "max_lat": 25.030,
        "min_lng": 55.300,
        "max_lng": 55.360
    },

    # =========================================================
    # CENTRAL INLAND DUBAI
    # =========================================================

    {
        "name": "Al Barsha",
        "min_lat": 25.080,
        "max_lat": 25.140,
        "min_lng": 55.180,
        "max_lng": 55.260
    },

    {
        "name": "Arjan",
        "min_lat": 25.030,
        "max_lat": 25.070,
        "min_lng": 55.240,
        "max_lng": 55.300
    },

    {
        "name": "Motor City",
        "min_lat": 25.030,
        "max_lat": 25.070,
        "min_lng": 55.250,
        "max_lng": 55.310
    },

    {
        "name": "Dubai Sports City",
        "min_lat": 25.030,
        "max_lat": 25.065,
        "min_lng": 55.210,
        "max_lng": 55.270
    },

    {
        "name": "Dubai Hills",
        "min_lat": 25.090,
        "max_lat": 25.140,
        "min_lng": 55.220,
        "max_lng": 55.290
    },

    # =========================================================
    # EASTERN DUBAI
    # =========================================================

    {
        "name": "Mirdif",
        "min_lat": 25.200,
        "max_lat": 25.260,
        "min_lng": 55.390,
        "max_lng": 55.460
    },

    {
        "name": "Al Warqa",
        "min_lat": 25.150,
        "max_lat": 25.230,
        "min_lng": 55.380,
        "max_lng": 55.500
    },

    {
        "name": "International City",
        "min_lat": 25.140,
        "max_lat": 25.190,
        "min_lng": 55.380,
        "max_lng": 55.460
    },

    {
        "name": "Warsan",
        "min_lat": 25.140,
        "max_lat": 25.220,
        "min_lng": 55.420,
        "max_lng": 55.520
    },

    {
        "name": "Dubai Silicon Oasis",
        "min_lat": 25.100,
        "max_lat": 25.160,
        "min_lng": 55.360,
        "max_lng": 55.430
    },

    {
        "name": "Liwan",
        "min_lat": 25.090,
        "max_lat": 25.130,
        "min_lng": 55.350,
        "max_lng": 55.400
    },

    {
        "name": "Academic City",
        "min_lat": 25.090,
        "max_lat": 25.160,
        "min_lng": 55.420,
        "max_lng": 55.500
    },

    {
        "name": "Muhaisnah",
        "min_lat": 25.240,
        "max_lat": 25.300,
        "min_lng": 55.390,
        "max_lng": 55.470
    },

    {
        "name": "Al Qusais",
        "min_lat": 25.250,
        "max_lat": 25.310,
        "min_lng": 55.350,
        "max_lng": 55.430
    },

    {
        "name": "Al Nahda Dubai",
        "min_lat": 25.270,
        "max_lat": 25.320,
        "min_lng": 55.350,
        "max_lng": 55.410
    },

    # =========================================================
    # SOUTH DUBAI
    # =========================================================

    {
        "name": "Dubai South",
        "min_lat": 24.850,
        "max_lat": 25.000,
        "min_lng": 55.100,
        "max_lng": 55.280
    },

    {
        "name": "Expo City",
        "min_lat": 24.930,
        "max_lat": 24.990,
        "min_lng": 55.120,
        "max_lng": 55.190
    },

    {
        "name": "Jebel Ali Village",
        "min_lat": 24.980,
        "max_lat": 25.040,
        "min_lng": 55.110,
        "max_lng": 55.170
    },

    # =========================================================
    # SHARJAH
    # =========================================================

    {
        "name": "Sharjah Central",
        "min_lat": 25.280,
        "max_lat": 25.380,
        "min_lng": 55.360,
        "max_lng": 55.460
    },

    {
        "name": "Al Nahda Sharjah",
        "min_lat": 25.290,
        "max_lat": 25.330,
        "min_lng": 55.370,
        "max_lng": 55.420
    },

    {
        "name": "Muwaileh",
        "min_lat": 25.290,
        "max_lat": 25.360,
        "min_lng": 55.450,
        "max_lng": 55.550
    },

    # =========================================================
    # AJMAN
    # =========================================================

    {
        "name": "Ajman Central",
        "min_lat": 25.360,
        "max_lat": 25.450,
        "min_lng": 55.420,
        "max_lng": 55.550
    },

    {
        "name": "Al Jurf Ajman",
        "min_lat": 25.380,
        "max_lat": 25.450,
        "min_lng": 55.470,
        "max_lng": 55.560
    },

    # =========================================================
    # ABU DHABI
    # =========================================================

    {
        "name": "Abu Dhabi Island",
        "min_lat": 24.420,
        "max_lat": 24.520,
        "min_lng": 54.320,
        "max_lng": 54.420
    },

    {
        "name": "Khalifa City",
        "min_lat": 24.390,
        "max_lat": 24.470,
        "min_lng": 54.520,
        "max_lng": 54.650
    },

    {
        "name": "Mohammed Bin Zayed City",
        "min_lat": 24.320,
        "max_lat": 24.390,
        "min_lng": 54.520,
        "max_lng": 54.620
    },

    {
        "name": "Al Reef",
        "min_lat": 24.480,
        "max_lat": 24.550,
        "min_lng": 54.600,
        "max_lng": 54.700
    },

    # =========================================================
    # AL AIN
    # =========================================================

    {
        "name": "Al Ain Central",
        "min_lat": 24.150,
        "max_lat": 24.250,
        "min_lng": 55.680,
        "max_lng": 55.820
    },
]


# ============================================================
# FETCH PIPELINE (Isolated Session Lifecycle)
# ============================================================

async def fetch_warehouse(client: ProxyClient, lat: float, lng: float) -> Optional[Dict]:
    owner_id = f"client-{uuid.uuid4().hex[:6]}"
    proxy = client.manager.reserve_proxy(owner_id)
    if not proxy:
        return None

    proxies_dict = client._get_proxies_dict(proxy)
    curl_opts = client._get_curl_resolve_options(proxy)

    try:
        # CRITICAL FIX: Every worker gets a completely isolated, locked session instance
        async with AsyncSession(
            impersonate="chrome120",
            timeout=30,
            curl_options=curl_opts
        ) as session:
            
            # STEP 1: Verify coordinate serviceability
            geo_response = await session.post(
                url=GEO_URL,
                json={"location": {"lat": lat, "lng": lng}},
                headers=HEADERS,
                proxies=proxies_dict
            )

            if geo_response.status_code != 200:
                client.manager.release_proxy(proxy.id)
                return None

            geo_data = geo_response.json()
            area_value = geo_data.get("area") or geo_data.get("placeName") or f"Lat:{lat}_Lng:{lng}"
            city_id_value = geo_data.get("cityId") or 1

            # STEP 2: Force location updates onto this specific, isolated cookie jar
            set_loc_payload = {
                "location": {"lat": lat, "lng": lng},
                "area": area_value,
                "cityId": city_id_value
            }

            set_loc_response = await session.post(
                url=SET_LOCATION_URL,
                json=set_loc_payload,
                headers=HEADERS,
                proxies=proxies_dict
            )

            if set_loc_response.status_code != 200:
                client.manager.release_proxy(proxy.id)
                return None

            # Small sleep mimics real user pacing so Noon doesn't flag the request sequence
            await asyncio.sleep(0.5)

            # STEP 3: Grab unique tracking warehouse codes from session context
            whoami_response = await session.get(
                url=WHOAMI_URL,
                headers=HEADERS,
                proxies=proxies_dict
            )

            if whoami_response.status_code != 200:
                client.manager.release_proxy(proxy.id)
                return None

            whoami_data = whoami_response.json()
            resp_headers = whoami_data.get("headers", {})
            
            # For minutes.noon.com, extract x-nooninstant-zonecode
            nooninstant_zone = resp_headers.get("x-nooninstant-zonecode")
            ecom_zone = resp_headers.get("x-ecom-zonecode")
            rocket_zone = resp_headers.get("x-rocket-zonecode")

            if isinstance(nooninstant_zone, list) and nooninstant_zone: 
                nooninstant_zone = nooninstant_zone[0]
            if isinstance(ecom_zone, list) and ecom_zone: 
                ecom_zone = ecom_zone[0]
            if isinstance(rocket_zone, list) and rocket_zone: 
                rocket_zone = rocket_zone[0]

            if not nooninstant_zone: 
                nooninstant_zone = whoami_response.headers.get("x-nooninstant-zonecode")
            if not ecom_zone: 
                ecom_zone = whoami_response.headers.get("x-ecom-zonecode")
            if not rocket_zone: 
                rocket_zone = whoami_response.headers.get("x-rocket-zonecode")

            # Primary zone for Minutes is nooninstant
            if not nooninstant_zone:
                client.manager.release_proxy(proxy.id)
                return None

            logger.success(f"[SUCCESS] Discovered Hub: {nooninstant_zone} -> {area_value}")
            client.manager.mark_success(proxy.id)
            
            return {
                "warehouse_key": nooninstant_zone,
                "nooninstant": nooninstant_zone,
                "ecom": ecom_zone if ecom_zone else None,
                "rocket": rocket_zone if rocket_zone else None,
                "area": area_value,
                "lat": lat,
                "lng": lng
            }

    except Exception:
        client.manager.release_proxy(proxy.id)
        return None

# ============================================================
# SEMAPHORE BOUND WORKER
# ============================================================

async def worker(semaphore: asyncio.Semaphore, client: ProxyClient, lat: float, lng: float) -> Optional[Dict]:
    async with semaphore:
        return await fetch_warehouse(client, lat, lng)

# ============================================================
# MAIN ENGINE
# ============================================================

async def main():
    logger.info("Initializing isolated-session warehouse scroller for Minutes...")
    started = time.time()

    config = ProxyConfig()
    proxy_manager = ProxyManager(config=config, platform="noon")
    
    raw_proxies = []
    for values in proxy_urls.values():
        if values: raw_proxies.extend(values)
    proxy_manager.load_proxies_from_url_list(raw_proxies)

    client = ProxyClient(config=config, proxy_manager=proxy_manager)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # 5km increments balances speed and coverage density
    step = 0.05
    tasks = []

    for box in URBAN_BOXES:
        curr_lat = box["min_lat"]
        while curr_lat <= box["max_lat"]:
            curr_lng = box["min_lng"]
            while curr_lng <= box["max_lng"]:
                tasks.append(
                    asyncio.create_task(
                        worker(semaphore, client, round(curr_lat, 4), round(curr_lng, 4))
                    )
                )
                curr_lng += step
            curr_lat += step

    logger.info(f"Loaded {len(tasks)} coordinates into safe loop runner.")

    # Execute and wait for results array
    raw_results = await asyncio.gather(*tasks)
    elapsed = time.time() - started

    # Deduplicate matching keys cleanly
    final_dictionary_map = {}
    for item in raw_results:
        if item and "warehouse_key" in item:
            w_key = item["warehouse_key"]
            final_dictionary_map[w_key] = item

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_dictionary_map, f, indent=4)

    await client.close_all_sessions()

    logger.info("══════════════════════════════")
    logger.info("WAREHOUSE SCROLLER COMPLETE (MINUTES)")
    logger.info(f"Total Grid Nodes Checked={len(tasks)}")
    logger.info(f"Unique Active Warehouses Extracted={len(final_dictionary_map)}")
    logger.info(f"Saved directly to file={OUTPUT_FILE}")
    logger.info(f"Total Execution Time={elapsed:.2f}s")
    logger.info("══════════════════════════════")

if __name__ == "__main__":
    asyncio.run(main())