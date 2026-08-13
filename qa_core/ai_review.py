"""Kartın DÜZ METİN kabul kriterlerini canlı yanıta karşı değerlendirir (Claude).

Neden LLM: `analyze.py` ve `compare.py` yapısal şeyleri yakalar — eksik alan, tip
farkı, envelope ihlali. Yakalayamadıkları şey kartların prose kabul kriterleridir:
"sidebar rol bazlı görünürlüğe göre filtrelenmeli", "iptal edilen teklif tekrar
gönderilemez", "sadece kendi departmanının görevleri dönmeli". Bunlar JSON diff'iyle
doğrulanamaz; okunup yanıtla karşılaştırılması gerekir.

TASARIM SINIRLARI (bilinçli):
  - Bu katman KANIT DEĞİL, YORUMDUR. Verdict'i kurallar belirler; LLM çıktısı ayrı
    bir kutuda "yorum" etiketiyle gösterilir. Deterministik motorlar tekrarlanabilir,
    bu değil.
  - Yanıt gövdesi panele girmeden ÖNCE PII maskelenir; buraya maskelenmiş hali gelir.
  - Deterministik bulgular prompt'a verilir ki LLM onları tekrar etmesin.
  - Kanıt yoksa "dogrulanamadi" der — uydurmaz. (Bu kural prompt'ta da,
    şemada da zorunlu.)

VERİ SINIRI: Bu çağrı kart metnini ve (maskelenmiş) canlı yanıtı Anthropic API'ye
gönderir. Kurum verisi altyapı dışına çıkar — kullanılmadan önce bu kabul edilmeli.
"""
import json
import os

MODEL = os.getenv("QA_AI_MODEL", "claude-opus-5")
EFFORT = os.getenv("QA_AI_EFFORT", "medium")
MAX_TOKENS = 8000

SYSTEM = """Sen bir QA mühendisisin. Görevin: bir Jira kartının kabul kriterlerini,
o kartın endpoint'ine yapılmış CANLI bir çağrının yanıtına karşı değerlendirmek.

Kurallar:
- Yalnızca sana verilen kanıta dayan. Yanıtta göremediğin bir şeyi "sağlanıyor"
  da "sağlanmıyor" da sayma — "dogrulanamadi" de ve neyin eksik olduğunu yaz.
- Yapısal kontroller (eksik alan, tip farkı, envelope, status kodu) BAŞKA bir motor
  tarafından zaten yapıldı ve sonuçları sana veriliyor. Onları TEKRAR ETME.
  Senin işin düz metin kabul kriterleri: iş kuralları, yetki/görünürlük mantığı,
  sıralama, filtreleme, metin içeriği, durum geçişleri.
- Tek bir yanıt tek bir veri profilidir. Boş liste ya da tek kayıt gördüğünde
  genelleme yapma — "dogrulanamadi" de.
- Kartta kabul kriteri yoksa bunu açıkça söyle.
- Türkçe yaz, kısa ve kanıta dayalı ol. Her değerlendirmede yanıttan alıntı yap."""

SCHEMA = {
    "type": "object",
    "properties": {
        "ozet": {
            "type": "string",
            "description": "Tek cümlelik genel değerlendirme.",
        },
        "kriterler": {
            "type": "array",
            "description": "Karttan çıkarılan her kabul kriteri için bir değerlendirme.",
            "items": {
                "type": "object",
                "properties": {
                    "kriter": {"type": "string", "description": "Kartta yazan kriter, kısaltılmış."},
                    "durum": {
                        "type": "string",
                        "enum": ["saglaniyor", "saglanmiyor", "dogrulanamadi"],
                    },
                    "gerekce": {
                        "type": "string",
                        "description": "Yanıttan somut kanıt. Kanıt yoksa neyin eksik olduğu.",
                    },
                },
                "required": ["kriter", "durum", "gerekce"],
                "additionalProperties": False,
            },
        },
        "ekBulgular": {
            "type": "array",
            "description": "Kriterlere bağlı olmayan, dikkat çeken gözlemler. Yoksa boş.",
            "items": {"type": "string"},
        },
    },
    "required": ["ozet", "kriterler", "ekBulgular"],
    "additionalProperties": False,
}


