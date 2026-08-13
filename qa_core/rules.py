"""Kural envanteri — KODDAN TURETILIR, elle yazilmaz.

Panoda "hangi kurallar var" sorusunu cevaplar. Elle tutulan bir liste kacinilmaz
olarak bayatlar; bu yuzden envanter gercek kaynaklardan okunur:

    analyze.py           -> bulgu tipleri ("baslik" alanlari)
    contract/run.sh      -> Schemathesis check seti
    pytest.ini           -> marker'lar
    envelope_exceptions  -> baseline istisnalari + kategorileri
    schemas/*.json       -> envelope zorunlu alanlari
    qa-endpoint-check.md -> ajan kontrol listesi + guardrail'ler
    tests/               -> kurallari uygulayan test dosyalari

Boylece koda bir kural eklendiginde panoda kendiliginden gorunur.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent

SEVERITY_ORDER = {"kritik": 0, "yuksek": 1, "orta": 2, "bilgi": 3}


def _read(path):
    full = ROOT / path
    return full.read_text(encoding="utf-8") if full.exists() else ""


def analyze_rules():
    """analyze.py'deki bulgu tiplerini kaynak koddan cikarir."""
    source = _read("qa-dashboard/analyze.py")
    rules = []
    # her add({...}) blogundaki severity + baslik ciftini yakala.
    # baslik f-string olabilir; {ifade} kisimlari okunabilir yer tutucuya cevrilir.
    for match in re.finditer(
            r'"severity":\s*("(?:kritik|yuksek|orta|bilgi)"|[^,\n]+),\s*\n\s*"baslik":\s*f?"((?:[^"\\]|\\.)*)"',
            source):
        severity = match.group(1).strip('"')
        if "if " in severity or "else" in severity:
            severity = "degisken"

        title = re.sub(r"\{[^}]*\}", "…", match.group(2))   # f-string ifadeleri
        title = title.replace("`", "").strip()
        title = re.sub(r"\s*[—-]\s*$", "", title).strip()     # sondaki tire
        title = re.sub(r"\(\s*…?\s*\)", "", title).strip()     # bos parantez
        rules.append({"severity": severity, "baslik": title})
    return rules


def schemathesis_checks():
    match = re.search(r"-c\s+([a-z_,]+)", _read("contract/run.sh"))
    return match.group(1).split(",") if match else []


def schemathesis_phases():
    match = re.search(r'PHASES="\$\{PHASES:-([a-z,]+)\}"', _read("contract/run.sh"))
    return match.group(1).split(",") if match else []


def pytest_markers():
    source = _read("pytest.ini")
    block = source.split("markers =", 1)[-1]
    out = []
    for line in block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        name, _, desc = line.partition(":")
        if re.fullmatch(r"[a-z_]+", name):
            out.append({"ad": name, "aciklama": desc.strip()})
    return out


def envelope_constraints():
    """schemas/*.json icindeki zorunlu alanlar."""
    out = []
    for name in ("success", "error"):
        path = ROOT / "schemas" / f"{name}.json"
        if not path.exists():
            continue
        schema = json.loads(path.read_text(encoding="utf-8"))
        for field in schema.get("required", []):
            out.append({"sema": name, "kisit": f"`{field}` zorunlu"})
        nested = schema.get("properties", {}).get("error", {}).get("required", [])
        for field in nested:
            out.append({"sema": name, "kisit": f"`error.{field}` zorunlu"})
    return out


def baseline_summary():
    path = ROOT / "contract" / "envelope_exceptions.json"
    if not path.exists():
        return {"toplam": 0, "kategoriler": {}}
    data = json.loads(path.read_text(encoding="utf-8")).get("istisnalar", {})
    categories = {}
    for entry in data.values():
        key = entry.get("kategori", "?")
        categories[key] = categories.get(key, 0) + 1
    return {"toplam": len(data), "kategoriler": categories}


