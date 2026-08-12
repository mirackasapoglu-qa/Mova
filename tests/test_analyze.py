"""qa-dashboard/analyze.py birim testleri — ag GEREKTIRMEZ.

Otomatik yorum motoru deterministik oldugu icin tamamen test edilebilir: ayni
girdi her zaman ayni bulgu kumesini uretir. Bu testler motorun sapmalari dogru
siniflandirdigini ve siddet sirasini korudugunu garanti eder.
"""
import importlib.util
import pathlib

import pytest

pytestmark = pytest.mark.schema

# qa-dashboard tire icerdigi icin normal import edilemez — dosyadan yuklenir
_PATH = pathlib.Path(__file__).parent.parent / "qa-dashboard" / "analyze.py"
_spec = importlib.util.spec_from_file_location("qa_analyze", _PATH)
qa_analyze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qa_analyze)

analyze = qa_analyze.analyze
summarize = qa_analyze.summarize
PLACEHOLDER_ID = qa_analyze.PLACEHOLDER_ID


def card(**over):
    base = {
        "method": "GET", "path": "/v1/customers/{customerId}",
        "documentedStatuses": ["200", "404"], "envelopeExceptions": [],
        "responseExample": {"success": True, "data": {"id": "uuid"}},
    }
    base.update(over)
    return base


def titles(findings):
    return [f["baslik"] for f in findings]


def by_severity(findings, severity):
    return [f for f in findings if f["severity"] == severity]


def test_server_error_is_critical():
    findings = analyze(card(), 500, {"success": False}, [])
    assert by_severity(findings, "kritik"), "5xx kritik olarak isaretlenmeli"
    assert findings[0]["severity"] == "kritik", "kritik bulgu en uste siralanmali"


def test_undocumented_status_is_high_but_401_is_informational():
    other = analyze(card(), 418, {}, [])
    assert any("418" in t for t in titles(other))
    assert by_severity(other, "yuksek"), "beklenmeyen status yuksek olmali"

    unauthorized = analyze(card(documentedStatuses=["200"]), 401, {}, [])
    assert by_severity(unauthorized, "bilgi"), "401 dokuman eksigi — bilgi seviyesi"
    assert not by_severity(unauthorized, "yuksek")


def test_money_field_type_mismatch_is_high_priority():
    errors = [{"path": "data/totalRevenue", "message": "141591.45 is not of type 'integer'"}]
    findings = analyze(card(), 200, {"success": True, "data": {}}, errors)
    money = [f for f in findings if "Para alani" in f["baslik"]]
    assert money, f"para alani ozel olarak isaretlenmeli: {titles(findings)}"
    assert money[0]["severity"] == "yuksek"
    assert "hassasiyet" in money[0]["aciklama"]


def test_count_field_is_not_treated_as_money():
    errors = [{"path": "meta/totalPages", "message": "10.5 is not of type 'integer'"}]
    findings = analyze(card(), 200, {"success": True, "data": {}}, errors)
    assert not [f for f in findings if "Para alani" in f["baslik"]], \
        "totalPages sayim alanidir, para olarak siniflandirilmamali"


def test_null_values_are_grouped_as_nullable_gap():
    errors = [
        {"path": "data/taxNumber", "message": "None is not of type 'string'"},
        {"path": "data/taxOffice", "message": "None is not of type 'string'"},
    ]
    findings = analyze(card(), 200, {"success": True, "data": {}}, errors)
    nullable = [f for f in findings if "null" in f["baslik"].lower()]
    assert len(nullable) == 1, "null bulgulari tek bulguda gruplanmali"
    assert "2 alan" in nullable[0]["baslik"]
    assert "nullable" in nullable[0]["oneri"]


def test_missing_required_field_flagged_as_possible_regression():
    errors = [{"path": "data", "message": "'id' is a required property"}]
    findings = analyze(card(), 200, {"success": True, "data": {}}, errors)
    missing = [f for f in findings if "Kayip alan" in f["baslik"]]
    assert missing and missing[0]["severity"] == "yuksek"
    assert "Regresyon" in missing[0]["oneri"]


def test_placeholder_id_404_warns_about_masking():
    findings = analyze(card(), 404, {"success": False}, [],
                       path_params={"customerId": PLACEHOLDER_ID})
    assert [f for f in findings if "maskelen" in f["baslik"].lower()], \
        "yer tutucu ID ile 404 alindiginda maskeleme uyarisi verilmeli"


