#!/usr/bin/env python3
"""
Nadir Gold V2 — QA Bilgi Tabanı / RAG prototipi (Aşama 1 + BM25 retrieval)

Amaç: dağınık QA bilgisini (captures/, repo dokümanları, memory) tek index'te
toplayıp doğal dil sorusuyla KAYNAK-REFERANSLI sonuç getirmek.

Tasarım kuralları (bilerek):
  • Dış API/embedding servisi YOK — saf Python BM25 (offline, deterministik).
  • Her sonuç kaynak yolu + (varsa) NSB kartı + verdict ile döner (grounding).
  • Retrieval-only: uydurmaz, sadece gerçek belgelerden getirir.
  • "Geçmişte böyleydi" ≠ "şu an böyle" — sonuçlarda capture tarihi gösterilir;
    canlı test/spec her zaman kaynak-of-truth kalır (NSB-6097 dersi).

Kullanım:
  .venv/bin/python rag/qa_rag.py build                 # index'i (yeniden) kur
  .venv/bin/python rag/qa_rag.py ask "soru..." [-k 6]   # sorgula
  .venv/bin/python rag/qa_rag.py stats                  # index özeti
"""
import json, os, re, sys, math, glob, argparse
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.expanduser(
    "~/.claude/projects/-Users-macbookair-MOVA/memory")
INDEX_PATH = os.path.join(ROOT, "rag", "corpus.jsonl")

# Jira kart kodu on eki (OPRAS kartlari TP-#### bicimindedir).
TICKET_PREFIX = os.getenv("JIRA_PROJECT_KEY", "TP").upper()
TICKET_RE = re.compile(rf"{TICKET_PREFIX}-\d+")

# ---- Türkçe-duyarlı basit tokenizer -------------------------------------
_TR_FOLD = str.maketrans("çğıöşüİ", "cgiosui")

def norm(s):
    """lower + Türkçe karakter katlama (eşleşme sağlamlığı için)."""
    return s.replace("I", "ı").lower().translate(_TR_FOLD)

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_/.][a-z0-9]+)*", re.I)

def tokenize(text):
    t = norm(text)
    toks = TOKEN_RE.findall(t)
    # NSB-#### gibi kart kodlarını da yakala
    toks += [m.lower() for m in re.findall(TICKET_PREFIX.lower() + r"-\d+", t)]
    return toks

# ---- Korpüs ingest ------------------------------------------------------
def ingest_registry():
    """qa-dashboard/registry.json -> operasyon başına bir belge.

    Sözleşmeden türetilen kartlar korpüsün omurgasıdır: hangi uç hangi servise
    ait, hangi statüleri dokümante ediyor, bilinen bir envelope sapması var mı.
    """
    path = os.path.join(ROOT, "qa-dashboard", "registry.json")
    if not os.path.exists(path):
        return []
    try:
        cards = json.load(open(path, encoding="utf-8")).get("cards", [])
    except (ValueError, OSError):
        return []

    out = []
    for c in cards:
        parts = [
            f"{c['method']} {c['path']}",
            f"servis: {c.get('service','')}",
            f"ozet: {c.get('summary','')}",
            f"auth: {'gerekli' if c.get('auth') else 'public'}",
            f"tip: {'mutating' if c.get('mutating') else 'salt-okunur'}",
            f"dokumante status: {', '.join(c.get('documentedStatuses', []))}",
        ]
        if c.get("notes"):
            parts.append(f"not: {c['notes']}")
        for exc in c.get("envelopeExceptions", []):
            parts.append(f"sapma [{exc.get('kategori')}]: {exc.get('gerekce')}")

        verdict = c.get("verdict", "")
        status = ("PASS" if "UYUMLU" in verdict or "PASS" in verdict
                  else "FAIL" if "SAPMA" in verdict or "FAIL" in verdict
                  else "FLAGGED" if c.get("envelopeExceptions")
                  else "?")
        out.append({
            "id": f"registry/{c['key']}",
            "type": "endpoint",
            "ticket": " ".join(TICKET_RE.findall(c.get("notes", "") + " " + c.get("summary", ""))),
            "status": status,
            "date": "spec",
            "text": "\n".join(parts),
        })
    return out


def ingest_exceptions():
    """contract/envelope_exceptions.json -> bilinen sapma baseline'ı."""
    path = os.path.join(ROOT, "contract", "envelope_exceptions.json")
    if not os.path.exists(path):
        return []
    try:
        data = json.load(open(path, encoding="utf-8")).get("istisnalar", {})
    except (ValueError, OSError):
        return []
    return [{
        "id": f"exception/{key}",
        "type": "sapma",
        "ticket": "",
        "status": "FLAGGED",
        "date": "baseline",
        "text": f"{key} | kategori: {v.get('kategori')} | ihlal: {v.get('ihlal')} "
                f"| gerekce: {v.get('gerekce')}",
    } for key, v in data.items()]

def chunk_md(path, kind):
    """MD -> başlık bazlı parçalar."""
    txt = open(path, encoding="utf-8").read()
    rel = os.path.relpath(path, ROOT) if path.startswith(ROOT) else os.path.basename(path)
    chunks, cur, curhdr = [], [], ""
    for line in txt.splitlines():
        if re.match(r"^#{1,4}\s", line):
            if cur:
                chunks.append((curhdr, "\n".join(cur)))
            curhdr, cur = line.strip("# ").strip(), [line]
        else:
            cur.append(line)
    if cur:
        chunks.append((curhdr, "\n".join(cur)))
    out = []
    for i, (hdr, body) in enumerate(chunks):
        if len(body.strip()) < 20:
            continue
        tickets = " ".join(sorted(set(TICKET_RE.findall(body))))
        out.append({
            "id": f"{rel}#{i}",
            "type": kind,
            "ticket": tickets,
            "status": "",
            "date": "",
            "text": (hdr + "\n" + body)[:2000],
        })
    return out

