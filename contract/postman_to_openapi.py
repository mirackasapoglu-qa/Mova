"""Postman koleksiyonundan OpenAPI 3.0 sozlesmesi uretir -> contract/openapi.json

Neden: OPRAS servisleri canli bir docs-json/swagger yayinlamiyor. Elimizdeki en
zengin sozlesme kaynagi Postman koleksiyonu: 391 request, 166 benzersiz path ve
**1041 kayitli ornek yanit** (200/201 + 400/401/403/404/409/422/429 hata yollari).
Bu script o ornekleri JSON Schema'ya cevirip Schemathesis'in tuketebilecegi tek
bir bundle uretir.

Sema cikarimi kurallari (bilerek muhafazakar):
  - `required` = ayni status kodunun TUM orneklerinde bulunan alanlar (kesisim).
    Tek ornekte olmayan alan zorunlu sayilmaz -> yanlis pozitif contract hatasi olmaz.
  - `additionalProperties` serbest birakilir -> API'ye yeni alan eklenmesi
    sozlesmeyi kirmaz; sadece KAYIP alan ve TIP DEGISIMI yakalanir.
  - Farkli orneklerde tip catisirsa alan "any" olur (uydurma kisit koymayiz).
  - null gorulen alan `nullable: true` alir.

Kaynak koleksiyon elle bakimli bir dokumandir; canli API ondan KAYABILIR.
Contract kosumunun amaci zaten tam olarak bu kaymayi yakalamaktir.

Kullanim:
    python contract/postman_to_openapi.py
    python contract/postman_to_openapi.py --collection <yol> --out <yol>
"""
import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
DEFAULT_COLLECTION = HERE / "opras.postman_collection.json"
DEFAULT_OUT = HERE / "openapi.json"

# Koleksiyon degiskeni -> OpenAPI path parametresi adi
# {{last_user_id}} -> {userId} ;  {{customerId}} -> {customerId}
VAR_RE = re.compile(r"\{\{(\w+)\}\}")

# URL'in basindaki host degiskeni. Yalnizca gateway uzerinden gecen istekler
# spec'e girer; {{project_url}} / {{file_url}} gibi degiskenler mikroservise
# DOGRUDAN gider (gateway'i bypass eder) — farkli bir sunucu olduklari icin
# gateway sozlesmesine karistirilirsa sahte contract hatasi uretirler.
HOST_VAR_RE = re.compile(r"^\{\{(\w+)\}\}")
GATEWAY_HOST_VARS = {"base_url", "baseUrl", "gatewayUrl"}


def to_param_name(name):
    """Postman degisken adini OpenAPI parametre adina cevirir."""
    if name.startswith("last_"):
        name = name[len("last_"):]
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


def host_var(raw):
    """URL'in basindaki host degiskenini doner ('base_url' gibi), yoksa None."""
    match = HOST_VAR_RE.match((raw or "").strip())
    return match.group(1) if match else None


def norm_path(raw):
    """'{{base_url}}/v1/users/{{last_user_id}}?x=1' -> '/v1/users/{userId}'"""
    if not raw:
        return None
    path = raw.split("?", 1)[0].strip()
    path = HOST_VAR_RE.sub("", path)  # bastaki host degiskenini at
    path = VAR_RE.sub(lambda m: "{" + to_param_name(m.group(1)) + "}", path)
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def path_params(path):
    return re.findall(r"\{(\w+)\}", path)


# ---------------------------------------------------------------- sema cikarimi

ANY = {}


def infer(value):
    """Tek bir JSON degerinden sema uretir."""
    if value is None:
        return {"nullable": True}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": ANY.copy()}
        items = infer(value[0])
        for v in value[1:]:
            items = merge(items, infer(v))
        return {"type": "array", "items": items}
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {k: infer(v) for k, v in value.items()},
            "required": sorted(value.keys()),
        }
    return ANY.copy()


