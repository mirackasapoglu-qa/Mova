"""OWASP API guvenlik farkindalik testleri — YALNIZCA GET, veri degistirmez.

Kapsam: kirik kimlik dogrulama (JWT kurcalama), tenant izolasyonu (BOLA/IDOR),
enjeksiyon dayanikliligi, hata mesajlarindan bilgi sizmasi, guvenlik basliklari.

Tasarim kurallari:
  - Hicbir test mutating istek atmaz.
  - OTP hiz sinirina dokunulmaz (test hesabi kilitlenmesin).
  - "5xx donmemeli" temel degismezdir: gecersiz girdi 4xx uretmeli, cokme degil.
  - Bos sonuc PASS sayilmaz; dogrulanamayan senaryo atlanir.
"""
import re

import pytest
import requests
from jsonschema import validate

from tests.api import endpoints

pytestmark = pytest.mark.security

# Uzerinde calisilacak korumali liste uclari (hepsi salt-okunur)
PROTECTED_LISTS = [endpoints.CUSTOMERS, endpoints.PROJECTS, endpoints.TASKS,
                   endpoints.REQUESTS, endpoints.QUOTES]


def _raw_get(config, path, headers=None, params=None):
    """Fixture client'ini atlayarak ham istek — basliklari bilincli bozabilmek icin."""
    base = {"User-Agent": "qa-security", "Accept": "application/json"}
    base.update(headers or {})
    return requests.get(f"{config['base_url']}{path}", headers=base,
                        params=params, timeout=config["timeout"])


# --------------------------------------------------------------- kirik auth

@pytest.mark.parametrize("mutate,label", [
    (lambda t: t[:-3] + ("aaa" if not t.endswith("aaa") else "bbb"), "imza bozuldu"),
    (lambda t: t.split(".")[0] + ".eyJzdWIiOiJoYWNrZXIifQ." + t.split(".")[2], "payload degistirildi"),
    (lambda t: "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJoYWNrZXIifQ.", "alg=none"),
    (lambda t: t.replace(".", "", 1), "yapisi bozuldu"),
])
def test_tampered_token_is_rejected(config, auth_token, load_schema, mutate, label):
    """Kurcalanmis JWT kabul edilmemeli — imza dogrulamasi calisiyor mu."""
    response = _raw_get(config, endpoints.AUTH_ME, headers={
        "Authorization": f"Bearer {mutate(auth_token)}",
        "x-tenant-id": config["tenant_id"],
    })
    assert response.status_code == 401, (
        f"[{label}] kurcalanmis token 401 donmeli, gelen {response.status_code}: "
        f"{response.text[:200]}"
    )
    validate(instance=response.json(), schema=load_schema("error"))


def test_token_without_bearer_scheme_is_rejected(config, auth_token):
    """Sema belirtilmeden gonderilen token kabul edilmemeli."""
    response = _raw_get(config, endpoints.AUTH_ME, headers={
        "Authorization": auth_token, "x-tenant-id": config["tenant_id"],
    })
    assert response.status_code == 401, (
        f"'Bearer' olmadan token 401 donmeli, gelen {response.status_code}"
    )


# --------------------------------------------------- tenant izolasyonu (BOLA)

def test_tenant_header_cannot_override_token_tenant(authed_api, config, load_schema):
    """Sahte x-tenant-id ile baska tenant'in verisi alinamamali.

    Kayitlar `tenantId` tasiyor; token'in tenant'i disinda bir deger donerse
    yatay yetki asimi (BOLA) var demektir.
    """
    honest = authed_api.get(endpoints.QUOTES, params={"page": 1, "limit": 5})
    if honest.status_code != 200:
        pytest.skip(f"baseline alinamadi (HTTP {honest.status_code})")

    rows = honest.json().get("data") or []
    tenants = {r.get("tenantId") for r in rows if isinstance(r, dict) and r.get("tenantId")}
    if not tenants:
        pytest.skip("kayitlar tenantId tasimiyor — izolasyon dogrulanamadi")
    assert len(tenants) == 1, f"Tek istekte birden fazla tenant verisi dondu: {tenants}"
    own_tenant = tenants.pop()

    spoofed = _raw_get(config, endpoints.QUOTES, params={"page": 1, "limit": 5}, headers={
        "Authorization": f"Bearer {authed_api._session.headers['Authorization'].split()[1]}",
        "x-tenant-id": "00000000-0000-0000-0000-0000000000ff",
    })
    assert spoofed.status_code < 500, (
        f"Sahte tenant basligi 5xx uretti: {spoofed.status_code} {spoofed.text[:200]}"
    )
    if spoofed.status_code != 200:
        return  # reddedildi — beklenen ve guvenli davranis

    leaked = {r.get("tenantId") for r in (spoofed.json().get("data") or [])
              if isinstance(r, dict) and r.get("tenantId")}
    assert leaked <= {own_tenant}, (
        f"BOLA: sahte x-tenant-id ile baska tenant verisi sizdi: {leaked - {own_tenant}}"
    )


def test_foreign_resource_id_is_not_readable(authed_api, load_schema):
    """Var olmayan/baskasina ait ID 200 donmemeli (nesne seviyesi yetki)."""
    response = authed_api.get(
        endpoints.QUOTES_BY_QUOTE_ID.format(quoteId="00000000-0000-0000-0000-0000000000ff"))
    assert response.status_code in (400, 403, 404), (
        f"Yabanci ID icin 400/403/404 beklenir, gelen {response.status_code}: "
        f"{response.text[:200]}"
    )


