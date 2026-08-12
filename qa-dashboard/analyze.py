"""Otomatik yorum motoru — sapmalardan okunabilir Turkce degerlendirme uretir.

LLM YOK. Girdi olarak (kart, canli yanit, sema hatalari) alir; ciktisi siniflandirilmis
bulgu listesidir. Deterministik: ayni girdi her zaman ayni yorumu verir, bu yuzden
birim testi yazilabilir (tests/api/test_analyze.py).

Amac: "3 alan uyusmuyor" gibi ham bir ciktiyi, QA'in aksiyon alabilecegi bir cumleye
cevirmek — hangi alan, neden onemli, ne yapilmali.

Her bulgu: {severity, baslik, aciklama, oneri}
severity: kritik > yuksek > orta > bilgi
"""
import re

SEVERITY_ORDER = {"kritik": 0, "yuksek": 1, "orta": 2, "bilgi": 3}

# Para/tutar tasidigi isminden anlasilan alanlar (sayim alanlari haric)
MONEY_RE = re.compile(
    r"(amount|revenue|price|budget|cost|fee|balance|salary|tutar|fiyat)", re.I)
COUNT_RE = re.compile(r"(count|pages|totalpages|totalcount)$", re.I)

PII_FIELDS = {"email", "phone", "iban", "taxnumber", "identitynumber", "tckn"}

PLACEHOLDER_ID = "00000000-0000-0000-0000-000000000000"

# Sema hata mesajlarindan tip cikarimi
NULL_TYPE_RE = re.compile(r"^None is not of type '(\w+)'")
TYPE_MISMATCH_RE = re.compile(r"^(.+?) is not of type '(\w+)'$", re.S)
REQUIRED_RE = re.compile(r"^'(\w+)' is a required property$")


def _leaf(path):
    """'data/0/taxNumber' -> 'taxNumber'"""
    return (path or "").split("/")[-1] or path


def _is_money(field):
    return bool(MONEY_RE.search(field or "")) and not COUNT_RE.search(field or "")


