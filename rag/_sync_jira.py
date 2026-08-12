#!/usr/bin/env python3
"""Aşama 2 sync yardımcısı: MCP JQL çıktısı (tool-results dosyaları) ->
rag/sources/jira_status.jsonl (normalize: key, summary, status, issuetype).
Kullanım: _sync_jira.py <dosya1.txt> [dosya2.txt ...]"""
import json, os, sys, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "rag", "sources", "jira_status.jsonl")

def extract_issues(path):
    raw = open(path, encoding="utf-8").read()
    # dosya: JSON array [{type,text}] VEYA düz metin; issues JSON'unu bul
    issues = []
    try:
        arr = json.loads(raw)
        blobs = [p.get("text", "") for p in arr if isinstance(p, dict)]
    except Exception:
        blobs = [raw]
    for b in blobs:
        if '"issues"' not in b:
            continue
        # b içinde JSON objesi olabilir; ilk { ... } bloğunu parse et
        try:
            obj = json.loads(b)
        except Exception:
            m = re.search(r"\{.*\"issues\".*\}", b, re.S)
            if not m:
                continue
            try:
                obj = json.loads(m.group(0))
            except Exception:
                continue
        for iss in obj.get("issues", []):
            f = iss.get("fields", {})
            st = (f.get("status") or {}).get("name", "")
            it = (f.get("issuetype") or {}).get("name", "")
            issues.append({
                "key": iss.get("key", ""),
                "summary": f.get("summary", ""),
                "status": st,
                "issuetype": it,
            })
    return issues

def main():
    seen, rows = {}, []
    for path in sys.argv[1:]:
        for r in extract_issues(path):
            if r["key"] and r["key"] not in seen:
                seen[r["key"]] = r
                rows.append(r)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in sorted(rows, key=lambda x: x["key"]):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"✓ {len(rows)} issue -> {os.path.relpath(OUT, ROOT)}")
    # kısa özet
    from collections import Counter
    by_status = Counter(r["status"] for r in rows)
    print("statü dağılımı:", dict(by_status))

if __name__ == "__main__":
    main()
