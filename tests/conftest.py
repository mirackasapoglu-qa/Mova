"""Ortak fixture'lar — tum testler bu yapilandirmayi paylasir.

Auth modeli (OPRAS): OTP tabanli.
    POST /v1/auth/otp/request  {email}                  -> OTP gonderilir
    POST /v1/auth/otp/verify   {email, otp, deviceInfo} -> accessToken + refreshToken

Otomasyon icin OTP_CODE (dev ortamindaki sabit/bypass kod) gerekir. Hazir bir
token varsa ACCESS_TOKEN ile dogrudan verilebilir ve OTP akisi atlanir.
Ikisi de yoksa auth gerektiren testler SKIP edilir — sessizce PASS gecmez.
"""
import json
import os
import pathlib
import time

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).parent.parent
SCHEMA_DIR = ROOT / "schemas"

OTP_REQUEST = "/v1/auth/otp/request"
OTP_VERIFY = "/v1/auth/otp/verify"


@pytest.fixture(scope="session")
def config():
    """Ortam degiskenlerinden yapilandirma."""
    return {
        "base_url": os.getenv("BASE_URL", "").rstrip("/"),
        "timeout": int(os.getenv("TIMEOUT", "15")),
        "tenant_id": os.getenv("TENANT_ID", "DEMO_TENANT"),
        "test_email": os.getenv("TEST_EMAIL", ""),
        "otp_code": os.getenv("OTP_CODE", ""),
        "access_token": os.getenv("ACCESS_TOKEN", ""),
        "unknown_email": os.getenv("UNKNOWN_EMAIL", "nonexistent_user_qa@example.com"),
    }


class Client:
    """base_url'e bagli, timeout'u onceden ayarlanmis ince requests sarmalayici."""

    def __init__(self, session, base_url, timeout):
        self._session = session
        self._base_url = base_url
        self._timeout = timeout

    def request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        url = path if path.startswith("http") else f"{self._base_url}{path}"
        return self._session.request(method, url, **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _make_session(tenant_id, token=None):
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    # Multi-tenant gateway: her istek tenant baglamini tasimali
    if tenant_id:
        session.headers.update({"x-tenant-id": tenant_id})
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="session")
def api(config):
    """Kimlik dogrulamasiz (misafir) client."""
    if not config["base_url"]:
        pytest.skip("BASE_URL tanimli degil — .env dosyasini doldur")
    session = _make_session(config["tenant_id"])
    yield Client(session, config["base_url"], config["timeout"])
    session.close()


@pytest.fixture(scope="session")
def auth_token(api, config):
    """Gecerli accessToken.

    Oncelik: ACCESS_TOKEN env > OTP akisi (TEST_EMAIL + OTP_CODE).
    Ikisi de yoksa auth gerektiren testler atlanir.
    """
    if config["access_token"]:
        return config["access_token"]

    if not (config["test_email"] and config["otp_code"]):
        pytest.skip(
            "Auth yapilandirilmadi — ACCESS_TOKEN ya da TEST_EMAIL+OTP_CODE tanimla"
        )

    # Sunucu OTP istekleri arasinda kisa bir bekleme penceresi uyguluyor
    # (resendAvailableIn ~5sn) ve asilirsa 429 doner. Panel/paralel kosum ayni
    # anda OTP isterse bu pencereye denk gelinir. Atlamak TEHLIKELI: skip build'i
    # kirmaz, suite hicbir sey dogrulamadan yesil gorunur. Bu yuzden yeniden dener.
    req = None
    for attempt in range(3):
        req = api.post(OTP_REQUEST, json={"email": config["test_email"]})
        if req.status_code in (200, 201):
            break
        if req.status_code != 429 and attempt == 0:
            break  # hiz siniri disi bir hata — tekrar denemenin anlami yok
        wait = 6
        try:
            payload = req.json().get("data") or req.json().get("error", {}).get("meta", {})
            wait = int(payload.get("resendAvailableIn") or payload.get("remainingSeconds") or 6)
        except (ValueError, AttributeError, TypeError):
            pass
        time.sleep(min(wait + 1, 30))

    if req.status_code not in (200, 201):
        pytest.skip(f"otp/request basarisiz (HTTP {req.status_code}): {req.text[:200]}")

    verify = api.post(OTP_VERIFY, json={
        "email": config["test_email"],
        "otp": config["otp_code"],
        "deviceInfo": "qa-automation",
    })
    if verify.status_code not in (200, 201):
        pytest.skip(f"otp/verify basarisiz (HTTP {verify.status_code}): {verify.text[:200]}")

    token = (verify.json().get("data") or {}).get("accessToken")
    if not token:
        pytest.skip(f"otp/verify accessToken dondurmedi: {verify.text[:200]}")
    return token


@pytest.fixture(scope="session")
def authed_api(config, auth_token):
    """Bearer token'i onceden set edilmis client."""
    session = _make_session(config["tenant_id"], token=auth_token)
    yield Client(session, config["base_url"], config["timeout"])
    session.close()


@pytest.fixture(scope="session")
def load_schema():
    """Isimle JSON sema yukler: schemas/<isim>.json"""
    def _load(name):
        with open(SCHEMA_DIR / f"{name}.json", encoding="utf-8") as f:
            return json.load(f)
    return _load


@pytest.fixture(scope="session")
def openapi_spec():
    """contract/openapi.json — spec-tabanli kapsam/drift testleri icin."""
    spec_path = ROOT / "contract" / "openapi.json"
    if not spec_path.exists():
        pytest.skip("contract/openapi.json yok — python contract/postman_to_openapi.py calistir")
    return json.loads(spec_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def envelope_exceptions():
    """contract/envelope_exceptions.json — bilinen envelope sapmalari baseline'i."""
    path = ROOT / "contract" / "envelope_exceptions.json"
    if not path.exists():
        return {"istisnalar": {}}
    return json.loads(path.read_text(encoding="utf-8"))