def analyze(card, status, body, schema_errors, elapsed_ms=None,
            headers=None, path_params=None):
    """Bulgu listesi doner (siddete gore sirali)."""
    findings = []
    add = findings.append
    headers = headers or {}
    path_params = path_params or {}

    documented = [c for c in (card.get("documentedStatuses") or []) if str(c).isdigit()]

    # --- 1. Sunucu hatasi ---
    if isinstance(status, int) and status >= 500:
        add({"severity": "kritik",
             "baslik": f"Sunucu hatasi ({status})",
             "aciklama": "Uc islenmeyen bir hata donduruyor. Bu bir istemci girdisi "
                         "sorunu degil, servis tarafinda cokme/erisim problemi.",
             "oneri": "Servis loglarina bakilmali; bug acilmali."})

    # --- 2. Dokumante olmayan status ---
    if isinstance(status, int) and str(status) not in documented:
        if status == 401:
            add({"severity": "bilgi",
                 "baslik": "401 sozlesmede tanimli degil",
                 "aciklama": "Davranis dogru (korumali uc token istiyor) ama koleksiyon "
                             "bu uc icin 401 ornegi tasimiyor. Dokumantasyon eksigi.",
                 "oneri": "Koleksiyona 401 ornegi eklenmeli."})
        elif status == 404:
            add({"severity": "bilgi",
                 "baslik": "404 sozlesmede tanimli degil",
                 "aciklama": "Var olmayan kayit icin 404 donmesi dogru davranis; "
                             "koleksiyon bunu dokumante etmemis.",
                 "oneri": "Detay uclarina 404 ornegi eklenmeli."})
        else:
            add({"severity": "yuksek",
                 "baslik": f"HTTP {status} sozlesmede tanimli degil",
                 "aciklama": f"Dokumante statusler: {', '.join(documented) or 'yok'}. "
                             "Istemci bu durumu beklemiyor olabilir.",
                 "oneri": "Davranis dogruysa dokumante edilmeli; degilse duzeltilmeli."})

    # --- 3. Yer tutucu ID ile 404 -> maskeleme uyarisi ---
    if status == 404 and any(v == PLACEHOLDER_ID for v in path_params.values()):
        add({"severity": "orta",
             "baslik": "Yer tutucu ID kullanildi — sapmalar maskelenmis olabilir",
             "aciklama": "Uc var olmayan bir ID ile cagrildi, bu yuzden 404 dondu. "
                         "404 sozlesmeye uygun oldugu icin sonuc 'uyumlu' gorunur; "
                         "asil yanit govdesi hic dogrulanmadi.",
             "oneri": "'Gercek ID getir' ile canli bir kayit secip tekrar kos."})

    # --- 4. Bos sonuc ---
    items = None
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and isinstance(data.get("data"), list):
            items = data["data"]
    if items is not None and len(items) == 0 and status == 200:
        add({"severity": "orta",
             "baslik": "Bos liste dondu — PASS sayilmaz",
             "aciklama": "Yanit basarili ama hic kayit yok; alan yapisi, tipler ve "
                         "sayfalama dogrulanamaz. Bos sonuc yesil gorunup gercek "
                         "sapmalari saklayabilir.",
             "oneri": "Veri bulunan bir tenant/filtre ile tekrar kos."})

    # --- 5. Liste yapisi (dokuman vs canli) ---
    if status == 200 and isinstance(body, dict):
        example = card.get("responseExample")
        live_flat = isinstance(body.get("data"), list)
        doc_nested = (isinstance(example, dict)
                      and isinstance(example.get("data"), dict)
                      and isinstance(example["data"].get("data"), list))
        if live_flat and doc_nested:
            add({"severity": "yuksek",
                 "baslik": "Liste yapisi dokumandan farkli",
                 "aciklama": "Canli `data[]` + kok seviye `meta` donuyor; dokuman "
                             "`data.data[]` + `data.meta` gosteriyor.",
                 "oneri": "FE `response.data.data` okuyorsa liste bos gelir. "
                          "Kaynak-of-truth netlestirilmeli."})

    # --- 6. Sema sapmalari ---
    nullable, type_mismatch, missing, structural = [], [], [], []
    for err in schema_errors or []:
        message = err.get("message", "")
        field = _leaf(err.get("path"))

        if NULL_TYPE_RE.match(message):
            expected = NULL_TYPE_RE.match(message).group(1)
            nullable.append((field, expected))
            continue

        required = REQUIRED_RE.match(message)
        if required:
            missing.append(required.group(1))
            continue

        mismatch = TYPE_MISMATCH_RE.match(message)
        if mismatch:
            value, expected = mismatch.group(1).strip(), mismatch.group(2)
            if value.startswith(("{", "[")):
                structural.append((field, expected))
            else:
                type_mismatch.append((field, value, expected))

    if nullable:
        fields = ", ".join(sorted({f"`{f}`" for f, _ in nullable}))
        add({"severity": "orta",
             "baslik": f"Dokumante edilmemis null deger ({len(nullable)} alan)",
             "aciklama": f"{fields} canlida `null` donuyor ama sema bos olmayan bir tip "
                         "bekliyor. Bu alanlar bazi kayitlarda dogal olarak bos olabilir.",
             "oneri": "Semada `nullable: true` isaretlenmeli; istemci null'a hazir olmali."})

    for field, value, expected in type_mismatch:
        if _is_money(field):
            add({"severity": "yuksek",
                 "baslik": f"Para alani tip uyusmazligi — `{field}`",
                 "aciklama": f"Canli `{value}` donuyor, sema `{expected}` bekliyor. "
                             "Para alaninin ondalikli/float temsili hem hassasiyet "
                             "riski tasir hem de istemcide yuvarlama/kirilma uretir.",
                 "oneri": "Tek konvansiyon belirlenmeli (tercihen string/decimal); "
                          "sema gercek tipe hizalanmali."})
        else:
            add({"severity": "orta",
                 "baslik": f"Tip uyusmazligi — `{field}`",
                 "aciklama": f"Canli `{value}` donuyor, sema `{expected}` bekliyor.",
                 "oneri": "Dokuman mi eski, API mi degisti — netlestirilmeli."})

    if structural:
        fields = ", ".join(sorted({f"`{f}`" for f, _ in structural}))
        add({"severity": "yuksek",
             "baslik": "Yapisal fark",
             "aciklama": f"{fields} alaninda canli yanit dokumante ornekten farkli bir "
                         "sekle sahip (nesne/dizi beklenmedigi yerde geliyor).",
             "oneri": "Alan yapisi karsilastirilip sozlesme guncellenmeli."})

    if missing:
        fields = ", ".join(f"`{f}`" for f in sorted(set(missing)))
        add({"severity": "yuksek",
             "baslik": f"Kayip alan ({len(set(missing))})",
             "aciklama": f"Sozlesmenin zorunlu tuttugu {fields} canli yanitta yok. "
                         "Alan kaybi istemci tarafinda dogrudan kirilma uretir.",
             "oneri": "Regresyon olabilir — bug acilmasi degerlendirilmeli."})

    # --- 7. Bilinen sapma baseline'i ---
    known = card.get("envelopeExceptions") or []
    if known:
        gercek = [k for k in known if k.get("kategori") in
                  ("envelope-disi", "yanlis-status-eslemesi")]
        add({"severity": "yuksek" if gercek else "bilgi",
             "baslik": f"Bu uctа bilinen sapma kayitli ({len(known)})",
             "aciklama": "; ".join(f"{k.get('kategori')}: {k.get('gerekce','')[:110]}"
                                   for k in known[:2]),
             "oneri": "Baseline'da kayitli — yeni bulgu sayilmaz. "
                      + ("Kategorisi gercek kusur: takip edilmeli."
                         if gercek else "Dokuman borcu.")})

    # --- 8. Performans ---
    if isinstance(elapsed_ms, int) and elapsed_ms > 1000:
        add({"severity": "orta" if elapsed_ms > 3000 else "bilgi",
             "baslik": f"Yavas yanit ({elapsed_ms} ms)",
             "aciklama": "Uc 1 saniyenin uzerinde surdu. Liste uclarinda sayfalama "
                         "veya N+1 sorgu problemi olabilir.",
             "oneri": "Sayfalama parametreleriyle karsilastirilmali."})

    # --- 9. Cache ---
    if status == 200 and card.get("method") == "GET":
        if not any(h.lower() == "cache-control" for h in headers):
            add({"severity": "bilgi",
                 "baslik": "Cache-Control yok",
                 "aciklama": "Salt-okunur uc onbellek basligi dondurmuyor.",
                 "oneri": "Degismeyen veri donen uclarda Cache-Control/ETag dusunulebilir."})

    # --- 10. PII ---
    def has_pii(node, depth=0):
        if depth > 6:
            return False
        if isinstance(node, dict):
            return any(k.lower() in PII_FIELDS and node[k] for k in node) or \
                   any(has_pii(v, depth + 1) for v in node.values())
        if isinstance(node, list):
            return any(has_pii(v, depth + 1) for v in node[:5])
        return False

    if status == 200 and has_pii(body):
        add({"severity": "bilgi",
             "baslik": "Yanit PII tasiyor",
             "aciklama": "Govdede e-posta/telefon/vergi no gibi kisisel veri var "
                         "(panoda maskelenerek gosterildi).",
             "oneri": "Loglara/rapora ham govde yazilmamali; yetki kontrolu (BOLA) "
                      "ayrica dogrulanmali."})

    findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
    return findings


def summarize(findings):
    """Bulgu listesinden tek satirlik ozet."""
    if not findings:
        return "Otomatik kontrollerde dikkat ceken bir sey bulunmadi."
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    parts = [f"{n} {sev}" for sev, n in
             sorted(counts.items(), key=lambda kv: SEVERITY_ORDER.get(kv[0], 9))]
    return " · ".join(parts)
