"""contract/openapi.json -> qa-dashboard/registry.json

Panonun kart kaynagi. NadirGold surumunde kartlar Jira'dan turetiliyordu; OPRAS'ta
sozlesmenin kendisi daha eksiksiz bir kaynak: 161 path / 237 operasyon, her biri
dokumante ornek istek + beklenen yanit semasiyla birlikte.

ELLE GIRILEN ALANLAR KORUNUR (status / verdict / notes / owner / jira). Yeniden
uretim yalnizca sozlesmeden gelen alanlari tazeler:

    python contract/postman_to_openapi.py   # koleksiyon -> spec
    python qa-dashboard/build_registry.py   # spec -> registry
"""
import json
import pathlib

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
SPEC = ROOT / "contract" / "openapi.json"
EXCEPTIONS = ROOT / "contract" / "envelope_exceptions.json"
REGISTRY = HERE / "registry.json"

# Kullanicinin elle doldurdugu, uretimde ezilmemesi gereken alanlar
MANUAL_FIELDS = ("status", "verdict", "notes", "owner", "jira", "checklist")

MUTATING_METHODS = {"post", "put", "patch", "delete"}


def load_exceptions():
    if not EXCEPTIONS.exists():
        return {}
    data = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    return data.get("istisnalar", {})


def json_example(container):
    return container.get("content", {}).get("application/json", {}).get("example")


def json_schema(container):
    return container.get("content", {}).get("application/json", {}).get("schema")


def build_card(path, method, op, exceptions):
    key = op.get("operationId") or f"{method}_{path}"
    statuses = sorted(op.get("responses", {}), key=lambda c: (not c.isdigit(), c))

    success_code = next((c for c in statuses if c.isdigit() and int(c) < 400), None)
    success = op.get("responses", {}).get(success_code, {}) if success_code else {}

    params = op.get("parameters", []) or []

    card = {
        "key": key,
        "method": method.upper(),
        "path": path,
        "service": (op.get("tags") or ["Diger"])[0],
        "summary": op.get("summary", ""),
        "auth": bool(op.get("security", [{"bearerAuth": []}])),
        "mutating": method in MUTATING_METHODS,
        "pathParams": [p["name"] for p in params if p.get("in") == "path"],
        "queryParams": [
            {"name": p["name"], "example": p.get("example")}
            for p in params if p.get("in") == "query"
        ],
        "documentedStatuses": statuses,
        "requestExample": json_example(op.get("requestBody", {})),
        "expectedStatus": int(success_code) if success_code else None,
        "responseExample": json_example(success),
        "hasResponseSchema": json_schema(success) is not None,
        # Bu operasyonun bilinen envelope sapmalari (varsa panoda uyari olarak gosterilir)
        "envelopeExceptions": [
            {"anahtar": k, **v}
            for k, v in exceptions.items()
            if k.startswith(f"{method.upper()} {path} [")
        ],
    }
    return card


def build():
    if not SPEC.exists():
        raise SystemExit(f"HATA: {SPEC} yok — once: python contract/postman_to_openapi.py")

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    exceptions = load_exceptions()

    # Onceki elle girilen alanlari koru
    previous = {}
    if REGISTRY.exists():
        try:
            old = json.loads(REGISTRY.read_text(encoding="utf-8"))
            previous = {c["key"]: c for c in old.get("cards", [])}
        except (ValueError, KeyError):
            previous = {}

    cards = []
    for path in sorted(spec["paths"]):
        for method, op in sorted(spec["paths"][path].items()):
            if method == "parameters":
                continue
            card = build_card(path, method, op, exceptions)
            old = previous.get(card["key"], {})
            for field in MANUAL_FIELDS:
                if old.get(field):
                    card[field] = old[field]
            card.setdefault("status", "untested")
            card.setdefault("verdict", "")
            card.setdefault("notes", "")
            cards.append(card)

    servers = spec.get("servers") or [{}]
    payload = {
        "_meta": {
            "title": spec.get("info", {}).get("title", "API"),
            "generatedFrom": "contract/openapi.json",
            "baseUrl": servers[0].get("url", ""),
            "operations": len(cards),
            "paths": len(spec["paths"]),
            "preservedManualFields": list(MANUAL_FIELDS),
        },
        "cards": cards,
    }
    REGISTRY.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    kept = sum(1 for c in cards if c["key"] in previous)
    mutating = sum(1 for c in cards if c["mutating"])
    flagged = sum(1 for c in cards if c["envelopeExceptions"])
    print(
        f"OK -> {REGISTRY}\n"
        f"   {len(cards)} operasyon ({len(cards) - mutating} GET / {mutating} mutating)\n"
        f"   {flagged} operasyonda bilinen envelope sapmasi\n"
        f"   {kept} kartin elle girilen alanlari korundu"
    )


if __name__ == "__main__":
    build()
