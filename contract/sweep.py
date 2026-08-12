"""Canli GET taramasi — her operasyonu cagirir, sozlesmeye uyumunu tablolar.

Schemathesis'in ozet ciktisinin aksine burada HER operasyon icin tek satir alirsin:
alinan status, dokumante mi, envelope uyumu, sema sapmasi, sure ve govde onizlemesi.

    .venv/bin/python contract/sweep.py                    # tablo (stdout)
    .venv/bin/python contract/sweep.py --md rapor.md      # markdown rapor
    .venv/bin/python contract/sweep.py --service Customers
    .venv/bin/python contract/sweep.py --no-resolve        # yer tutucu ID (eski davranis)

Path parametreleri VARSAYILAN OLARAK canlidan cozumlenir (qa_core.resolver): yer
tutucu ID kullanildiginda uclar 404 doner, 404 sozlesmeye uygun oldugu icin sonuc
"uyumlu" gorunur ve yanit govdesi hic dogrulanmaz. Cozumleme bu kor noktayi kapatir
— ilk kullanimda 19 gizli sema sapmasi ortaya cikardi.

GUVENLIK: yalnizca GET. Mutating metotlar bilincli olarak hic denenmez.
Token: .env'deki ACCESS_TOKEN, yoksa TEST_EMAIL+OTP_CODE ile OTP akisi.
PII maskelenir.
"""
import argparse
import json
import os
import pathlib
import re
import sys
import time

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from jsonschema import Draft7Validator

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
SPEC = HERE / "openapi.json"
SCHEMAS = ROOT / "schemas"

sys.path.insert(0, str(ROOT))
from qa_core.resolver import PathParamResolver, PLACEHOLDER_ID  # noqa: E402

BASE_URL = (os.getenv("BASE_URL") or "").rstrip("/")
TENANT_ID = os.getenv("TENANT_ID", "DEMO_TENANT")
TIMEOUT = int(os.getenv("TIMEOUT", "15"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/124.0 Safari/537.36"

MASK_KEYS = {"email", "phone", "iban", "taxnumber", "identitynumber",
             "token", "accesstoken", "refreshtoken", "password", "otp"}


def mask(value, depth=0):
    if depth > 8:
        return "..."
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in MASK_KEYS and v else mask(v, depth + 1))
                for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v, depth + 1) for v in value[:3]]
    return value


def get_token():
    token = os.getenv("ACCESS_TOKEN")
    if token:
        return token, "env"
    email, otp = os.getenv("TEST_EMAIL"), os.getenv("OTP_CODE")
    if not (email and otp):
        return None, "yok"
    headers = {"User-Agent": UA, "x-tenant-id": TENANT_ID}
    requests.post(f"{BASE_URL}/v1/auth/otp/request", json={"email": email},
                  headers=headers, timeout=TIMEOUT)
    resp = requests.post(f"{BASE_URL}/v1/auth/otp/verify", headers=headers,
                         json={"email": email, "otp": otp, "deviceInfo": "qa-sweep"},
                         timeout=TIMEOUT)
    token = (resp.json().get("data") or {}).get("accessToken")
    return token, ("otp" if token else "basarisiz")


def query_params(op):
    """Dokumante ornekli query parametreleri."""
    return {p["name"]: p["example"] for p in (op.get("parameters") or [])
            if p.get("in") == "query" and "example" in p}


def build_url(path, resolver=None):
    """Path parametrelerini cozumler; cozulemezse yer tutucuya duser.

    Doner: (url, id_durumu) — id_durumu: 'gercek' | 'yer tutucu' | '-'
    """
    if "{" not in path:
        return path, "-"
    if resolver is None:
        return re.sub(r"\{(\w+)\}", PLACEHOLDER_ID, path), "yer tutucu"

    result = resolver.resolve(path)
    url = resolver.fill(path, result["values"])
    status = "gercek" if not result["error"] else (
        "kismi" if result["values"] else "yer tutucu")
    return url, status


