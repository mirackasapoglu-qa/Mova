"""Auth davranisi — token GEREKTIRMEYEN negatif/sinir senaryolar.

Guvenlik notu: gercek bir hesap icin YANLIS OTP denemesi yapilmaz. Sunucu
OTP_LOOKUP_RATE_LIMITED (429) ile hiz siniri uyguluyor; ardarda yanlis deneme
test hesabini kilitleyip tum authli suite'i dusurebilir. Bunun yerine LOOKUP
ONCESI dogrulamaya (payload validation) takilan senaryolar kullanilir.
"""
import pytest
from jsonschema import validate

from tests.api import endpoints

pytestmark = pytest.mark.negative


def _assert_error_envelope(response, load_schema):
    body = response.json()
    validate(instance=body, schema=load_schema("error"))
    return body["error"]


@pytest.mark.smoke
def test_me_requires_token(api, load_schema):
    """Tokensiz profil cagrisi 401 + hata envelope'i donmeli."""
    response = api.get(endpoints.AUTH_ME)
    assert response.status_code == 401, (
        f"Tokensiz /auth/me 401 donmeli, gelen {response.status_code}: {response.text[:300]}"
    )
    error = _assert_error_envelope(response, load_schema)
    assert error["code"], "Hata kodu bos olmamali"


@pytest.mark.smoke
def test_protected_list_requires_token(api, load_schema):
    """Korumali liste ucu tokensiz 401 donmeli (acik veri sizmamali)."""
    response = api.get(endpoints.CUSTOMERS)
    assert response.status_code == 401, (
        f"Tokensiz /customers 401 donmeli, gelen {response.status_code}: {response.text[:300]}"
    )
    _assert_error_envelope(response, load_schema)


def test_otp_request_rejects_invalid_email(api, load_schema):
    """Bicimi bozuk e-posta lookup'a gitmeden 400 ERR_VALIDATION ile reddedilmeli."""
    response = api.post(endpoints.AUTH_OTP_REQUEST, json={"email": "not-an-email"})
    assert response.status_code == 400, (
        f"Gecersiz e-posta 400 donmeli, gelen {response.status_code}: {response.text[:300]}"
    )
    error = _assert_error_envelope(response, load_schema)
    assert error["code"] == "ERR_VALIDATION", f"Beklenen ERR_VALIDATION, gelen {error['code']}"
    fields = [item["field"] for item in error.get("errors", [])]
    assert "email" in fields, f"Validation hatasi email alanini gostermeli: {error}"


def test_otp_request_missing_email_rejected(api, load_schema):
    """Bos govde 400 ile reddedilmeli — 500 patlamamali."""
    response = api.post(endpoints.AUTH_OTP_REQUEST, json={})
    assert response.status_code == 400, (
        f"Bos govde 400 donmeli, gelen {response.status_code}: {response.text[:300]}"
    )
    _assert_error_envelope(response, load_schema)


def test_otp_verify_rejects_malformed_payload(api, load_schema):
    """Eksik alanli verify istegi dogrulamaya takilmali (OTP denemesi harcamadan)."""
    response = api.post(endpoints.AUTH_OTP_VERIFY, json={"email": "not-an-email"})
    assert response.status_code in (400, 422), (
        f"Bozuk verify govdesi 400/422 donmeli, gelen {response.status_code}: {response.text[:300]}"
    )
    _assert_error_envelope(response, load_schema)


def test_unknown_email_does_not_return_server_error(api, config, load_schema):
    """Kayitli olmayan e-posta duzgun karsilanmali — 5xx ile patlamamali.

    Beklenen: 404 USER_NOT_FOUND ya da 429 (hiz siniri). Not: 404 donmesi hesap
    numaralandirmasina (account enumeration) acik demektir; bu bilincli bir urun
    karari olabilir, test yalnizca sunucu hatasi olmadigini garanti eder.
    """
    response = api.post(endpoints.AUTH_OTP_REQUEST, json={"email": config["unknown_email"]})
    assert response.status_code < 500, (
        f"Bilinmeyen e-posta 5xx uretmemeli, gelen {response.status_code}: {response.text[:300]}"
    )
    assert response.status_code in (200, 404, 429), (
        f"Beklenmeyen status {response.status_code}: {response.text[:300]}"
    )
    if response.status_code >= 400:
        _assert_error_envelope(response, load_schema)