def agent_rules():
    source = _read(".claude/agents/qa-endpoint-check.md")
    checklist, guardrails = [], []
    in_guard = False
    for line in source.splitlines():
        if line.startswith("## GUARDRAIL"):
            in_guard = True
            continue
        if line.startswith("## ") and in_guard:
            in_guard = False
        item = re.match(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*—\s*(.*)$", line)
        if item and not in_guard and len(checklist) < 11:
            checklist.append({"no": int(item.group(1)), "ad": item.group(2),
                              "aciklama": item.group(3)[:160]})
        guard = re.match(r"^-\s+\*\*(.+?)\*\*\s*(.*)$", line)
        if guard and in_guard:
            guardrails.append({"ad": guard.group(1), "aciklama": guard.group(2)[:160]})
    return checklist, guardrails


def spec_sync_rules():
    """test_spec_sync.py'deki test docstring'lerinden kural listesi."""
    source = _read("tests/api/test_spec_sync.py")
    out = []
    for match in re.finditer(r'def (test_\w+)\([^)]*\):\s*\n\s*"""(.+?)[\.\n"]', source):
        out.append({"test": match.group(1), "aciklama": match.group(2).strip()})
    return out


def test_files():
    """Kurallari uygulayan test dosyalari + fonksiyon sayilari."""
    out = []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        count = len(re.findall(r"^def test_", source, re.M))
        marks = sorted(set(re.findall(r"pytest\.mark\.(\w+)", source)))
        needs_network = "authed_api" in source or "api." in source or "requests" in source
        out.append({
            "dosya": str(path.relative_to(ROOT)),
            "fonksiyon": count,
            "marker": [m for m in marks if m not in ("parametrize", "xfail", "skip")],
            "agGerekir": bool(needs_network) and "test_analyze" not in path.name
                         and "test_compare" not in path.name,
        })
    return out


def inventory():
    """Panonun tukettigi tam envanter."""
    analyze = analyze_rules()
    checklist, guardrails = agent_rules()
    checks = schemathesis_checks()
    constraints = envelope_constraints()
    sync = spec_sync_rules()
    files = test_files()
    baseline = baseline_summary()

    otomatik = len(analyze) + len(checks) + len(constraints) + len(sync) + 4  # +4 sweep kolonu
    return {
        "ozet": {
            "otomatikKural": otomatik,
            "ajanKurali": len(checklist) + len(guardrails),
            "toplam": otomatik + len(checklist) + len(guardrails),
            "testFonksiyonu": sum(f["fonksiyon"] for f in files),
            "baselineIstisnasi": baseline["toplam"],
        },
        "setler": [
            {
                "ad": "Otomatik yorum motoru",
                "kaynak": "qa-dashboard/analyze.py",
                "adet": len(analyze),
                "ag": False,
                "aciklama": "Canli yaniti siniflandirip Turkce degerlendirme uretir. "
                            "LLM yok — deterministik, birim testli.",
                "kurallar": [{"etiket": r["severity"], "metin": r["baslik"]}
                             for r in sorted(analyze, key=lambda r: SEVERITY_ORDER.get(r["severity"], 9))],
            },
            {
                "ad": "Envelope sozlesmesi",
                "kaynak": "schemas/success.json · schemas/error.json",
                "adet": len(constraints),
                "ag": False,
                "aciklama": "Her dokumante ornege ve her canli yanita uygulanir.",
                "kurallar": [{"etiket": c["sema"], "metin": c["kisit"]} for c in constraints],
            },
            {
                "ad": "Sozlesme ic tutarliligi",
                "kaynak": "tests/api/test_spec_sync.py",
                "adet": len(sync),
                "ag": False,
                "aciklama": "Uretilmis dosyalarin guncelligi ve baseline bekciligi. "
                            "Canli ortam gerekmez.",
                "kurallar": [{"etiket": "test", "metin": s["aciklama"]} for s in sync],
            },
            {
                "ad": "Schemathesis check seti",
                "kaynak": "contract/run.sh",
                "adet": len(checks),
                "ag": True,
                "aciklama": f"Fazlar: {', '.join(schemathesis_phases()) or '—'} "
                            "(fuzzing ve stateful kapali).",
                "kurallar": [{"etiket": "check", "metin": c} for c in checks],
            },
            {
                "ad": "Canli tarama degerlendirmesi",
                "kaynak": "contract/sweep.py",
                "adet": 4,
                "ag": True,
                "aciklama": "Her GET operasyonu icin tek satirlik sonuc.",
                "kurallar": [{"etiket": "kolon", "metin": m} for m in
                             ("id — gercek / kismi / yer tutucu",
                              "documented — alinan status sozlesmede var mi",
                              "envelope — basari/hata envelope'una uyum",
                              "schema — spec semasina uyum")],
            },
            {
                "ad": "Kart ↔ canli karsilastirma",
                "kaynak": "qa-dashboard/compare.py",
                "adet": 3,
                "ag": True,
                "aciklama": "Jira kartinin kod blogundaki beklenen yanit ile canli yanit. "
                            "Deger degil TIP karsilastirilir.",
                "kurallar": [{"etiket": "diff", "metin": m} for m in
                             ("eksik — kartta var, canlida yok",
                              "tipFarki — kart integer demis, canli string dondurmus",
                              "fazla — canlida kartta olmayan alan (kart eskimis olabilir)")],
            },
            {
                "ad": "QA ajani kontrol listesi",
                "kaynak": ".claude/agents/qa-endpoint-check.md",
                "adet": len(checklist),
                "ag": True,
                "aciklama": "Ajan bir endpoint/kart incelerken uyguladigi maddeler.",
                "kurallar": [{"etiket": str(c["no"]), "metin": f"{c['ad']} — {c['aciklama']}"}
                             for c in checklist],
            },
            {
                "ad": "Ajan guardrail'leri",
                "kaynak": ".claude/agents/qa-endpoint-check.md",
                "adet": len(guardrails),
                "ag": False,
                "aciklama": "Ihlal edilmemesi gereken kisitlar — yanlis bulgu uretmeyi engeller.",
                "kurallar": [{"etiket": "guard", "metin": f"{g['ad']} {g['aciklama']}"}
                             for g in guardrails],
            },
        ],
        "baseline": baseline,
        "markerlar": pytest_markers(),
        "testDosyalari": files,
    }
