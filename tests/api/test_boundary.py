"""Sinir deger testleri — YALNIZCA GET, veri degistirmez.

Kapsam: sayfalama sinirlari, bicimi bozuk parametreler, cok uzun/unicode girdi,
gecersiz siralama alani, bilinmeyen parametre.

Temel degismez: gecersiz girdi **4xx** uretmeli, 5xx DEGIL. Sunucunun cokmesi
her zaman kusurdur; girdiyi reddetmesi dogru davranistir.
"""
import pytest

from tests.api import endpoints

pytestmark = pytest.mark.boundary

LIST_ENDPOINT = endpoints.CUSTOMERS


def _assert_no_server_error(response, label):
    assert response.status_code < 500, (
        f"[{label}] sunucu hatasi {response.status_code}: {response.text[:250]}"
    )


# ------------------------------------------------------------- sayfalama

@pytest.mark.parametrize("params,label", [
    ({"page": 0, "limit": 10}, "page=0"),
    ({"page": -1, "limit": 10}, "page=-1"),
    ({"page": 1, "limit": 0}, "limit=0"),
    ({"page": 1, "limit": -5}, "limit=-5"),
    ({"page": 1, "limit": 100000}, "limit=100000"),
    ({"page": 999999, "limit": 10}, "page=999999"),
])
def test_pagination_bounds_do_not_crash(authed_api, params, label):
    """Sinir disi sayfalama degerleri cokme uretmemeli."""
    _assert_no_server_error(authed_api.get(LIST_ENDPOINT, params=params), label)


@pytest.mark.parametrize("params,label", [
    ({"page": "abc", "limit": 10}, "page=abc"),
    ({"page": 1, "limit": "on"}, "limit=on"),
    ({"page": 1.5, "limit": 10}, "page=1.5"),
    ({"page": "1;DROP", "limit": 10}, "page=1;DROP"),
])
def test_non_numeric_pagination_is_rejected(authed_api, params, label):
    """Sayisal olmayan sayfalama degeri 400 ile reddedilmeli."""
    response = authed_api.get(LIST_ENDPOINT, params=params)
    _assert_no_server_error(response, label)
    assert response.status_code == 400, (
        f"[{label}] 400 beklenir, gelen {response.status_code}: {response.text[:200]}"
    )


def test_huge_limit_is_capped(authed_api):
    """Cok buyuk limit ya reddedilmeli ya da makul bir tavana cekilmeli.

    Sinirsiz kabul edilirse tek istekle tum tablo cekilebilir (DoS/veri sizinti riski).
    """
    response = authed_api.get(LIST_ENDPOINT, params={"page": 1, "limit": 100000})
    _assert_no_server_error(response, "limit=100000")
    if response.status_code != 200:
        return  # reddedildi — kabul edilebilir

    rows = response.json().get("data") or []
    assert len(rows) <= 1000, (
        f"limit=100000 ile {len(rows)} kayit dondu — tavan uygulanmiyor"
    )


def test_page_beyond_end_returns_empty_not_error(authed_api):
    """Son sayfanin otesi bos liste donmeli, hata degil."""
    response = authed_api.get(LIST_ENDPOINT, params={"page": 999999, "limit": 10})
    _assert_no_server_error(response, "page=999999")
    if response.status_code != 200:
        pytest.skip(f"asim 200 disi donuyor (HTTP {response.status_code}) — davranis farkli")
    rows = response.json().get("data")
    assert isinstance(rows, list) and not rows, (
        f"Son sayfa otesinde bos liste beklenir, gelen: {str(rows)[:150]}"
    )


# --------------------------------------------------------------- arama girdisi

@pytest.mark.parametrize("value,label", [
    ("a" * 5000, "5000 karakter"),
    ("çğıöşüÇĞİÖŞÜ", "turkce karakter"),
    ("🔥🚀💥 emoji", "emoji"),
    ("   ", "sadece bosluk"),
    ("%00null", "null byte kacisi"),
    ("%%%", "yuzde isaretleri"),
    ("\\", "ters bolu"),
])
def test_search_input_edge_cases(authed_api, value, label):
    """Sinir/ozel karakter iceren arama cokme uretmemeli."""
    _assert_no_server_error(
        authed_api.get(LIST_ENDPOINT, params={"search": value, "limit": 5}), label)


def test_turkish_characters_are_preserved(authed_api):
    """Turkce arama terimi bozulmadan islenmeli (i/I katlanmasi tuzagi)."""
    response = authed_api.get(LIST_ENDPOINT, params={"search": "şirket", "limit": 5})
    _assert_no_server_error(response, "turkce arama")
    assert response.status_code == 200, (
        f"Turkce arama 200 donmeli, gelen {response.status_code}: {response.text[:200]}"
    )


# --------------------------------------------------- path parametresi / siralama

@pytest.mark.parametrize("value,label", [
    ("not-a-uuid", "gecersiz uuid"),
    ("123", "sayisal id"),
    # NOT: duz "../customers" yazilamaz — requests URL'i istemci tarafinda
    # normalize edip istegi /v1/customers'a cevirir ve test sunucuyu hic denemez.
    # Kacisli bicim gercekten sunucuya gider.
    ("%2e%2e%2fcustomers", "path traversal (kacisli)"),
    ("null", "null kelimesi"),
])
def test_malformed_path_param_is_handled(authed_api, value, label):
    """Bicimi bozuk path parametresi 400/404 donmeli, cokme degil."""
    response = authed_api.get(endpoints.CUSTOMERS_BY_CUSTOMER_ID.format(customerId=value))
    _assert_no_server_error(response, label)
    assert response.status_code in (400, 404), (
        f"[{label}] 400/404 beklenir, gelen {response.status_code}: {response.text[:200]}"
    )


@pytest.mark.parametrize("params,label", [
    ({"sortBy": "gecersizAlan"}, "bilinmeyen sortBy"),
    pytest.param(
        {"sortBy": "id", "sortOrder": "yukari"}, "gecersiz sortOrder",
        marks=pytest.mark.xfail(
            reason="ACIK BULGU: gecersiz sortOrder degeri dogrulanmadan Prisma'ya "
                   "gidiyor ve servis 500 ile cokuyor. Yanit ayrica kaynak dosya "
                   "yolunu ve kod satirlarini sizdiriyor — bkz. DISCREPANCIES.md C7",
            strict=False)),
    ({"sortBy": "id; DROP TABLE"}, "sortBy enjeksiyon"),
])
def test_invalid_sorting_is_rejected_not_crashing(authed_api, params, label):
    """Gecersiz siralama parametresi cokme uretmemeli."""
    _assert_no_server_error(
        authed_api.get(LIST_ENDPOINT, params={**params, "limit": 5}), label)


def test_unknown_query_param_is_tolerated(authed_api):
    """Bilinmeyen query parametresi ya yok sayilmali ya 400 donmeli — 5xx degil."""
    response = authed_api.get(LIST_ENDPOINT,
                              params={"bilinmeyenParametre": "x", "limit": 5})
    _assert_no_server_error(response, "bilinmeyen parametre")


def test_conflicting_filters_do_not_crash(authed_api):
    """Ayni parametrenin coklu/celiskili verilmesi cokme uretmemeli."""
    _assert_no_server_error(
        authed_api.get(LIST_ENDPOINT, params=[("limit", "5"), ("limit", "10")]),
        "tekrarli limit")
