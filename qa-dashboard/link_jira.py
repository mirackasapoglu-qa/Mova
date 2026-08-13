"""Jira kartlarini endpoint'lere baglar -> registry.json'daki `jira` alani.

Kartlarin ozet/aciklamalarinda endpoint referanslari yazili
(orn. "Endpoint GET /v1/requests/:id/activities"). Bu betik TP projesindeki tum
kartlari cekip bu referanslari cikarir, sozlesmedeki operasyonlarla eslestirir ve
registry'ye isler. Boylece panoda "bu ucu hangi kartlar kapsiyor" gorunur.

Eslestirme yolu SEKIL uzerinden yapilir: parametre adlari onemsizdir, yapisi onemlidir.
    kart : GET /api/projects/:id/participants
    spec : GET /v1/projects/{projectId}/participants
    sekil: GET /v1/projects/{}/participants          -> eslesir

Normalize edilenler:
  - /api/... on eki  -> /v1/...   (kartlarda eski/FE adlandirmasi)
  - :param, {param}  -> {}
  - somut UUID/sayi  -> {}        (kartlarda ornek deger yazilmis olabilir)

Kullanim:
    .venv/bin/python qa-dashboard/link_jira.py            # baglar + registry'yi gunceller
    .venv/bin/python qa-dashboard/link_jira.py --dry-run  # sadece rapor, yazma
    .venv/bin/python qa-dashboard/link_jira.py --jql "project = TP AND status = Test"

Gerekli: .env icinde JIRA_BASE, JIRA_EMAIL, JIRA_API_TOKEN
"""
import argparse
import json
import os
import pathlib
import re
import sys
from collections import Counter, defaultdict

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
REGISTRY = HERE / "registry.json"
JIRA_CARDS = HERE / "jira_cards.json"
UNMATCHED_REPORT = ROOT / "reports" / "jira-unmatched.md"

JIRA_BASE = (os.getenv("JIRA_BASE") or "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN = os.getenv("JIRA_API_TOKEN", "")
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "TP")

ENDPOINT_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_\-/{}:.]+)")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
NUMERIC_RE = re.compile(r"^\d+$")

# Kartlarda gecen ama tek basina anlamli olmayan yollar (gurultuyu azaltir)
IGNORED_SHAPES = {"/v1", "/v1/"}


def adf_text(node):
    """Jira ADF aciklamasini duz metne cevirir."""
    out = []

    def walk(item):
        if isinstance(item, dict):
            if item.get("type") == "text":
                out.append(item.get("text", ""))
            for value in item.values():
                walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)

    walk(node)
    return " ".join(out)


def adf_blocks(node):
    """ADF'yi yapisal bloklara ayirir: kod bloklari ayri tutulur.

    Kartlar beklenen response'u kod blogu olarak yaziyor; duz metne cevirirken
    bu yapi kayboluyordu. Karsilastirma icin JSON'i ayri saklamak gerekiyor.
    """
    code, tables = [], []

    def walk(item):
        if isinstance(item, dict):
            kind = item.get("type")
            if kind == "codeBlock":
                text = "".join(c.get("text", "") for c in item.get("content", []))
                if text.strip():
                    code.append(text)
                return
            if kind == "table":
                cells = []

                def collect(node2):
                    if isinstance(node2, dict):
                        if node2.get("type") == "text":
                            cells.append(node2.get("text", ""))
                        for value in node2.values():
                            collect(value)
                    elif isinstance(node2, list):
                        for value in node2:
                            collect(value)

                collect(item)
                if cells:
                    tables.append(" | ".join(cells))
                return
            for value in item.values():
                walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)

    walk(node)
    return code, tables


def classify_code_block(text):
    """Kod blogunu siniflandirir: response / request / endpoint / parca."""
    stripped = text.strip()

    if ENDPOINT_RE.match(stripped):
        return "endpoint", None

    try:
        parsed = json.loads(stripped)
    except ValueError:
        return "parca", None

    if isinstance(parsed, dict) and "success" in parsed:
        return "response", parsed
    if isinstance(parsed, dict) and "data" in parsed:
        return "response", parsed
    return "request", parsed


