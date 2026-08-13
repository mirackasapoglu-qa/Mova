"""Musteri CRUD — CANLI VERI YARATIR/DEGISTIRIR/SILER.

Bu suite `mutating` marker'i tasir ve varsayilan kosumda HARIC tutulur:

    pytest                     # bu dosya kosmaz
    pytest -m mutating         # bilincli olarak kosar

Guvenlik onlemleri (uc katmanli):
  1. Ortam kilidi — BASE_URL test/dev ortamina benzemiyorsa suite tamamen atlanir.
  2. Garanti temizlik — yaratilan her kayit ID'si aninda kaydedilir ve teardown'da
     test basarisiz olsa bile silinir.
  3. Taninabilir veri — tum kayitlar QA-AUTO oneki tasir; elde kalirsa kim yaratti
     bellidir.

Neden gerekli: API'nin 237 operasyonunun 135'i mutating. Yalnizca GET test etmek
yuzeyin %43'unu dogrular; create/update/delete davranisi, cakisma yonetimi ve
girdi dogrulama tamamen kor nokta kalir.
"""
import pytest

from tests.api import endpoints
from tests.utils import factories

pytestmark = [pytest.mark.mutating, pytest.mark.auth]

# Ortam kilidi: yalnizca bu kaliplari tasiyan adreslerde veri degistirilir
SAFE_ENVIRONMENT_HINTS = ("test", "dev", "staging", "localhost", "127.0.0.1")


@pytest.fixture(scope="module", autouse=True)
def guard_environment(config):
    """Uretim ortamina benzeyen bir adreste bu suite hic kosmaz."""
    base_url = (config["base_url"] or "").lower()
    if not base_url:
        pytest.skip("BASE_URL tanimli degil")
    if not any(hint in base_url for hint in SAFE_ENVIRONMENT_HINTS):
        pytest.skip(
            f"EMNIYET KILIDI: '{base_url}' test/dev ortamina benzemiyor. "
            f"Mutating suite yalnizca {SAFE_ENVIRONMENT_HINTS} iceren adreslerde kosar."
        )


@pytest.fixture
def customer_sink(authed_api):
    """Yaratilan musteri ID'lerini toplar ve test bitince siler.

    Temizlik teardown'da yapilir; test assert'te patlasa bile calisir.
    """
    created = []
    yield created
    for customer_id in created:
        try:
            authed_api.delete(
                endpoints.CUSTOMERS_BY_CUSTOMER_ID.format(customerId=customer_id))
        except Exception as exc:  # temizlik hatasi testi maskelememeli
            print(f"UYARI: {customer_id} temizlenemedi: {exc}")


# CANLI dogrulanmis minimum gecerli govde.
#
# DIKKAT: sozlesmedeki dokumante ornek KULLANILAMIYOR — canli API onu 400 ile
# reddediyor (`fullName` ve `isVip` alanlari taninmiyor, `individual` icin
# firstName/lastName/nationalId zorunlu). Bu bir sozlesme bulgusudur ve
# test_documented_example_is_accepted ile ayrica izlenir; buradaki govde
# canliya karsi kesfedilmistir.
def new_payload(openapi_spec=None, **overrides):
    """Canlida gecerli, benzersiz bir kurumsal musteri govdesi uretir."""
    payload = {
        "customerKind": "corporate",
        "customerType": "corporate",
        "companyName": factories.gen_name("QA-AUTO"),
        "taxNumber": factories.gen_national_id()[:10],
        "taxOffice": "Kadikoy",
        "email": factories.gen_email("qa_auto"),
        "phone": factories.gen_phone(),
    }
    payload.update(overrides)
    return payload


def create_customer(authed_api, customer_sink, payload):
    """Musteri yaratir, ID'yi TEMIZLIK LISTESINE ANINDA ekler ve yaniti doner."""
    response = authed_api.post(endpoints.CUSTOMERS, json=payload)
    if response.status_code in (200, 201):
        customer_id = ((response.json().get("data") or {}).get("id"))
        if customer_id:
            customer_sink.append(customer_id)
    return response


# --------------------------------------------------------------- yasam dongusu