def merge(a, b):
    """Iki semayi birlestirir: required = kesisim, tip catismasi -> any."""
    # sadece nullable bilgisi tasiyan taraf (ornekte null gelmis)
    if a == {"nullable": True}:
        out = dict(b)
        out["nullable"] = True
        return out
    if b == {"nullable": True}:
        out = dict(a)
        out["nullable"] = True
        return out
    if not a or not b:
        return ANY.copy()

    ta, tb = a.get("type"), b.get("type")
    if ta != tb:
        # integer + number -> number (uyumlu daraltma)
        if {ta, tb} == {"integer", "number"}:
            out = {"type": "number"}
        else:
            out = ANY.copy()
        if a.get("nullable") or b.get("nullable"):
            out["nullable"] = True
        return out

    out = {"type": ta}
    if a.get("nullable") or b.get("nullable"):
        out["nullable"] = True

    if ta == "object":
        props = {}
        # sorted(): set uzerinde dolasmak hash randomizasyonu yuzunden her kosumda
        # farkli sira uretir -> uretilen spec deterministik olmaz, CI surekli kirilir
        for key in sorted(set(a.get("properties", {})) | set(b.get("properties", {}))):
            pa = a.get("properties", {}).get(key)
            pb = b.get("properties", {}).get(key)
            props[key] = merge(pa, pb) if pa is not None and pb is not None else (pa or pb)
        out["properties"] = props
        # KESISIM: sadece her iki ornekte de bulunan alanlar zorunlu
        req = sorted(set(a.get("required", [])) & set(b.get("required", [])))
        if req:
            out["required"] = req
    elif ta == "array":
        out["items"] = merge(a.get("items", ANY), b.get("items", ANY))
    return out


def parse_json(text):
    if not text or not text.strip():
        return None, False
    try:
        return json.loads(text), True
    except (ValueError, TypeError):
        return None, False


# ---------------------------------------------------------------- koleksiyon gezme

def walk(items, trail=()):
    """Klasor agacini duzlestirir: (folder_trail, item) uretir."""
    for it in items or []:
        if "item" in it:
            yield from walk(it["item"], trail + (it.get("name", ""),))
        else:
            yield trail, it


def tag_of(trail):
    """'01-Auth' -> 'Auth' ; ic klasorler ust klasore baglanir."""
    if not trail:
        return "default"
    return re.sub(r"^\d+[-_]\s*", "", trail[0]).strip() or "default"


def build_operation(item, trail, path):
    req = item.get("request", {})
    method = (req.get("method") or "GET").lower()
    url = req.get("url") or {}

    op = {
        "operationId": None,  # asagida method+path'ten uretilir
        "tags": [tag_of(trail)],
        "summary": item.get("name") or f"{method.upper()} {path}",
        "responses": {},
    }
    desc = req.get("description") or item.get("description")
    if isinstance(desc, dict):
        desc = desc.get("content")
    if desc:
        op["description"] = str(desc)[:2000]

    # --- parametreler ---
    params = []
    for name in path_params(path):
        params.append({
            "name": name, "in": "path", "required": True,
            "schema": {"type": "string"},
        })

    if isinstance(url, dict):
        for q in url.get("query") or []:
            if q.get("disabled"):
                continue
            key = q.get("key")
            if not key:
                continue
            value = VAR_RE.sub("", q.get("value") or "")
            schema = {"type": "string"}
            if value.isdigit():
                schema = {"type": "integer"}
            entry = {"name": key, "in": "query", "required": False, "schema": schema}
            if value:
                entry["example"] = int(value) if value.isdigit() else value
            params.append(entry)

    for h in req.get("header") or []:
        key = (h.get("key") or "").lower()
        if h.get("disabled") or key in ("content-type", "authorization", "accept"):
            continue
        params.append({
            "name": h.get("key"), "in": "header", "required": False,
            "schema": {"type": "string"},
            "example": VAR_RE.sub("", h.get("value") or "") or None,
        })

    # None example'lari temizle
    for p in params:
        if p.get("example") is None:
            p.pop("example", None)
    if params:
        op["parameters"] = params

    # --- request body ---
    body = req.get("body") or {}
    raw = body.get("raw") if body.get("mode") == "raw" else None
    parsed, ok = parse_json(raw)
    if ok:
        op["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": infer(parsed),
                    "example": parsed,
                }
            },
        }

    # --- yanitlar (ornek kayitlarindan) ---
    by_code = {}
    for resp in item.get("response") or []:
        code = str(resp.get("code") or "")
        if not code:
            continue
        parsed, ok = parse_json(resp.get("body"))
        entry = by_code.setdefault(code, {"schema": None, "example": None, "name": resp.get("name")})
        if ok:
            entry["schema"] = infer(parsed) if entry["schema"] is None else merge(entry["schema"], infer(parsed))
            if entry["example"] is None:
                entry["example"] = parsed

    for code, entry in sorted(by_code.items()):
        response = {"description": entry["name"] or f"HTTP {code}"}
        if entry["schema"] is not None:
            content = {"schema": entry["schema"]}
            if entry["example"] is not None:
                content["example"] = entry["example"]
            response["content"] = {"application/json": content}
        op["responses"][code] = response

    if not op["responses"]:
        op["responses"]["200"] = {"description": "OK"}

    return method, op