def shape(path):
    """Yolu karsilastirilabilir bicime indirger."""
    cleaned = path.split("?")[0].split("#")[0].rstrip("/")
    cleaned = re.sub(r"^/api(?=/)", "", cleaned)      # /api/... -> /...
    if not cleaned.startswith("/v1"):
        cleaned = "/v1" + cleaned                      # /projects -> /v1/projects

    segments = []
    for seg in cleaned.strip("/").split("/"):
        if seg.startswith(":") or (seg.startswith("{") and seg.endswith("}")):
            segments.append("{}")
        elif UUID_RE.match(seg) or NUMERIC_RE.match(seg):
            segments.append("{}")
        else:
            segments.append(seg)
    return "/" + "/".join(segments)


def fetch_issues(jql):
    """TP kartlarini sayfalayarak ceker."""
    if not (JIRA_BASE and JIRA_EMAIL and JIRA_TOKEN):
        sys.exit("HATA: JIRA_BASE / JIRA_EMAIL / JIRA_API_TOKEN tanimli degil (.env)")

    issues, token = [], None
    while True:
        params = {"jql": jql, "maxResults": 100,
                  "fields": "summary,status,issuetype,description,assignee,parent"}
        if token:
            params["nextPageToken"] = token
        resp = requests.get(f"{JIRA_BASE}/rest/api/3/search/jql",
                            auth=(JIRA_EMAIL, JIRA_TOKEN),
                            headers={"Accept": "application/json"},
                            params=params, timeout=60)
        if resp.status_code != 200:
            sys.exit(f"HATA: Jira {resp.status_code} — {resp.text[:300]}")
        payload = resp.json()
        issues += payload.get("issues", [])
        token = payload.get("nextPageToken")
        if payload.get("isLast") or not token:
            break
        print(f"  … {len(issues)} kart", file=sys.stderr)
    return issues


# Destekleyici uclar: kartlarda baglam icin anilir, kartin konusu degildir
SUPPORTING_RE = re.compile(r"^/v1/(lookups|auth|sidebar|health)\b")


def extract_endpoints(issue):
    """Karttan (metot, sekil) ciftlerini GECIS SIRASIYLA cikarir.

    Sira onemli: kartin BIRINCIL ucunu belirlemek icin kullanilir. Bir kart
    genelde birden fazla uc anar — biri konusu, digerleri destekleyici
    (dropdown icin /v1/lookups/enums gibi). Kartin beklenen yanit ornegi
    yalnizca BIRINCIL uca aittir; hepsine uygulamak sahte "uyumsuz" uretir.
    """
    fields = issue["fields"]
    summary = fields.get("summary") or ""
    text = summary + " \n " + adf_text(fields.get("description"))

    ordered, seen = [], set()
    for method, path in ENDPOINT_RE.findall(text):
        normalized = shape(path)
        if normalized in IGNORED_SHAPES:
            continue
        pair = (method.upper(), normalized)
        if pair not in seen:
            seen.add(pair)
            ordered.append(pair)
    return ordered, summary


