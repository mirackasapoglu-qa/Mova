"""TP-797 — Talepler / Aktiviteler Sekmesi (GET /v1/requests/{id}/activities)

Kartin kabul kriterleri testе cevrildi:
  - 8 aksiyon tipi tanimli
  - BE her aktivite icin hazir Turkce `text` doner; FE metin uretmez
  - Her aktivite: id, action, actor{id,name,avatarColor,initials}, metadata, text, createdAt

Metin formatlari karttaki sablonlarla BIREBIR karsilastirilir. Bir aksiyon tipi
canli veride hic gorulmezse test onu FAIL saymaz — dogrulanamadi olarak atlar
(bos sonuc PASS degildir, ama yoklugu da kusur degildir).
"""
import re

import pytest

from tests.api import endpoints

pytestmark = [pytest.mark.auth, pytest.mark.smoke]

# Kart TP-797'deki metin formatlari (birebir)
TEXT_FORMATS = {
    "request_created": re.compile(r"^.+ talebi oluşturdu\.$"),
    "status_changed": re.compile(r"^.+, durumu .+ → .+ olarak değiştirdi\.$"),
    "priority_changed": re.compile(r"^.+, önceliği .+ → .+ olarak değiştirdi\.$"),
    "assignee_changed": re.compile(r"^.+, sorumluyu .+ → .+ olarak değiştirdi\.$"),
    "description_changed": re.compile(r"^.+ açıklamayı güncelledi\.$"),
    "file_added": re.compile(r"^.+, .+ dosyasını yükledi\.$"),
    "file_removed": re.compile(r"^.+, .+ dosyasını sildi\.$"),
    "quote_created": re.compile(r"^.+ teklif oluşturdu\.$"),
}

ACTIVITY_FIELDS = ("id", "action", "actor", "metadata", "text", "createdAt")
ACTOR_FIELDS = ("id", "name", "avatarColor", "initials")

SCAN_PAGES = 2
PAGE_SIZE = 50


@pytest.fixture(scope="module")
def activities(authed_api):
    """Birden fazla talebin aktivitelerini toplar (tek talep temsili degildir)."""
    request_ids = []
    for page in range(1, SCAN_PAGES + 1):
        response = authed_api.get(endpoints.REQUESTS, params={"page": page, "limit": PAGE_SIZE})
        if response.status_code != 200:
            pytest.skip(f"talep listesi alinamadi (HTTP {response.status_code})")
        batch = response.json().get("data") or []
        request_ids += [item["id"] for item in batch if item.get("id")]
        if len(batch) < PAGE_SIZE:
            break

    if not request_ids:
        pytest.skip("hic talep yok — aktiviteler dogrulanamaz")

    collected = []
    for request_id in request_ids:
        response = authed_api.get(
            endpoints.REQUESTS_ACTIVITIES_BY_REQUEST_ID.format(requestId=request_id)
        )
        assert response.status_code == 200, (
            f"aktivite ucu HTTP {response.status_code} dondu (talep {request_id}): "
            f"{response.text[:200]}"
        )
        collected += response.json().get("data") or []

    if not collected:
        pytest.skip("taranan taleplerin hicbirinde aktivite yok — dogrulanamadi")
    return collected


def test_activity_records_carry_required_fields(activities):
    """Her aktivite kartta tanimli tum alanlari tasimali."""
    missing = []
    for act in activities:
        for field in ACTIVITY_FIELDS:
            if field not in act:
                missing.append(f"{act.get('action')}: '{field}'")
        for field in ACTOR_FIELDS:
            if field not in (act.get("actor") or {}):
                missing.append(f"{act.get('action')}: actor.{field}")
    assert not missing, f"{len(missing)} eksik alan: {sorted(set(missing))[:10]}"


def test_actions_are_within_documented_set(activities):
    """Kartta tanimli olmayan bir aksiyon tipi donmemeli."""
    unknown = {a.get("action") for a in activities} - set(TEXT_FORMATS)
    assert not unknown, f"Kartta tanimli olmayan aksiyon(lar): {unknown}"


@pytest.mark.parametrize("action", sorted(TEXT_FORMATS))
def test_text_matches_card_format(activities, action):
    """BE'nin urettigi Turkce metin, karttaki sablona birebir uymali."""
    matching = [a for a in activities if a.get("action") == action]
    if not matching:
        pytest.skip(f"'{action}' canli veride gorulmedi — dogrulanamadi")

    pattern = TEXT_FORMATS[action]
    bad = [a.get("text") for a in matching if not pattern.match(a.get("text") or "")]
    assert not bad, (
        f"'{action}' metni sablona uymuyor ({len(bad)}/{len(matching)}): {bad[:3]}"
    )


def test_status_change_carries_label_metadata(activities):
    """status_changed, FE'nin gostermesi icin from/to etiketlerini tasimali."""
    changes = [a for a in activities if a.get("action") == "status_changed"]
    if not changes:
        pytest.skip("status_changed gorulmedi — dogrulanamadi")

    incomplete = [
        a["id"] for a in changes
        if not all(k in (a.get("metadata") or {})
                   for k in ("fromValue", "fromLabel", "toValue", "toLabel"))
    ]
    assert not incomplete, f"{len(incomplete)} status_changed kaydinda etiket eksik"