def test_create_returns_201_with_envelope(authed_api, customer_sink, openapi_spec, load_schema):
    """Yeni musteri 201 + basari envelope'u ile donmeli, id tasimalı."""
    from jsonschema import validate

    payload = new_payload(openapi_spec)
    response = create_customer(authed_api, customer_sink, payload)

    assert response.status_code in (200, 201), (
        f"Olusturma basarisiz (HTTP {response.status_code}): {response.text[:300]}"
    )
    body = response.json()
    validate(instance=body, schema=load_schema("success"))
    data = body["data"]
    assert data.get("id"), f"Yanit id tasimiyor: {data}"
    assert data.get("tenantId"), "Yanit tenantId tasimiyor — tenant baglami kaybolmus"


def test_created_customer_is_readable(authed_api, customer_sink, openapi_spec):
    """Yaratilan kayit hemen okunabilmeli ve alanlari korunmali."""
    payload = new_payload(openapi_spec)
    created = create_customer(authed_api, customer_sink, payload)
    if created.status_code not in (200, 201):
        pytest.skip(f"olusturma basarisiz (HTTP {created.status_code})")

    customer_id = created.json()["data"]["id"]
    fetched = authed_api.get(
        endpoints.CUSTOMERS_BY_CUSTOMER_ID.format(customerId=customer_id))

    assert fetched.status_code == 200, (
        f"Yaratilan kayit okunamadi (HTTP {fetched.status_code}): {fetched.text[:250]}"
    )
    data = fetched.json()["data"]
    assert data["id"] == customer_id
    assert payload["companyName"] in (data.get("companyName") or data.get("displayName") or ""), (
        f"companyName korunmadi: gonderilen {payload['companyName']!r}, "
        f"donen {data.get('companyName')!r}"
    )


def test_update_is_applied_and_persisted(authed_api, customer_sink, openapi_spec):
    """PATCH degisikligi hem yanitta hem sonraki okumada gorunmeli."""
    created = create_customer(authed_api, customer_sink, new_payload(openapi_spec))
    if created.status_code not in (200, 201):
        pytest.skip(f"olusturma basarisiz (HTTP {created.status_code})")

    customer_id = created.json()["data"]["id"]
    new_name = factories.gen_name("QA-AUTO-GUNCEL")

    patched = authed_api.patch(
        endpoints.CUSTOMERS_BY_CUSTOMER_ID.format(customerId=customer_id),
        json={"companyName": new_name})
    assert patched.status_code == 200, (
        f"Guncelleme basarisiz (HTTP {patched.status_code}): {patched.text[:250]}"
    )

    fetched = authed_api.get(
        endpoints.CUSTOMERS_BY_CUSTOMER_ID.format(customerId=customer_id))
    data = fetched.json()["data"]
    assert new_name in (data.get("companyName") or data.get("displayName") or ""), (
        f"Guncelleme kalici olmadi: {data.get('companyName')!r} != {new_name!r}"
    )


def test_delete_removes_customer(authed_api, customer_sink, openapi_spec):
    """Silinen kayit artik okunamamali."""
    created = create_customer(authed_api, customer_sink, new_payload(openapi_spec))
    if created.status_code not in (200, 201):
        pytest.skip(f"olusturma basarisiz (HTTP {created.status_code})")

    customer_id = created.json()["data"]["id"]
    path = endpoints.CUSTOMERS_BY_CUSTOMER_ID.format(customerId=customer_id)

    deleted = authed_api.delete(path)
    assert deleted.status_code in (200, 204), (
        f"Silme basarisiz (HTTP {deleted.status_code}): {deleted.text[:250]}"
    )

    fetched = authed_api.get(path)
    assert fetched.status_code == 404, (
        f"Silinen kayit hala okunabiliyor (HTTP {fetched.status_code}): "
        f"{fetched.text[:250]}"
    )


def test_second_delete_does_not_crash(authed_api, customer_sink, openapi_spec):
    """Ayni kaydi iki kez silmek 404 donmeli, 500 degil."""
    created = create_customer(authed_api, customer_sink, new_payload(openapi_spec))
    if created.status_code not in (200, 201):
        pytest.skip(f"olusturma basarisiz (HTTP {created.status_code})")

    path = endpoints.CUSTOMERS_BY_CUSTOMER_ID.format(
        customerId=created.json()["data"]["id"])
    authed_api.delete(path)
    second = authed_api.delete(path)

    assert second.status_code < 500, (
        f"Ikinci silme 5xx uretti ({second.status_code}): {second.text[:250]}"
    )
    assert second.status_code in (404, 400, 200, 204), (
        f"Beklenmeyen status {second.status_code}: {second.text[:250]}"
    )