def preview(body, limit=90):
    text = json.dumps(mask(body), ensure_ascii=False) if body is not None else ""
    text = re.sub(r"\s+", " ", text)
    return text[:limit] + ("…" if len(text) > limit else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--service", help="yalnizca bu tag/servis")
    ap.add_argument("--md", help="markdown raporu bu dosyaya yaz")
    ap.add_argument("--limit", type=int, help="ilk N operasyon")
    ap.add_argument("--no-resolve", action="store_true",
                    help="path parametrelerini canlidan cozumleme (yer tutucu ID kullan)")
    args = ap.parse_args()

    if not BASE_URL:
        sys.exit("HATA: BASE_URL tanimli degil (.env)")
    if not SPEC.exists():
        sys.exit("HATA: contract/openapi.json yok — once postman_to_openapi.py")

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    success_v = Draft7Validator(json.loads((SCHEMAS / "success.json").read_text(encoding="utf-8")))
    error_v = Draft7Validator(json.loads((SCHEMAS / "error.json").read_text(encoding="utf-8")))

    token, source = get_token()
    print(f"Hedef : {BASE_URL}\nTenant: {TENANT_ID}\nToken : {source}\n", file=sys.stderr)

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json",
                            "x-tenant-id": TENANT_ID})
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})

    resolver = None if args.no_resolve else PathParamResolver(
        BASE_URL, headers=dict(session.headers), timeout=TIMEOUT)

    rows = []
    ops = [(p, o) for p in sorted(spec["paths"]) for m, o in spec["paths"][p].items()
           if m == "get"]
    if args.service:
        ops = [(p, o) for p, o in ops if (o.get("tags") or [""])[0] == args.service]
    if args.limit:
        ops = ops[:args.limit]

    for path, op in ops:
        url, id_state = build_url(path, resolver)
        params = query_params(op)
        started = time.time()
        try:
            resp = session.get(f"{BASE_URL}{url}", params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            rows.append({"path": path, "service": (op.get("tags") or ["-"])[0],
                         "id": id_state, "status": "ERR", "documented": "-",
                         "envelope": "-", "schema": "-", "ms": "-",
                         "preview": str(exc)[:80]})
            continue
        ms = round((time.time() - started) * 1000)

        documented = sorted(op.get("responses", {}))
        is_doc = str(resp.status_code) in documented

        try:
            body = resp.json()
        except ValueError:
            body = None

        # envelope uyumu
        if body is None:
            env = "—"
        else:
            validator = success_v if resp.status_code < 400 else error_v
            env = "OK" if not list(validator.iter_errors(body)) else "SAPMA"

        # spec sema uyumu (bu status icin tanimliysa)
        entry = op.get("responses", {}).get(str(resp.status_code), {})
        schema = entry.get("content", {}).get("application/json", {}).get("schema")
        if schema is None:
            sch = "—"
        elif body is None:
            sch = "—"
        else:
            errs = list(Draft7Validator(schema).iter_errors(body))
            sch = "OK" if not errs else f"{len(errs)} sapma"

        rows.append({
            "path": path, "service": (op.get("tags") or ["-"])[0], "id": id_state,
            "status": resp.status_code, "documented": "evet" if is_doc else "HAYIR",
            "envelope": env, "schema": sch, "ms": ms, "preview": preview(body),
        })

    # ---- tablo ----
    width = max(len(r["path"]) for r in rows) if rows else 20
    header = (f"{'ENDPOINT':<{width}}  {'ID':<11}  {'HTTP':>4}  {'DOK':<5}  "
              f"{'ENVELOPE':<8}  {'SEMA':<9}  {'MS':>5}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['path']:<{width}}  {r['id']:<11}  {str(r['status']):>4}  "
              f"{r['documented']:<5}  {r['envelope']:<8}  {str(r['schema']):<9}  "
              f"{str(r['ms']):>5}")

    total = len(rows)
    undoc = sum(1 for r in rows if r["documented"] == "HAYIR")
    envbad = sum(1 for r in rows if r["envelope"] == "SAPMA")
    schbad = sum(1 for r in rows if isinstance(r["schema"], str) and "sapma" in r["schema"])
    ok2xx = sum(1 for r in rows if isinstance(r["status"], int) and r["status"] < 300)
    real = sum(1 for r in rows if r["id"] == "gercek")
    ph = sum(1 for r in rows if r["id"] in ("yer tutucu", "kismi"))
    print(f"\nTOPLAM {total} | 2xx {ok2xx} | dokumante degil {undoc} | "
          f"envelope sapmasi {envbad} | sema sapmasi {schbad}")
    if resolver is not None:
        print(f"ID cozumleme: {real} gercek, {ph} cozulemedi "
              f"({resolver.requests_made} ek istek, {len(resolver._cache)} koleksiyon)")
        if ph:
            print("  ! cozulemeyen uclar 404 doner ve sapmalari MASKELER — "
                  "ilgili koleksiyonda kayit yok demektir")

    if args.md:
        lines = [
            f"# Canli GET Taramasi — {BASE_URL}", "",
            f"Tarih: {time.strftime('%Y-%m-%d %H:%M')} · Tenant: `{TENANT_ID}` · Token: {source}", "",
            f"**{total}** operasyon · 2xx **{ok2xx}** · dokümante değil **{undoc}** · "
            f"envelope sapması **{envbad}** · şema sapması **{schbad}**", "",
            "| Endpoint | Servis | ID | HTTP | Dokümante | Envelope | Şema | ms | Yanıt |",
            "|---|---|---|---:|---|---|---|---:|---|",
        ]
        for r in rows:
            prev = r["preview"].replace("|", "\\|")
            lines.append(f"| `{r['path']}` | {r['service']} | {r['id']} | {r['status']} | "
                         f"{r['documented']} | {r['envelope']} | {r['schema']} | {r['ms']} | `{prev}` |")
        pathlib.Path(args.md).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nMarkdown -> {args.md}", file=sys.stderr)


if __name__ == "__main__":
    main()
