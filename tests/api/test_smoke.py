"""Authli okuma akislari — kritik uclarin canlida ayakta oldugunu dogrular.

Yalnizca GET; hicbir test veri yaratmaz/degistirmez. Mutating senaryolar ayri
bir suite'e ait ve acik onay ister.
"""
import pytest
from jsonschema import validate

from tests.api import endpoints

pytestmark = [pytest.mark.smoke, pytest.mark.auth]


def _assert_success_envelope(response, load_schema):
    assert response.status_code == 200, (
        f"200 beklendi, gelen {response.status_code}: {response.text[:300]}"
    )
    body = response.json()
    validate(instance=body, schema=load_schema("success"))
    return body["data"]


def test_me_returns_profile(authed_api, load_schema):
    """Token gecerliyse /auth/me kimlik bilgisini dondurmeli."""
    data = _assert_success_envelope(authed_api.get(endpoints.AUTH_ME), load_schema)
    for field in ("id", "email", "role"):
        assert data.get(field), f"/auth/me yanitinda '{field}' bos/eksik: {data}"


@pytest.mark.xfail(
    reason="DOKUMAN<->CANLI SAPMASI: dokumante ornek tenantId'yi uuid gosteriyor, "
           "canli null donuyor. Multi-tenant sistemde profilin tenant baglami "
           "tasimamasi teyit gerektirir — bkz. DISCREPANCIES.md",
    strict=False,
)
def test_me_carries_tenant_context(authed_api, load_schema):
    """Multi-tenant sistemde profil, ait oldugu tenant'i tasimali."""
    data = _assert_success_envelope(authed_api.get(endpoints.AUTH_ME), load_schema)
    assert data.get("tenantId"), (
        f"/auth/me tenantId dondurmedi (canli: {data.get('tenantId')!r}); "
        f"dokumante ornek uuid bekliyor"
    )


@pytest.mark.parametrize("path", [
    endpoints.CUSTOMERS,
    endpoints.PROJECTS,
    endpoints.TASKS,
    endpoints.REQUESTS,
    endpoints.QUOTES,
])
def test_core_list_endpoints_respond(authed_api, load_schema, path):
    """Cekirdek liste uclari basari envelope'u ile yanit vermeli."""
    _assert_success_envelope(authed_api.get(path), load_schema)


def test_list_pagination_is_honoured(authed_api, load_schema):
    """limit parametresi yanit boyutunu gercekten sinirlamali.

    Bos liste PASS sayilmaz: veri yoksa dogrulama yapilamaz, test atlanir.
    """
    response = authed_api.get(endpoints.CUSTOMERS, params={"page": 1, "limit": 2})
    data = _assert_success_envelope(response, load_schema)

    # Liste uclarinda sayfalama data.data / data icinde gelebiliyor
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        pytest.skip(f"Liste yapisi beklenenden farkli, sayfalama dogrulanamadi: {type(items)}")
    if not items:
        pytest.skip("Kayit yok — sayfalama dogrulanamadi (bos sonuc PASS sayilmaz)")

    assert len(items) <= 2, f"limit=2 istendi, {len(items)} kayit dondu"


def test_invalid_token_is_rejected(api, config, load_schema):
    """Kurcalanmis token 401 donmeli — imza dogrulamasi calisiyor mu.

    `api` fixture'i BASE_URL yoksa suite'i atlatir; burada bilincli olarak ham
    requests kullaniliyor cunku amac gecersiz Authorization basligi gondermek.
    """
    import requests

    response = requests.get(
        f"{config['base_url']}{endpoints.AUTH_ME}",
        headers={
            "Authorization": "Bearer gecersiz.token.imzasi",
            "x-tenant-id": config["tenant_id"],
        },
        timeout=config["timeout"],
    )
    assert response.status_code == 401, (
        f"Gecersiz token 401 donmeli, gelen {response.status_code}: {response.text[:300]}"
    )
    validate(instance=response.json(), schema=load_schema("error"))
