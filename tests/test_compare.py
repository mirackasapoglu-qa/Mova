"""qa-dashboard/compare.py birim testleri — AGSIZ.

Kart beklentisi ile canli yaniti karsilastiran motor deterministiktir, bu yuzden
tamamen test edilebilir. Kritik davranislar: yer tutucu toleransi, degisken
alanlarin (id/timestamp) yok sayilmasi, eksik alan tespiti, tip farki tespiti.
"""
import importlib.util
import pathlib

import pytest

pytestmark = pytest.mark.schema

_PATH = pathlib.Path(__file__).parent.parent / "qa-dashboard" / "compare.py"
_spec = importlib.util.spec_from_file_location("qa_compare", _PATH)
qa_compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qa_compare)

compare_card_to_live = qa_compare.compare_card_to_live


def test_identical_shape_is_uyumlu():
    expected = {"success": True, "data": {"name": "Acente", "memberCount": 0}}
    live = {"success": True, "data": {"name": "Muhasebe", "memberCount": 7}}
    result = compare_card_to_live(expected, live, 200)
    assert result["durum"] == "uyumlu", result
    assert not result["eksik"] and not result["tipFarki"]


def test_placeholder_values_are_tolerated():
    """Kart 'uuid'/'$string' yazmis; canli gercek deger donmus — fark sayilmaz."""
    expected = {"success": True, "data": {"id": "uuid", "code": "$string"}}
    live = {"success": True, "data": {"id": "8f14e45f-ceea-467a-9c1e-000000000001",
                                      "code": "DEP-001"}}
    result = compare_card_to_live(expected, live, 200)
    assert result["durum"] == "uyumlu", result


def test_missing_field_is_detected():
    expected = {"success": True, "data": {"name": "x", "icon": "briefcase"}}
    live = {"success": True, "data": {"name": "x"}}
    result = compare_card_to_live(expected, live, 200)
    assert result["durum"] == "uyumsuz"
    assert "data.icon" in result["eksik"]


def test_type_mismatch_is_detected():
    """Kart sayi vaat etmis, canli string donmus."""
    expected = {"success": True, "data": {"memberCount": 0}}
    live = {"success": True, "data": {"memberCount": "0"}}
    result = compare_card_to_live(expected, live, 200)
    assert result["durum"] == "uyumsuz"
    assert result["tipFarki"][0]["alan"] == "data.memberCount"
    assert result["tipFarki"][0]["beklenen"] == "integer"
    assert result["tipFarki"][0]["gelen"] == "string"


def test_integer_and_float_are_compatible():
    expected = {"success": True, "data": {"total": 10}}
    live = {"success": True, "data": {"total": 10.5}}
    assert compare_card_to_live(expected, live, 200)["durum"] == "uyumlu"


def test_volatile_fields_are_ignored():
    """id/timestamp gibi her yanitta degisen alanlar fark uretmemeli."""
    expected = {"success": True, "data": {"id": "uuid", "createdAt": "2026-07-01T00:00:00.000Z"}}
    live = {"success": True, "data": {"id": 12345, "createdAt": 99999}}
    assert compare_card_to_live(expected, live, 200)["durum"] == "uyumlu"


def test_extra_live_fields_are_informational_not_failure():
    expected = {"success": True, "data": {"name": "x"}}
    live = {"success": True, "data": {"name": "x", "yeniAlan": "z"}}
    result = compare_card_to_live(expected, live, 200)
    assert result["durum"] == "uyumlu", "fazla alan uyumsuzluk sayilmamali"
    assert any("yeniAlan" in n for n in result["notlar"])


def test_nested_array_first_element_is_compared():
    expected = {"success": True, "data": [{"action": "x", "text": "y"}]}
    live = {"success": True, "data": [{"action": "x"}]}
    result = compare_card_to_live(expected, live, 200)
    assert "data[0].text" in result["eksik"]


def test_object_expected_but_array_returned():
    expected = {"success": True, "data": {"a": 1}}
    live = {"success": True, "data": [1, 2]}
    result = compare_card_to_live(expected, live, 200)
    assert result["durum"] == "uyumsuz"
    assert result["tipFarki"][0]["beklenen"] == "object"


def test_error_status_short_circuits_with_clear_verdict():
    """Kart basari tarif ederken canli 500 donduyse yapi diff'i anlamsiz."""
    expected = {"success": True, "data": {"name": "x"}}
    result = compare_card_to_live(expected, {"success": False}, 500,
                                  documented_statuses=["200", "400"])
    assert result["durum"] == "uyumsuz"
    assert "500" in result["verdict"]
    assert any("tanimli degil" in n for n in result["notlar"])


def test_no_expected_response_is_dogrulanamadi():
    result = compare_card_to_live(None, {"success": True}, 200)
    assert result["durum"] == "dogrulanamadi"


def test_non_json_live_body_is_dogrulanamadi():
    result = compare_card_to_live({"success": True}, None, 200)
    assert result["durum"] == "dogrulanamadi"