SOURCES_DIR = os.path.join(ROOT, "rag", "sources")

def ingest_jira():
    """Aşama 2: rag/sources/jira_status.jsonl -> canlı statü snapshot'ı."""
    p = os.path.join(SOURCES_DIR, "jira_status.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        st = r.get("status", "")
        norm_st = ("PASS" if st in ("Ready For Stage", "Ready For Deploy")
                   else "FAIL" if st == "Test Failed"
                   else "BLOCKED" if st in ("Test Blocked", "Blocked")
                   else st)
        out.append({
            "id": r["key"],
            "type": "jira",
            "ticket": r["key"],
            "status": norm_st,
            "date": "canlı",
            "text": f"{r['key']} {r.get('summary','')} | statü: {st} "
                    f"| tip: {r.get('issuetype','')}",
        })
    return out

def ingest():
    docs = []
    # Sözleşmeden türetilen omurga
    docs += ingest_registry()
    docs += ingest_exceptions()
    for name in ("DISCREPANCIES.md", "README.md",
                 os.path.join("qa-dashboard", "README.md")):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            docs += chunk_md(p, "doc")
    for p in glob.glob(os.path.join(MEMORY_DIR, "*.md")):
        docs += chunk_md(p, "memory")
    # Aşama 2: canlı Jira statüsü + Confluence roll-up snapshot'ı
    docs += ingest_jira()
    roll = os.path.join(SOURCES_DIR, "confluence_rollup.md")
    if os.path.exists(roll):
        docs += chunk_md(roll, "confluence")
    return docs

# ---- BM25 (saf Python) --------------------------------------------------
class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tokens = [tokenize(d["text"] + " " + d.get("ticket", "")) for d in docs]
        self.len = [len(t) for t in self.tokens]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 0
        self.df = defaultdict(int)
        self.tf = []
        for toks in self.tokens:
            f = defaultdict(int)
            for t in toks:
                f[t] += 1
            self.tf.append(f)
            for t in f:
                self.df[t] += 1
        self.N = len(docs)
        self.idf = {t: math.log(1 + (self.N - df + 0.5) / (df + 0.5))
                    for t, df in self.df.items()}

    def search(self, query, k=6):
        q = tokenize(query)
        scores = []
        for i, f in enumerate(self.tf):
            s = 0.0
            for t in q:
                if t not in f:
                    continue
                idf = self.idf.get(t, 0)
                num = f[t] * (self.k1 + 1)
                den = f[t] + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1))
                s += idf * num / den
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return scores[:k]

# ---- CLI ----------------------------------------------------------------
def cmd_build(_):
    docs = ingest()
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    caps = sum(1 for d in docs if d["type"] == "capture")
    print(f"✓ index kuruldu: {len(docs)} belge ({caps} capture + "
          f"{len(docs)-caps} doküman/memory) -> {os.path.relpath(INDEX_PATH, ROOT)}")

def load_docs():
    if not os.path.exists(INDEX_PATH):
        print("Index yok. Önce: qa_rag.py build", file=sys.stderr)
        sys.exit(1)
    return [json.loads(l) for l in open(INDEX_PATH, encoding="utf-8")]

def cmd_ask(a):
    docs = load_docs()
    bm = BM25(docs)
    hits = bm.search(a.query, a.k)
    if not hits:
        print("Eşleşme yok.")
        return
    icon = {"PASS": "✅", "FAIL": "❌", "BLOCKED": "🟡", "?": "•", "": "•"}
    print(f"\nSoru: {a.query}\n" + "=" * 60)
    for rank, (score, i) in enumerate(hits, 1):
        d = docs[i]
        head = f"{rank}. [{d['type']}] {d['id']}"
        meta = []
        if d.get("ticket"):
            meta.append(d["ticket"])
        if d.get("status"):
            meta.append(icon.get(d["status"], "") + d["status"])
        if d.get("date"):
            meta.append(d["date"])
        if meta:
            head += "  (" + " · ".join(meta) + ")"
        print(f"\n{head}   ~{score:.1f}")
        snippet = d["text"].strip().replace("\n", " ")
        print("   " + (snippet[:280] + ("…" if len(snippet) > 280 else "")))
    print("\n" + "=" * 60)
    print("Not: sonuçlar geçmiş QA kayıtlarından; CANLI test/spec kaynak-of-truth.")

def cmd_stats(_):
    docs = load_docs()
    by_type = defaultdict(int)
    by_status = defaultdict(int)
    for d in docs:
        by_type[d["type"]] += 1
        if d["type"] == "capture":
            by_status[d["status"]] += 1
    print("Belge tipi:", dict(by_type))
    print("Capture verdict:", dict(by_status))
    print("Toplam:", len(docs))

def main():
    ap = argparse.ArgumentParser(description="Nadir Gold QA RAG prototipi")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").set_defaults(fn=cmd_build)
    pa = sub.add_parser("ask")
    pa.add_argument("query")
    pa.add_argument("-k", type=int, default=6)
    pa.set_defaults(fn=cmd_ask)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    a = ap.parse_args()
    a.fn(a)

if __name__ == "__main__":
    main()
