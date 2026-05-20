import uuid
from curl_cffi.requests import AsyncSession

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
        self.visitor_id = str(uuid.uuid4())

    async def start(self):

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

        steps = [
            ("POST", f"{BASE_URL}/_svc/instant/config", {}),
            ("GET", f"{BASE_URL}/_svc/configs-v1/configs", None),
            ("POST", f"{BASE_URL}/_svc/instant/session/get", {}),
        ]

        for method, url, body in steps:

            if method == "POST":
                r = await self.session.post(
                    url,
                    headers=headers,
                    json=body,
                )
            else:
                r = await self.session.get(
                    url,
                    headers=headers,
                )

            if r.status_code not in [200, 201]:
                raise Exception(f"Bootstrap failed {r.status_code}")

    async def get(self, url, **kwargs):

        headers = build_headers(self.visitor_id)

        r = await self.session.get(
            url,
            headers=headers,
            **kwargs,
        )

        return r

    async def post(self, url, **kwargs):

        headers = build_headers(self.visitor_id)

        r = await self.session.post(
            url,
            headers=headers,
            **kwargs,
        )

        return r

    async def close(self):

        if self.session:
            await self.session.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()