def available():
    """Kimlik bilgisi var mı — SDK env değişkeni ya da profil okur."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "anthropic paketi kurulu degil (pip install anthropic)"
    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
            or os.path.isdir(os.path.expanduser("~/.config/anthropic/credentials"))):
        return False, ("Anthropic kimlik bilgisi yok — ANTHROPIC_API_KEY tanimla "
                       "ya da `ant auth login` ile profil olustur")
    return True, ""


def _prompt(jira_card, run_result):
    """Modele verilecek tek kullanıcı mesajı."""
    findings = run_result.get("findings") or []
    comparison = run_result.get("comparison") or {}

    deterministic = []
    for f in findings:
        deterministic.append(f"[{f.get('severity')}] {f.get('baslik')}")
    if comparison.get("eksik"):
        deterministic.append(f"eksik alanlar: {', '.join(comparison['eksik'][:10])}")
    for m in (comparison.get("tipFarki") or [])[:10]:
        deterministic.append(
            f"tip farki: {m.get('alan')} (kart {m.get('beklenen')} / canli {m.get('gelen')})")

    body = run_result.get("body")
    body_text = json.dumps(body, ensure_ascii=False, indent=2)[:12000]

    return f"""## Jira kartı: {jira_card.get('key')}
Özet: {jira_card.get('summary')}
Statü: {jira_card.get('status')} · Tip: {jira_card.get('type')}

### Kartın açıklaması / kabul kriterleri
{(jira_card.get('description') or '(kartta açıklama yok)')[:6000]}

## Canlı çağrı
{run_result.get('operation', {}).get('method')} {run_result.get('operation', {}).get('path')}
HTTP {run_result.get('status')} · {run_result.get('elapsedMs')} ms

### Yanıt gövdesi (PII maskeli)
```json
{body_text}
```

## Yapısal motorların zaten bulduğu şeyler — TEKRAR ETME
{chr(10).join('- ' + d for d in deterministic) if deterministic else '- (yapısal sapma bulunmadı)'}

Kartın düz metin kabul kriterlerini bu yanıta karşı değerlendir."""


def review(jira_card, run_result):
    """Kart ↔ canlı yanıt için LLM değerlendirmesi. Hata durumunda {'error': ...} döner."""
    ok, reason = available()
    if not ok:
        return {"error": reason}

    import anthropic

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            messages=[{"role": "user", "content": _prompt(jira_card, run_result)}],
        )
    except anthropic.AuthenticationError:
        return {"error": "Anthropic kimlik dogrulamasi basarisiz — anahtari kontrol et"}
    except anthropic.RateLimitError:
        return {"error": "Anthropic hiz siniri — biraz sonra tekrar dene"}
    except anthropic.APIStatusError as exc:
        return {"error": f"Anthropic API hatasi {exc.status_code}: {str(exc)[:200]}"}
    except anthropic.APIConnectionError:
        return {"error": "Anthropic API'ye baglanilamadi (ag hatasi)"}

    # Guvenlik siniflandiricisi reddedebilir — content'e bakmadan once kontrol et
    if response.stop_reason == "refusal":
        return {"error": "Model istegi reddetti (guvenlik siniflandiricisi)"}

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        parsed = json.loads(text)
    except ValueError:
        return {"error": "Model yaniti JSON olarak cozulemedi", "ham": text[:400]}

    parsed["_meta"] = {
        "model": response.model,
        "effort": EFFORT,
        "girdiToken": response.usage.input_tokens,
        "ciktiToken": response.usage.output_tokens,
    }
    return parsed
