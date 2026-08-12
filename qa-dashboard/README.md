# QA Endpoint Panosu — OPRAS

161 path / 237 operasyon tek ekranda: dokümante örnek istek, beklenen şema, bilinen
envelope sapmaları ve **canlı test** butonu.

## Çalıştır

```bash
.venv/bin/python qa-dashboard/build_registry.py   # spec -> registry (kartlar)
.venv/bin/python qa-dashboard/server.py           # http://127.0.0.1:8777
```

Farklı port: `QA_PANEL_PORT=8778 .venv/bin/python qa-dashboard/server.py`

Ortam `.env`'den okunur: `BASE_URL`, `TENANT_ID`, `ACCESS_TOKEN` (opsiyonel).

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
- `registry.json` — kart verisi (üretilmiş + elle zenginleştirilebilir).
