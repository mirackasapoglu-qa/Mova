"""QA Endpoint Panosu — yerel sunucu (stdlib + requests).

Calistir:
    .venv/bin/python qa-dashboard/server.py
    Tarayici: http://127.0.0.1:8777

Kartlar contract/openapi.json'dan turetilir (qa-dashboard/build_registry.py).
Her kart icin: dokumante ornek istek, beklenen yanit semasi, bilinen envelope
sapmalari ve "canli test" butonu.

Guvenlik duruşu:
  - Token YALNIZCA bellekte tutulur; diske yazilmaz (NadirGold surumu .otp_state.json
    yaziyordu — bu surumde bilincli olarak kaldirildi).
  - Mutating operasyonlar (POST/PUT/PATCH/DELETE) acik onay (confirm) ister.
  - Yanit govdesindeki PII alanlari maskelenerek gosterilir.
  - Pano yalnizca 127.0.0.1'e baglanir.

API:
    GET  /api/meta                → ortam + auth durumu
    GET  /api/cards               → kart listesi (ozet)
    GET  /api/card/<key>          → kart detay
    POST /api/run/<key>           → canli test (mutating ise {"confirm": true} sart)
    POST /api/auth/otp/request    → {"email"} — OTP gonderir
    POST /api/auth/otp/verify     → {"email","otp"} — token'i belege alir
"""
import json
import os
import pathlib
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from jsonschema import Draft7Validator
except ImportError:
    Draft7Validator = None

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
REGISTRY = HERE / "registry.json"
SPEC = ROOT / "contract" / "openapi.json"
INDEX = HERE / "index.html"

