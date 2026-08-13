"""Kural envanteri testleri — AGSIZ.

Envanter koddan turetiliyor; bu testler turetimin sessizce bozulmamasini garanti
eder. Bir regex kayarsa envanter bos/eksik doner ve pano "kural yok" gosterir —
sessiz bir yalan olur. Bu yuzden alt sinirlar assert edilir.
"""
import pathlib
import sys

import pytest

pytestmark = pytest.mark.schema

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from qa_core import rules  # noqa: E402


def test_analyze_rules_are_extracted():
    extracted = rules.analyze_rules()
    assert len(extracted) >= 15, f"analyze.py'den yalnizca {len(extracted)} kural cikti"
    assert all(r["baslik"] for r in extracted), "basligi bos kural var"
    severities = {r["severity"] for r in extracted}
    assert "kritik" in severities and "yuksek" in severities


def test_rule_titles_have_no_leftover_syntax():
    """f-string ifadeleri ve backtick'ler temizlenmis olmali."""
    for rule in rules.analyze_rules():
        title = rule["baslik"]
        assert "{" not in title and "}" not in title, f"ham f-string kalmis: {title!r}"
        assert "`" not in title, f"backtick kalmis: {title!r}"
        assert not title.endswith(("—", "-", "(")), f"sonu kirik: {title!r}"


def test_schemathesis_checks_are_read_from_run_sh():
    checks = rules.schemathesis_checks()
    assert "response_schema_conformance" in checks
    assert "not_a_server_error" in checks
    assert len(checks) == 4


def test_pytest_markers_are_read_from_ini():
    markers = {m["ad"] for m in rules.pytest_markers()}
    assert {"smoke", "auth", "negative", "schema", "boundary", "security",
            "mutating"} <= markers


def test_envelope_constraints_cover_both_schemas():
    constraints = rules.envelope_constraints()
    text = " ".join(c["kisit"] for c in constraints)
    assert "`success` zorunlu" in text
    assert "`error.code` zorunlu" in text
    assert "`error.message` zorunlu" in text


def test_agent_checklist_and_guardrails_are_parsed():
    checklist, guardrails = rules.agent_rules()
    assert len(checklist) == 11, f"11 kontrol maddesi bekleniyor, {len(checklist)} bulundu"
    assert len(guardrails) >= 5, f"guardrail sayisi dusuk: {len(guardrails)}"
    assert all(c["ad"] for c in checklist)


def test_baseline_summary_matches_file():
    summary = rules.baseline_summary()
    assert summary["toplam"] > 0
    assert sum(summary["kategoriler"].values()) == summary["toplam"]


def test_inventory_is_complete():
    inv = rules.inventory()
    assert len(inv["setler"]) == 8, f"{len(inv['setler'])} kural seti (8 bekleniyor)"
    assert inv["ozet"]["toplam"] == (inv["ozet"]["otomatikKural"]
                                     + inv["ozet"]["ajanKurali"])
    assert inv["ozet"]["testFonksiyonu"] > 50
    for rule_set in inv["setler"]:
        assert rule_set["adet"] == len(rule_set["kurallar"]), (
            f"'{rule_set['ad']}' sayisi ({rule_set['adet']}) listesiyle uyusmuyor "
            f"({len(rule_set['kurallar'])})")
        assert rule_set["aciklama"], f"'{rule_set['ad']}' aciklamasiz"


def test_test_files_are_discovered_with_markers():
    files = {f["dosya"]: f for f in rules.test_files()}
    assert "tests/api/test_security.py" in files
    assert "security" in files["tests/api/test_security.py"]["marker"]
    # agsiz olanlar dogru isaretlenmeli
    assert files["tests/test_analyze.py"]["agGerekir"] is False
