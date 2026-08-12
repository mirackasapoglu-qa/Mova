# OPRAS — QA Bilgi Tabanı / RAG

Dağınık QA bilgisini tek index'te toplayıp doğal dil sorusuyla **kaynak-referanslı**
sonuç getiren hafif retrieval aracı.

## Kullanım

```bash
.venv/bin/python rag/qa_rag.py build            # index'i (yeniden) kur
.venv/bin/python rag/qa_rag.py ask "soru" -k 6  # sorgula
.venv/bin/python rag/qa_rag.py stats            # index özeti
```

## Korpüs kaynakları

| Tip | Kaynak | Adet |
|---|---|---|
| `endpoint` | `qa-dashboard/registry.json` — operasyon başına bir belge | 237 |
| `sapma` | `contract/envelope_exceptions.json` — bilinen envelope sapmaları | 31 |
| `doc` | `DISCREPANCIES.md`, `README.md`, `qa-dashboard/README.md` | ~25 |
| `memory` | `~/.claude/projects/-Users-macbookair-MOVA/memory/*.md` | değişken |
| `jira` | `rag/sources/jira_status.jsonl` (opsiyonel snapshot) | — |
| `confluence` | `rag/sources/confluence_rollup.md` (opsiyonel snapshot) | — |

Sözleşme değişince `build` yeniden çalıştırılmalı — omurga `registry.json`'dan gelir,
o da `contract/openapi.json`'dan üretilir.

## Jira snapshot (opsiyonel)

Araç MCP çağıramaz; snapshot'lar `rag/sources/` altına elle beslenir (gitignore'da):

1. Jira'dan JQL ile çek (MCP `searchJiraIssuesUsingJql`).
2. Normalize et: `.venv/bin/python rag/_sync_jira.py <toolresult...>` → `rag/sources/jira_status.jsonl`
3. `rag/qa_rag.py build`

Kart kodu ön eki `JIRA_PROJECT_KEY` ile ayarlanır (varsayılan `TP`).

## Tasarım (bilerek)

- **Dış API/embedding servisi yok** — saf Python BM25 (offline, deterministik).
- **Grounding zorunlu** — her sonuç kaynak yolu + kart + statü ile döner; uydurmaz.
- **"Geçmişte böyleydi" ≠ "şu an böyle"** — sonuçlar kayıttan gelir; **canlı test/spec
  her zaman kaynak-of-truth**. Araç canlı testin yerine geçmez, hafızasıdır.
- `rag/corpus.jsonl` türetilmiş build-artifact'tır (gitignore'da).