def merge_operation(existing, new):
    """Ayni method+path birden fazla klasorde geciyorsa yanitlari birlestir."""
    for code, resp in new.get("responses", {}).items():
        if code not in existing.get("responses", {}):
            existing.setdefault("responses", {})[code] = resp
        else:
            cur = existing["responses"][code]
            cur_schema = cur.get("content", {}).get("application/json", {}).get("schema")
            new_schema = resp.get("content", {}).get("application/json", {}).get("schema")
            if cur_schema and new_schema:
                cur["content"]["application/json"]["schema"] = merge(cur_schema, new_schema)
            elif new_schema and not cur_schema:
                cur["content"] = resp["content"]
    if "requestBody" not in existing and "requestBody" in new:
        existing["requestBody"] = new["requestBody"]
    return existing


def build(collection_path, out_path, base_url):
    collection = json.loads(pathlib.Path(collection_path).read_text(encoding="utf-8"))
    info = collection.get("info", {})

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": info.get("name", "API"),
            "description": (
                "Postman koleksiyonundan uretilmistir "
                "(contract/postman_to_openapi.py). Yanit semalari kayitli ornek "
                "yanitlardan cikarilmistir; canli API bu sozlesmeden kayabilir — "
                "contract kosumunun amaci o kaymayi yakalamaktir."
            ),
            "version": "1.0.0",
        },
        "servers": [{"url": base_url}],
        "tags": [],
        "paths": {},
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
        "security": [{"bearerAuth": []}],
    }

    seen_tags, op_ids, n_req, n_examples = [], set(), 0, 0
    skipped = []

    for trail, item in walk(collection.get("item", [])):
        req = item.get("request")
        if not req:
            continue
        url = req.get("url") or {}
        raw = url.get("raw") if isinstance(url, dict) else url
        path = norm_path(raw)
        if not path:
            continue

        # Gateway disi (dogrudan servise giden) istekleri spec'e alma
        hvar = host_var(raw)
        if hvar and hvar not in GATEWAY_HOST_VARS:
            skipped.append(f"{req.get('method', 'GET')} {path}  [{{{{{hvar}}}}}]")
            continue

        n_req += 1
        n_examples += len(item.get("response") or [])

        method, op = build_operation(item, trail, path)

        tag = op["tags"][0]
        if tag not in seen_tags:
            seen_tags.append(tag)

        # benzersiz operationId
        base_id = re.sub(r"\W+", "_", f"{method}_{path}").strip("_").lower()
        op_id, i = base_id, 2
        while op_id in op_ids:
            op_id, i = f"{base_id}_{i}", i + 1
        op_ids.add(op_id)
        op["operationId"] = op_id

        entry = spec["paths"].setdefault(path, {})
        if method in entry:
            merge_operation(entry[method], op)
        else:
            entry[method] = op

    spec["tags"] = [{"name": t} for t in seen_tags]

    out = pathlib.Path(out_path)
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    n_ops = sum(len([m for m in v if m != "parameters"]) for v in spec["paths"].values())
    print(
        f"OK -> {out}\n"
        f"   {n_req} request -> {len(spec['paths'])} path / {n_ops} operasyon\n"
        f"   {n_examples} ornek yanit islendi, {len(seen_tags)} tag\n"
        f"   server: {base_url}"
    )
    if skipped:
        print(f"   ATLANDI ({len(skipped)} gateway disi istek — dogrudan servise gidiyor):")
        for entry in skipped:
            print(f"     - {entry}")
    return spec


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--collection", default=str(DEFAULT_COLLECTION))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument(
        "--base-url",
        default=None,
        help="servers[0].url (varsayilan: .env / BASE_URL, o da yoksa koleksiyon base_url degiskeni)",
    )
    args = ap.parse_args()

    base_url = args.base_url
    if not base_url:
        import os
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        base_url = os.getenv("BASE_URL")
    if not base_url:
        collection = json.loads(pathlib.Path(args.collection).read_text(encoding="utf-8"))
        for v in collection.get("variable", []):
            if v.get("key") == "base_url":
                base_url = v.get("value")
                break
    if not base_url:
        print("HATA: BASE_URL bulunamadi (.env / --base-url / koleksiyon degiskeni)", file=sys.stderr)
        return 1

    build(args.collection, args.out, base_url.rstrip("/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
