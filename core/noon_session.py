import asyncio
import uuid

from curl_cffi.requests import AsyncSession

from proxy.proxy_manager import (
    get_global_manager,
    mark_cooldown,
    mark_success,
    release_proxy,
)

BASE_URL = "https://minutes.noon.com"


def build_headers(visitor_id, platform="web"):
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": f"{BASE_URL}/uae-en/",
        "user-agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "x-platform": platform,
        "x-visitor-id": visitor_id,
        "x-locale": "en-ae",
        "x-mp-country": "ae",
        "x-experience": "nooninstant",
        "x-mp": "nooninstant",
        "x-ecom-zonecode": "AE_DXB-S5",
        "x-nooninstant-zonecode": "W00048740A",
        "x-lat": "249885436",
        "x-lng": "551589470",
    }


class NoonMinutesSession:

    def __init__(self):
        self.session = None
        self.proxy = None
        self.visitor_id = str(uuid.uuid4())

        self.proxy_manager = get_global_manager()

    async def start(self):

        self.proxy = self.proxy_manager.reserve_proxy(
            owner_id=self.visitor_id
        )

        if not self.proxy:
            raise Exception("No proxy available")

        self.session = AsyncSession(
            impersonate="chrome120",
            timeout=30,
        )

        self.session.cookies.set(
            "visitor_id",
            self.visitor_id,
            domain="minutes.noon.com",
        )

        headers = build_headers(self.visitor_id)

        proxies = {
            "http": self.proxy.url,
            "https": self.proxy.url,
        }

        steps = [
            ("POST", f"{BASE_URL}/_svc/instant/config", {}),
            ("GET", f"{BASE_URL}/_svc/configs-v1/configs", None),
            ("POST", f"{BASE_URL}/_svc/instant/session/get", {}),
        ]

        try:

            for method, url, body in steps:

                if method == "POST":

                    r = await self.session.post(
                        url,
                        headers=headers,
                        proxies=proxies,
                        json=body,
                    )

                else:

                    r = await self.session.get(
                        url,
                        headers=headers,
                        proxies=proxies,
                    )

                if r.status_code not in [200, 201]:
                    raise Exception(f"Bootstrap failed {r.status_code}")

            mark_success(self.proxy.id)

        except Exception:

            mark_cooldown(
                self.proxy.id,
                seconds=30,
                reason="bootstrap_failed",
            )

            raise

    async def get(self, url, **kwargs):

        headers = build_headers(self.visitor_id)

        proxies = {
            "http": self.proxy.url,
            "https": self.proxy.url,
        }

        try:

            r = await self.session.get(
                url,
                headers=headers,
                proxies=proxies,
                **kwargs,
            )

            if r.status_code in [403, 429]:
                mark_cooldown(
                    self.proxy.id,
                    seconds=30,
                    reason=f"http_{r.status_code}",
                )

            else:
                mark_success(self.proxy.id)

            return r

        except Exception:

            mark_cooldown(
                self.proxy.id,
                seconds=30,
                reason="request_failed",
            )

            raise

    async def post(self, url, **kwargs):

        headers = build_headers(self.visitor_id)

        proxies = {
            "http": self.proxy.url,
            "https": self.proxy.url,
        }

        try:

            r = await self.session.post(
                url,
                headers=headers,
                proxies=proxies,
                **kwargs,
            )

            if r.status_code in [403, 429]:
                mark_cooldown(
                    self.proxy.id,
                    seconds=30,
                    reason=f"http_{r.status_code}",
                )

            else:
                mark_success(self.proxy.id)

            return r

        except Exception:

            mark_cooldown(
                self.proxy.id,
                seconds=30,
                reason="request_failed",
            )

            raise

    async def close(self):

        if self.proxy:
            release_proxy(self.proxy.id)

        if self.session:
            await self.session.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()