# ------------------------------------------------------------- enjeksiyon

INJECTIONS = [
    ("' OR '1'='1", "sql-tautoloji"),
    ("'; DROP TABLE quotes;--", "sql-piggyback"),
    ('{"$ne": null}', "nosql-operator"),
    ("<script>alert(1)</script>", "xss-yansima"),
    ("../../../../etc/passwd", "path-traversal"),
]


@pytest.mark.parametrize("payload,label", INJECTIONS)
def test_injection_payloads_do_not_break_search(authed_api, payload, label):
    """Enjeksiyon yuku arama parametresinde cokme uretmemeli."""
    response = authed_api.get(endpoints.CUSTOMERS, params={"search": payload, "limit": 5})
    assert response.status_code < 500, (
        f"[{label}] 5xx uretti ({response.status_code}): {response.text[:200]}"
    )


def test_tautology_does_not_widen_result_set(authed_api):
    """SQL tautolojisi sonuc kumesini genisletmemeli (filtre bypass)."""
    baseline = authed_api.get(endpoints.CUSTOMERS,
                              params={"search": "zzzzz-eslesmeyen-zzzzz", "limit": 5})
    injected = authed_api.get(endpoints.CUSTOMERS,
                              params={"search": "zzzzz' OR '1'='1", "limit": 5})
    if baseline.status_code != 200 or injected.status_code != 200:
        pytest.skip("karsilastirma yapilamadi (200 disi yanit)")

    def total(resp):
        meta = resp.json().get("meta") or {}
        return meta.get("total", len(resp.json().get("data") or []))

    assert total(injected) <= total(baseline), (
        f"Tautoloji sonuc kumesini genisletti: {total(baseline)} -> {total(injected)} "
        "(filtre bypass olabilir)"
    )


def test_error_messages_do_not_leak_internals(authed_api):
    """Hata gövdesi stack trace / SQL / dosya yolu sizdirmamali."""
    response = authed_api.get(endpoints.QUOTES_BY_QUOTE_ID.format(quoteId="not-a-uuid"))
    body = response.text
    leaks = [pattern for pattern in
             (r"at \w+\.\w+ \(", r"node_modules", r"SELECT .* FROM", r"/usr/src/",
              r"QueryFailedError", r"\.ts:\d+")
             if re.search(pattern, body, re.I)]
    assert not leaks, f"Hata govdesi ic detay sizdiriyor ({leaks}): {body[:300]}"


@pytest.mark.xfail(
    reason="ACIK BULGU: gecersiz sortOrder 500 uretiyor ve yanit sunucu dosya yolunu "
           "(/root/opras-development/...), kaynak kod satirlarini ve Prisma sorgusunu "
           "sizdiriyor — bkz. DISCREPANCIES.md C7",
    strict=False)
def test_server_error_does_not_leak_source_code(authed_api):
    """5xx govdesi kaynak kod / dosya yolu / ORM sorgusu sizdirmamali."""
    response = authed_api.get(endpoints.CUSTOMERS,
                              params={"sortBy": "id", "sortOrder": "yukari", "limit": 5})
    body = response.text
    leaks = [pattern for pattern in
             (r"/root/", r"\.service\.ts:\d+", r"prisma\.\w+\.\w+\(", r"invocation in")
             if re.search(pattern, body, re.I)]
    assert not leaks, (
        f"5xx yaniti ic detay sizdiriyor ({leaks}). Istemciye yalnizca genel bir "
        f"hata mesaji donmeli. Govde: {body[:220]}"
    )


# ------------------------------------------------------- metot / basliklar

@pytest.mark.parametrize("path", [endpoints.AUTH_ME, endpoints.CUSTOMERS])
def test_undefined_method_does_not_crash(config, auth_token, path):
    """Tanimsiz metot 404/405 donmeli — 5xx degil. (Guvenli: TRACE)"""
    response = requests.request(
        "TRACE", f"{config['base_url']}{path}",
        headers={"Authorization": f"Bearer {auth_token}",
                 "x-tenant-id": config["tenant_id"]},
        timeout=config["timeout"])
    assert response.status_code < 500, (
        f"TRACE {path} -> {response.status_code}: {response.text[:200]}"
    )


@pytest.mark.xfail(
    reason="ACIK BULGU: X-Content-Type-Options ve Strict-Transport-Security yok; "
           "buna karsilik X-Powered-By donuyor (sunucu parmak izi) — "
           "bkz. DISCREPANCIES.md C8",
    strict=False)
def test_security_headers(authed_api):
    """Temel guvenlik basliklari olmali, parmak izi basliklari olmamali."""
    response = authed_api.get(endpoints.AUTH_ME)
    if response.status_code != 200:
        pytest.skip(f"/auth/me 200 donmedi (HTTP {response.status_code})")

    headers = {k.lower(): v for k, v in response.headers.items()}
    problems = []
    for required in ("x-content-type-options", "strict-transport-security"):
        if required not in headers:
            problems.append(f"eksik: {required}")
    for fingerprint in ("x-powered-by", "server"):
        if fingerprint in headers and headers[fingerprint].lower() not in ("cloudflare",):
            problems.append(f"parmak izi sizdiriyor: {fingerprint}={headers[fingerprint]}")

    assert not problems, "; ".join(problems)