def test_real_id_404_does_not_warn_about_masking():
    findings = analyze(card(), 404, {"success": False}, [],
                       path_params={"customerId": "24f4414b-67c3-4e94-9d59-e8a80c6e3287"})
    assert not [f for f in findings if "maskelen" in f["baslik"].lower()]


def test_empty_list_is_not_a_pass():
    findings = analyze(card(path="/v1/customers"), 200,
                       {"success": True, "data": [], "meta": {"total": 0}}, [])
    empty = [f for f in findings if "Bos liste" in f["baslik"]]
    assert empty, "bos liste ayrica isaretlenmeli"
    assert empty[0]["severity"] == "orta"


def test_list_shape_drift_detected():
    documented_nested = card(
        path="/v1/customers",
        responseExample={"success": True, "data": {"data": [{"id": "uuid"}],
                                                  "meta": {"total": 1}}},
    )
    findings = analyze(documented_nested, 200,
                       {"success": True, "data": [{"id": "x"}], "meta": {"total": 1}}, [])
    shape = [f for f in findings if "Liste yapisi" in f["baslik"]]
    assert shape and shape[0]["severity"] == "yuksek"
    assert "data.data" in shape[0]["aciklama"]


def test_known_exception_marked_as_not_new():
    with_exception = card(envelopeExceptions=[
        {"anahtar": "GET /v1/customers/{customerId} [400]", "kategori": "eksik-ornek",
         "gerekce": "Ornek kisaltilmis."}])
    findings = analyze(with_exception, 200, {"success": True, "data": {}}, [])
    known = [f for f in findings if "bilinen sapma" in f["baslik"].lower()]
    assert known, "baseline'daki sapma bildirilmeli"
    assert "yeni bulgu sayilmaz" in known[0]["oneri"]


def test_real_defect_category_raises_severity():
    real = card(envelopeExceptions=[
        {"anahtar": "POST /v1/projects/{projectId}/notes [403]",
         "kategori": "envelope-disi", "gerekce": "Global envelope uygulanmamis."}])
    findings = analyze(real, 200, {"success": True, "data": {}}, [])
    known = [f for f in findings if "bilinen sapma" in f["baslik"].lower()]
    assert known[0]["severity"] == "yuksek", \
        "envelope-disi gercek kusurdur, bilgi seviyesinde kalmamali"


def test_pii_is_flagged():
    body = {"success": True, "data": {"id": "x", "email": "a@b.com"}}
    findings = analyze(card(), 200, body, [])
    assert [f for f in findings if "PII" in f["baslik"]]


def test_slow_response_flagged_by_threshold():
    assert not [f for f in analyze(card(), 200, {"success": True, "data": {}}, [],
                                   elapsed_ms=400) if "Yavas" in f["baslik"]]
    slow = [f for f in analyze(card(), 200, {"success": True, "data": {}}, [],
                               elapsed_ms=3500) if "Yavas" in f["baslik"]]
    assert slow and slow[0]["severity"] == "orta"


def test_cache_header_present_suppresses_note():
    with_cache = analyze(card(), 200, {"success": True, "data": {}}, [],
                         headers={"Cache-Control": "max-age=60"})
    assert not [f for f in with_cache if "Cache-Control" in f["baslik"]]


def test_clean_response_yields_no_findings():
    findings = analyze(card(), 200, {"success": True, "data": {"id": "x"}}, [],
                       elapsed_ms=120, headers={"Cache-Control": "max-age=60"})
    assert findings == [], f"temiz yanitta bulgu olmamali: {titles(findings)}"
    assert "bulunmadi" in summarize(findings)


def test_summary_orders_by_severity():
    findings = analyze(card(documentedStatuses=["200"]), 500, {"success": False}, [])
    summary = summarize(findings)
    assert summary.startswith("1 kritik"), summary


def test_findings_are_sorted_most_severe_first():
    errors = [{"path": "data/totalRevenue", "message": "1.5 is not of type 'integer'"}]
    findings = analyze(card(documentedStatuses=["200"]), 500,
                       {"success": True, "data": {"email": "a@b.com"}}, errors,
                       elapsed_ms=5000)
    severities = [qa_analyze.SEVERITY_ORDER[f["severity"]] for f in findings]
    assert severities == sorted(severities), "bulgular siddete gore sirali olmali"
