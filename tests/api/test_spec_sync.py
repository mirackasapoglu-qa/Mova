"""Spec ic tutarliligi — AGSIZ calisir (canli ortam gerekmez).

Bu testler API'yi degil, sozlesmenin kendisini dogrular:
  - endpoints.py ile openapi.json ayni yollari mi tasiyor (uretim guncel mi)
  - her operasyonun dokumante edilmis en az bir yaniti var mi
  - dokumante ornekler OPRAS envelope'una uyuyor mu (2xx -> success, 4xx/5xx -> error)

Envelope sapmasi burada yakalanirsa sorun koleksiyondadir; canli kosumda
yakalanirsa sorun API'dedir. Ikisini ayirmak, contract bulgularinin kime
gidecegini netlestirir.
"""
import pytest
from jsonschema import Draft7Validator

from tests.api import endpoints

pytestmark = pytest.mark.schema


def _operations(spec):
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method != "parameters":
                yield path, method, op


def test_endpoints_module_matches_spec(openapi_spec):
    """endpoints.py, spec ile birebir ayni yol kumesini tasimali."""
    spec_paths = set(openapi_spec["paths"])
    module_paths = set(endpoints.ALL_PATHS)

    missing = spec_paths - module_paths
    extra = module_paths - spec_paths
    assert not missing and not extra, (
        f"endpoints.py guncel degil — eksik: {sorted(missing)[:5]}, "
        f"fazla: {sorted(extra)[:5]}. Cozum: python contract/gen_endpoints.py"
    )


def test_every_operation_documents_a_response(openapi_spec):
    """Yanitsiz operasyon contract testinde dogrulanamaz."""
    undocumented = [
        f"{method.upper()} {path}"
        for path, method, op in _operations(openapi_spec)
        if not op.get("responses")
    ]
    assert not undocumented, f"Yanit dokumante edilmemis operasyonlar: {undocumented}"


def _envelope_violations(spec, load_schema):
    """Envelope'a uymayan dokumante ornekleri (anahtar -> ihlal) doner."""
    success_validator = Draft7Validator(load_schema("success"))
    error_validator = Draft7Validator(load_schema("error"))

    violations = {}
    for path, method, op in _operations(spec):
        for code, response in op.get("responses", {}).items():
            example = (
                response.get("content", {})
                .get("application/json", {})
                .get("example")
            )
            if example is None or not isinstance(example, dict) or not code.isdigit():
                continue

            validator = success_validator if int(code) < 400 else error_validator
            errors = sorted(validator.iter_errors(example), key=lambda e: list(e.path))
            if errors:
                violations[f"{method.upper()} {path} [{code}]"] = errors[0].message
    return violations


def test_no_new_envelope_violations(openapi_spec, load_schema, envelope_exceptions):
    """Baseline'da OLMAYAN yeni bir envelope sapmasi cikmamali.

    Bilinen sapmalar contract/envelope_exceptions.json'da gerekceleriyle kayitli.
    Yeni bir sapma eklenirse bu test kirilir — borç sessizce birikemez.
    """
    known = set(envelope_exceptions["istisnalar"])
    found = _envelope_violations(openapi_spec, load_schema)

    new = {k: v for k, v in found.items() if k not in known}
    assert not new, (
        f"{len(new)} YENI envelope sapmasi:\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in list(new.items())[:15])
        + "\n\nDuzeltilemiyorsa contract/envelope_exceptions.json'a gerekcesiyle ekle."
    )


def test_exception_baseline_has_no_stale_entries(openapi_spec, load_schema, envelope_exceptions):
    """Duzelen sapma baseline'da kalmamali — liste gercegi yansitmali."""
    found = set(_envelope_violations(openapi_spec, load_schema))
    stale = [k for k in envelope_exceptions["istisnalar"] if k not in found]
    assert not stale, (
        f"{len(stale)} istisna artik gecerli degil (sapma duzelmis) — "
        f"contract/envelope_exceptions.json'dan sil:\n  " + "\n  ".join(stale[:15])
    )