def pick_primary(ordered, summary):
    """Kartin birincil ucu: ozette gecen; yoksa aciklamada ilk gecen (destekleyiciler haric)."""
    in_summary = {(m.upper(), shape(p)) for m, p in ENDPOINT_RE.findall(summary)}
    for pair in ordered:
        if pair in in_summary:
            return pair
    for pair in ordered:
        if not SUPPORTING_RE.match(pair[1]):
            return pair
    return ordered[0] if ordered else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jql", default=f"project = {PROJECT_KEY} ORDER BY created ASC")
    ap.add_argument("--dry-run", action="store_true", help="registry'ye yazma, sadece raporla")
    args = ap.parse_args()

    if not REGISTRY.exists():
        sys.exit("HATA: registry.json yok — once: python qa-dashboard/build_registry.py")

    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    cards = data["cards"]

    # sekil -> operasyon anahtarlari
    index = defaultdict(list)
    for card in cards:
        index[(card["method"], shape(card["path"]))].append(card["key"])

    print(f"registry : {len(cards)} operasyon, {len(index)} benzersiz sekil")
    print(f"jira     : {JIRA_BASE} — {args.jql}", file=sys.stderr)

    issues = fetch_issues(args.jql)
    print(f"cekilen kart: {len(issues)}")

    links = defaultdict(list)          # operasyon anahtari -> kart listesi
    unmatched = Counter()              # eslesmeyen sekil -> kac kart
    unmatched_examples = defaultdict(set)
    with_endpoint = matched_cards = 0
    jira_cards = []                    # kart merkezli gorunum icin

    for issue in issues:
        fields = issue["fields"]
        entry = {
            "key": issue["key"],
            "summary": fields.get("summary", ""),
            "status": (fields.get("status") or {}).get("name", ""),
            "type": (fields.get("issuetype") or {}).get("name", ""),
            "assignee": (fields.get("assignee") or {}).get("displayName", ""),
            "parent": (fields.get("parent") or {}).get("key", ""),
        }

        code_blocks, tables = adf_blocks(fields.get("description"))
        classified, expected_response, request_body = [], None, None
        for block in code_blocks:
            kind, parsed = classify_code_block(block)
            classified.append({"kind": kind, "text": block[:2500]})
            if kind == "response" and expected_response is None:
                expected_response = parsed
            elif kind == "request" and request_body is None:
                request_body = parsed

        entry_detail = {
            "description": adf_text(fields.get("description"))[:4000],
            "blocks": classified,
            "tables": tables[:6],
            "expectedResponse": expected_response,
            "requestBody": request_body,
        }

        endpoints, summary_text = extract_endpoints(issue)
        primary = pick_primary(endpoints, summary_text)
        card_endpoints = []
        hit = False

        if endpoints:
            with_endpoint += 1
            for method, normalized in endpoints:
                op_keys = index.get((method, normalized)) or []
                if op_keys:
                    hit = True
                    for op_key in op_keys:
                        links[op_key].append(entry)
                else:
                    unmatched[f"{method} {normalized}"] += 1
                    unmatched_examples[f"{method} {normalized}"].add(issue["key"])
                card_endpoints.append({
                    "method": method, "shape": normalized, "operations": op_keys,
                    "primary": (method, normalized) == primary,
                })
            matched_cards += 1 if hit else 0

        jira_cards.append({**entry, **entry_detail,
                           "endpoints": card_endpoints, "matched": hit})

    total_links = sum(len(v) for v in links.values())
    print(f"\nendpoint gecen kart : {with_endpoint}")
    print(f"eslesen kart        : {matched_cards} "
          f"(%{round(100 * matched_cards / max(with_endpoint, 1))})")
    print(f"kart baglanan uc    : {len(links)}/{len(cards)} "
          f"(%{round(100 * len(links) / max(len(cards), 1))})")
    print(f"toplam baglanti     : {total_links}")

    # --- registry'ye isle ---
    if not args.dry_run:
        for card in cards:
            entries = links.get(card["key"], [])
            # ayni kart birden fazla kez gecebilir — tekille, key'e gore sirala
            seen, unique = set(), []
            for entry in sorted(entries, key=lambda e: e["key"]):
                if entry["key"] not in seen:
                    seen.add(entry["key"])
                    unique.append(entry)
            if unique:
                card["jira"] = unique
            else:
                card.pop("jira", None)

        data["_meta"]["jiraLinkedAt"] = f"{JIRA_BASE} · {args.jql}"
        data["_meta"]["jiraLinkedOperations"] = len(links)
        REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nOK -> {REGISTRY}")

        # Kart merkezli gorunum: panoda "karttan uca" gezinmek icin
        JIRA_CARDS.write_text(json.dumps({
            "_meta": {"base": JIRA_BASE, "jql": args.jql, "total": len(jira_cards),
                      "withEndpoint": with_endpoint, "matched": matched_cards},
            "cards": jira_cards,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OK -> {JIRA_CARDS}  ({len(jira_cards)} kart)")
    else:
        print("\n(dry-run — registry yazilmadi)")

    # --- eslesmeyen yollar raporu: sozlesme/kart drift sinyali ---
    if unmatched:
        lines = [
            "# Jira ↔ Sözleşme eşleşmeyen yollar", "",
            "Kartlarda geçen ama sözleşmede karşılığı bulunmayan endpoint'ler.",
            "Üç sebebi olabilir: (1) uç koleksiyonda yok, (2) kart eski bir yolu",
            "referans veriyor, (3) kartta kısaltma kullanılmış (örn. `cms` öneki atlanmış).",
            "", f"Toplam {len(unmatched)} farklı yol.", "",
            "| Yol | Kart sayısı | Örnek kartlar |", "|---|---:|---|",
        ]
        for path, count in unmatched.most_common():
            examples = ", ".join(sorted(unmatched_examples[path])[:4])
            lines.append(f"| `{path}` | {count} | {examples} |")
        UNMATCHED_REPORT.parent.mkdir(exist_ok=True)
        UNMATCHED_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Eslesmeyen {len(unmatched)} yol -> {UNMATCHED_REPORT}")
        print("\nEN COK GECEN ESLESMEYENLER:")
        for path, count in unmatched.most_common(8):
            print(f"   {count:>3} kart  {path}")


if __name__ == "__main__":
    main()