BASE_URL = (os.getenv("BASE_URL") or "").rstrip("/")
TENANT_ID = os.getenv("TENANT_ID", "DEMO_TENANT")
PORT = int(os.getenv("QA_PANEL_PORT", "8777"))
TIMEOUT = int(os.getenv("TIMEOUT", "15"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/124.0 Safari/537.36"

# Oturum token'i — yalnizca bellekte
TOKEN = {"value": os.getenv("ACCESS_TOKEN", ""), "source": "env" if os.getenv("ACCESS_TOKEN") else ""}

MASK_KEYS = {
    "email", "phone", "telephone", "gsm", "iban", "taxnumber", "identitynumber",
    "tckn", "token", "accesstoken", "refreshtoken", "password", "otp",
}


def mask(value, depth=0):
    """PII alanlarini maskeleyerek govdeyi gosterilebilir hale getirir."""
    if depth > 12:
        return "..."
    if isinstance(value, dict):
        out = {}
        for key, val in value.items():
            if key.lower() in MASK_KEYS and isinstance(val, str) and val:
                out[key] = val[:2] + "***" + (val[-2:] if len(val) > 6 else "")
            else:
                out[key] = mask(val, depth + 1)
        return out
    if isinstance(value, list):
        return [mask(v, depth + 1) for v in value[:25]]
    return value


def load_registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def load_spec():
    return json.loads(SPEC.read_text(encoding="utf-8")) if SPEC.exists() else {"paths": {}}


def find_card(key):
    for card in load_registry().get("cards", []):
        if card["key"] == key:
            return card
    return None


def response_schema(spec, path, method, status):
    """Spec'te bu operasyon + status icin tanimli yanit semasi."""
    op = spec.get("paths", {}).get(path, {}).get(method.lower(), {})
    responses = op.get("responses", {})
    entry = responses.get(str(status)) or responses.get("default")
    if not entry:
        return None
    return entry.get("content", {}).get("application/json", {}).get("schema")


def run_card(card, payload):
    """Karti canliya karsi kosar ve sozlesmeye uyumunu degerlendirir."""
    # Guvenlik kapisi once: yapilandirmadan bagimsiz olarak her zaman uygulanir
    if card["mutating"] and not payload.get("confirm"):
        return {"error": "Bu operasyon veri degistirir; calistirmak icin onay gerekli.",
                "needsConfirm": True}

    if not BASE_URL:
        return {"error": "BASE_URL tanimli degil — .env doldur"}

    path = card["path"]
    for name, value in (payload.get("pathParams") or {}).items():
        path = path.replace("{" + name + "}", str(value))

    missing = re.findall(r"\{(\w+)\}", path)
    if missing:
        return {"error": f"Eksik path parametresi: {', '.join(missing)}"}

    headers = {"User-Agent": UA, "Accept": "application/json", "x-tenant-id": TENANT_ID}
    if TOKEN["value"]:
        headers["Authorization"] = f"Bearer {TOKEN['value']}"

    body = payload.get("body")
    if isinstance(body, str) and body.strip():
        try:
            body = json.loads(body)
        except ValueError as exc:
            return {"error": f"Govde gecerli JSON degil: {exc}"}

    started = time.time()
    try:
        response = requests.request(
            card["method"], f"{BASE_URL}{path}",
            headers=headers,
            params=payload.get("query") or None,
            json=body if body else None,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        return {"error": f"Istek basarisiz: {exc}"}
    elapsed = round((time.time() - started) * 1000)

    try:
        parsed = response.json()
        body_out = mask(parsed)
    except ValueError:
        parsed = None
        body_out = response.text[:2000]

    result = {
        "status": response.status_code,
        "elapsedMs": elapsed,
        "contentType": response.headers.get("Content-Type", ""),
        "body": body_out,
        "documented": str(response.status_code) in card["documentedStatuses"],
        "schemaErrors": [],
        "verdict": "",
    }

    # Sema uyumu
    schema = response_schema(load_spec(), card["path"], card["method"], response.status_code)
    if schema and parsed is not None and Draft7Validator:
        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(parsed), key=lambda e: list(e.path))
        result["schemaErrors"] = [
            {"path": "/".join(str(p) for p in e.path) or "(kok)", "message": e.message}
            for e in errors[:10]
        ]

    # Verdict
    if not result["documented"]:
        result["verdict"] = (
            f"DOKUMANTE DEGIL — {response.status_code} sozlesmede tanimli degil "
            f"(dokumante: {', '.join(card['documentedStatuses'])})"
        )
    elif result["schemaErrors"]:
        result["verdict"] = f"SEMA SAPMASI — {len(result['schemaErrors'])} alan uyusmuyor"
    elif response.status_code >= 500:
        result["verdict"] = "SUNUCU HATASI"
    else:
        result["verdict"] = "UYUMLU — status ve sema sozlesmeye uygun"
    return result


def otp_request(email):
    if not BASE_URL:
        return {"error": "BASE_URL tanimli degil"}
    try:
        response = requests.post(
            f"{BASE_URL}/v1/auth/otp/request",
            headers={"User-Agent": UA, "x-tenant-id": TENANT_ID},
            json={"email": email}, timeout=TIMEOUT,
        )
        return {"status": response.status_code, "body": mask(response.json())}
    except (requests.RequestException, ValueError) as exc:
        return {"error": str(exc)}


def otp_verify(email, otp):
    if not BASE_URL:
        return {"error": "BASE_URL tanimli degil"}
    try:
        response = requests.post(
            f"{BASE_URL}/v1/auth/otp/verify",
            headers={"User-Agent": UA, "x-tenant-id": TENANT_ID},
            json={"email": email, "otp": otp, "deviceInfo": "qa-panel"}, timeout=TIMEOUT,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        return {"error": str(exc)}

    token = (data.get("data") or {}).get("accessToken")
    if token:
        TOKEN["value"] = token
        TOKEN["source"] = "otp"
        return {"status": response.status_code, "authed": True}
    return {"status": response.status_code, "authed": False, "body": mask(data)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # sessiz

    def _send(self, payload, code=200, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            if not INDEX.exists():
                return self._send({"error": "index.html yok"}, 404)
            return self._send(INDEX.read_bytes(), content_type="text/html; charset=utf-8")

        if self.path == "/api/meta":
            registry = load_registry()
            return self._send({
                "title": registry["_meta"].get("title", "API"),
                "baseUrl": BASE_URL,
                "tenantId": TENANT_ID,
                "authed": bool(TOKEN["value"]),
                "authSource": TOKEN["source"],
                "operations": registry["_meta"].get("operations"),
                "paths": registry["_meta"].get("paths"),
            })

        if self.path == "/api/cards":
            cards = load_registry().get("cards", [])
            return self._send([{
                "key": c["key"], "method": c["method"], "path": c["path"],
                "service": c["service"], "summary": c["summary"],
                "mutating": c["mutating"], "status": c.get("status", "untested"),
                "flagged": bool(c.get("envelopeExceptions")),
            } for c in cards])

        if self.path.startswith("/api/card/"):
            key = urllib_unquote(self.path[len("/api/card/"):])
            card = find_card(key)
            return self._send(card or {"error": "kart bulunamadi"}, 200 if card else 404)

        return self._send({"error": "bulunamadi"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            return self._send({"error": "gecersiz JSON"}, 400)

        if self.path == "/api/auth/otp/request":
            return self._send(otp_request(payload.get("email", "")))

        if self.path == "/api/auth/otp/verify":
            return self._send(otp_verify(payload.get("email", ""), payload.get("otp", "")))

        if self.path == "/api/auth/token":
            TOKEN["value"] = payload.get("token", "")
            TOKEN["source"] = "manual" if TOKEN["value"] else ""
            return self._send({"authed": bool(TOKEN["value"])})

        if self.path.startswith("/api/run/"):
            key = urllib_unquote(self.path[len("/api/run/"):])
            card = find_card(key)
            if not card:
                return self._send({"error": "kart bulunamadi"}, 404)
            return self._send(run_card(card, payload))

        return self._send({"error": "bulunamadi"}, 404)


def urllib_unquote(text):
    import urllib.parse
    return urllib.parse.unquote(text.split("?")[0])


def main():
    if not REGISTRY.exists():
        raise SystemExit("HATA: registry.json yok — once: python qa-dashboard/build_registry.py")
    meta = load_registry()["_meta"]
    print(f"QA Panosu — {meta.get('title')}")
    print(f"  operasyon : {meta.get('operations')} ({meta.get('paths')} path)")
    print(f"  hedef     : {BASE_URL or '(BASE_URL tanimli degil — .env doldur)'}")
    print(f"  tenant    : {TENANT_ID}")
    print(f"  auth      : {'token yuklu (' + TOKEN['source'] + ')' if TOKEN['value'] else 'yok — panelden OTP ile giris yap'}")
    print(f"\n  http://127.0.0.1:{PORT}\n")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
