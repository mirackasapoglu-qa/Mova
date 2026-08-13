# QA Endpoint Panosu — OPRAS

161 path / 237 operasyon tek ekranda: dokümante örnek istek, beklenen şema, bilinen
envelope sapmaları ve **canlı test** butonu.

## Çalıştır

```bash
.venv/bin/python qa-dashboard/build_registry.py   # spec -> registry (kartlar)
.venv/bin/python qa-dashboard/link_jira.py        # TP kartlarini uclara bagla (opsiyonel)
.venv/bin/python qa-dashboard/server.py           # http://127.0.0.1:8777
```

Farklı port: `QA_PANEL_PORT=8778 .venv/bin/python qa-dashboard/server.py`

Ortam `.env`'den okunur: `BASE_URL`, `TENANT_ID`, `ACCESS_TOKEN` (opsiyonel).

## İki görünüm

Sağ üstteki **Uçlar / Jira kartları** düğmesiyle panelin ekseni değişir
(`#jira` hash'i ile doğrudan açılabilir):

- **Uçlar** — sözleşmeden gelen 237 operasyon; her ucun altında onu kapsayan Jira kartları.
- **Jira kartları** — TP projesindeki 915 kart; statü/tip/eşleşme filtreleri, karttan
  ilgili uca tek tıkla geçiş (uç görünümüne atlar ve o kartı açar).

## Ne yapar

- **Sol:** operasyon listesi — path/özet/servis araması, servis + metot filtresi,
  "sadece mutating" ve "sapma işaretli" görünümleri. ▲ = bilinen envelope sapması.
- **Sağ:** seçili operasyon → sözleşme özeti (dokümante status, şema var mı, auth,
  mutating mi), path/query parametre alanları, dokümante örnek gövde, **Çalıştır**.
- **Gerçek ID getir:** koleksiyonda gerçek ID yok (`{{last_customer_id}}` koşum anında
  doluyordu). Bu buton path parametrelerini canlı koleksiyonlardan çeker — iç içe
  yollarda kademeli çözer (`customerId` → `/v1/customers`, sonra `noteId` →
  `/v1/customers/<id>/notes`). Yer tutucu ID ile uç 404 döndüğü için şema sapmaları
  maskeleniyordu; bu buton o kör noktayı kapatır.
- **Canlı test:** isteği atar, dönen status'ün dokümante olup olmadığını ve gövdenin
  spec şemasına uyup uymadığını değerlendirir; verdict + şema sapma listesi gösterir.

- **Otomatik yorum:** her koşumdan sonra `analyze.py` sapmaları sınıflandırıp Türkçe
  değerlendirme üretir — hangi alan, neden önemli, ne yapılmalı. Şiddet sırası
  `kritik > yüksek > orta > bilgi`. LLM kullanmaz: deterministik, offline ve birim
  testli (`tests/test_analyze.py`, 18 test). Kapsadığı kurallar: 5xx, dokümante
  olmayan status, yer tutucu ID maskelemesi, boş liste, liste yapısı kayması,
  nullable eksiği, para alanı tip uyuşmazlığı, kayıp alan, bilinen sapma baseline'ı,
  yavaş yanıt, Cache-Control, PII.

- **Bağlı Jira kartları:** her uç için o ucu kapsayan TP kartları listelenir (key,
  statü, tip, özet — Jira'ya tıklanabilir link). Listede rozet olarak görünür;
  `Jira: Test'te` filtresiyle QA'in iş kuyruğu (105 uç) süzülebilir,
  `Jira kartı yok` ile kapsanmayan 79 uç görülür.

## Kart ↔ canlı karşılaştırması

Jira kartları beklenen response'u kod bloğu olarak yazıyor — **168 kartta** var,
**129'u** hem beklenen yanıta hem eşleşmiş endpoint'e sahip. Kart görünümünde her
endpoint satırındaki **Çalıştır** butonu ucu koşar ve yanıtı *kartın kendi
beklentisiyle* karşılaştırır (`compare.py`):

- **Kartta var, canlıda yok** → eksik alan listesi
- **Tip farkı** → kart `integer` demiş, canlı `string` dönmüş
- **Fazla alan** → canlıda kartta olmayan alanlar (kart eskimiş olabilir — uyarı, hata değil)

Değerler değil **tipler** karşılaştırılır: kart örnekleri yer tutucu taşır (`uuid`,
`$string`). `id`/`createdAt` gibi her yanıtta değişen alanlar yok sayılır.
Mutating uçlar onay kutusu ister ve kartın kendi istek gövdesini kullanır.
Deterministik ve birim testli (`tests/test_compare.py`, 12 test).

## Claude değerlendirmesi (opsiyonel)

Kural motorları **yapısal** şeyleri yakalar: eksik alan, tip farkı, envelope, status.
Yakalayamadıkları şey kartların **düz metin kabul kriterleridir** — "sidebar rol bazlı
görünürlüğe göre filtrelenmeli", "iptal edilen teklif tekrar gönderilemez". Bunlar JSON
diff'iyle doğrulanamaz.

Koşum sonucunun altındaki **Claude ile değerlendir** butonu kartın açıklamasını ve canlı
yanıtı Claude'a verip her kriteri `sağlanıyor / sağlanmıyor / doğrulanamadı` olarak
işaretletir, her biri için yanıttan kanıt ister.

- **Bu katman kanıt değil, yorumdur.** Verdict'i kurallar belirler; LLM çıktısı ayrı bir
  kutuda "yorum" etiketiyle gösterilir. Deterministik motorlar tekrarlanabilir, bu değil.
- Yapısal bulgular prompt'a verilir ki model onları tekrar etmesin.
- Yanıt gövdesi **PII maskelendikten sonra** gönderilir.
- **Veri sınırı:** bu çağrı kart metnini ve maskelenmiş yanıtı Anthropic API'ye gönderir —
  kurum verisi altyapı dışına çıkar. Kullanmadan önce kabul edilmeli.
- Kimlik: `ANTHROPIC_API_KEY` ya da `ant auth login` profili. Yoksa buton nedenini söyler.
- Ayarlanabilir: `QA_AI_MODEL` (varsayılan `claude-opus-5`), `QA_AI_EFFORT` (`medium`).

## Güvenlik duruşu

- Token **yalnızca bellekte** tutulur, diske yazılmaz.
- Mutating operasyonlar (POST/PUT/PATCH/DELETE) açık onay kutusu ister; onay kapısı
  yapılandırmadan bağımsız olarak her zaman uygulanır.
- Yanıt gövdesindeki PII alanları (email, phone, iban, token, taxNumber…) maskelenir.
- Sunucu yalnızca `127.0.0.1`'e bağlanır.

## Dosyalar

- `build_registry.py` — `contract/openapi.json` → `registry.json`. Elle girilen alanlar
  (`status`, `verdict`, `notes`, `owner`, `jira`, `checklist`) yeniden üretimde **korunur**.
- `server.py` — stdlib HTTP sunucu (yalnız `requests` + `jsonschema` bağımlı).
- `index.html` — tek dosya UI.
- `link_jira.py` — TP kartlarını içeriğine göre endpoint'lere bağlar. Eşleştirme
  **şekil** üzerinden: parametre adları önemsiz, yapı önemli
  (`GET /api/projects/:id` ≡ `GET /v1/projects/{projectId}`). `/api` → `/v1` öneki
  ve `:id`/somut UUID → `{}` normalize edilir. Eşleşmeyen yollar
  `reports/jira-unmatched.md`'ye yazılır — sözleşme/kart drift sinyalidir.
- `registry.json` — kart verisi (üretilmiş + elle zenginleştirilebilir).