@pytest.mark.xfail(
    reason="ACIK BULGU: sozlesmedeki dokumante istek ornegi canli API tarafindan "
           "400 ile reddediliyor (fullName/isVip taninmiyor, individual icin "
           "firstName/lastName/nationalId zorunlu) — bkz. DISCREPANCIES.md C9",
    strict=False)
def test_documented_example_is_accepted(authed_api, customer_sink, openapi_spec):
    """Sozlesmedeki dokumante govde canlida kabul edilmeli.

    Dokuman bir istemci icin talimattir: oradaki ornegi gonderen FE calismali.
    """
    example = factories.spec_example(openapi_spec, endpoints.CUSTOMERS, "post")
    if not example:
        pytest.skip("sozlesmede istek ornegi yok")

    payload = factories.uniquify(example)
    response = create_customer(authed_api, customer_sink, payload)
    assert response.status_code in (200, 201), (
        f"Dokumante ornek reddedildi (HTTP {response.status_code}): "
        f"{response.text[:400]}"
    )


# ------------------------------------------------------------- dogrulama

def test_empty_payload_is_rejected(authed_api, load_schema):
    """Bos govde 400 ERR_VALIDATION ile reddedilmeli — kayit yaratilmamali."""
    from jsonschema import validate

    response = authed_api.post(endpoints.CUSTOMERS, json={})
    assert response.status_code == 400, (
        f"Bos govde 400 donmeli, gelen {response.status_code}: {response.text[:250]}"
    )
    body = response.json()
    validate(instance=body, schema=load_schema("error"))
    assert body["error"]["code"] == "ERR_VALIDATION", (
        f"ERR_VALIDATION beklenir, gelen {body['error']['code']}"
    )


def test_duplicate_tax_number_conflicts(authed_api, customer_sink, openapi_spec):
    """Ayni vergi numarasiyla ikinci kayit 409 donmeli (dokumante davranis)."""
    payload = new_payload(openapi_spec)
    first = create_customer(authed_api, customer_sink, payload)
    if first.status_code not in (200, 201):
        pytest.skip(f"ilk olusturma basarisiz (HTTP {first.status_code})")
    if not payload.get("taxNumber"):
        pytest.skip("govdede taxNumber yok — cakisma dogrulanamaz")

    duplicate = new_payload(openapi_spec, taxNumber=payload["taxNumber"])
    second = create_customer(authed_api, customer_sink, duplicate)

    assert second.status_code != 500, (
        f"Cakisma 5xx uretti: {second.text[:250]}"
    )
    assert second.status_code == 409, (
        f"Tekrarli vergi no icin 409 beklenir, gelen {second.status_code}: "
        f"{second.text[:250]}"
    )


def test_server_controlled_fields_cannot_be_injected(authed_api, customer_sink, openapi_spec):
    """Istemci id/tenantId gibi sunucu kontrolundeki alanlari belirleyememeli.

    Mass-assignment: govdede gonderilen tenantId kabul edilirse baska bir tenant'a
    kayit yazilabilir.
    """
    forged_tenant = "00000000-0000-0000-0000-0000000000ff"
    forged_id = "11111111-1111-4111-8111-111111111111"
    payload = new_payload(openapi_spec, tenantId=forged_tenant, id=forged_id)

    response = create_customer(authed_api, customer_sink, payload)
    if response.status_code == 400:
        return  # tanimsiz alan reddedildi — en guvenli davranis

    if response.status_code not in (200, 201):
        pytest.skip(f"olusturma basarisiz (HTTP {response.status_code})")

    data = response.json()["data"]
    assert data.get("tenantId") != forged_tenant, (
        "MASS-ASSIGNMENT: govdede gonderilen tenantId kabul edildi — "
        "baska tenant'a kayit yazilabilir"
    )
    assert data.get("id") != forged_id, (
        "MASS-ASSIGNMENT: govdede gonderilen id kabul edildi"
    )
