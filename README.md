# OPRAS API Test Suite

OPRAS API (SOA gateway — auth, crm, project, notification, file, approval, core,
event-consumer) için `pytest` tabanlı API test yapısı, sözleşme testi ve QA panosu.

**Sözleşme kaynağı:** `contract/opras.postman_collection.json` — 391 request,
166 path, **1041 kayıtlı örnek yanıt**. OpenAPI 3.0 sözleşmesi bu koleksiyondan
üretilir; servisler kendi Swagger'ını yayınlamıyor.

> Koleksiyon elle bakımlı bir dokümandır ve canlı API ondan **kayabilir**. Sözleşme
> testinin amacı tam olarak bu kaymayı ölçmektir. Servisler ileride canlı `docs-json`
> yayınlarsa kaynak-of-truth oraya taşınmalı, koleksiyon senaryo kaynağı olarak kalmalı.

## Kurulum

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # BASE_URL, TENANT_ID ve auth bilgilerini doldur
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Üretim zinciri

Koleksiyon değiştiğinde iki komut her şeyi tazeler:

```bash
python contract/postman_to_openapi.py    # koleksiyon -> contract/openapi.json
python contract/gen_endpoints.py         # openapi.json -> tests/api/endpoints.py
python qa-dashboard/build_registry.py    # openapi.json -> qa-dashboard/registry.json
```

CI, üretilmiş dosyaların güncel olduğunu doğrular; unutulursa build kırılır.

## Çalıştırma

```bash
pytest -m schema            # sözleşme iç tutarlılığı — AĞSIZ, ortam gerekmez
pytest -m smoke             # kritik akışlar (canlı)
pytest -m negative          # hata senaryoları (canlı)
pytest -m "not mutating"    # varsayılan güvenli koşum
pytest tests/api/test_auth.py
```

Rapor: `reports/report.html`

## Ortam değişkenleri (`.env`)

| Değişken | Açıklama |
|---|---|
| `BASE_URL` | Gateway kök adresi. Koleksiyon varsayılanı `http://localhost:7000` |
| `TENANT_ID` | `x-tenant-id` başlığı — multi-tenant bağlam (varsayılan `DEMO_TENANT`) |
| `TEST_EMAIL` + `OTP_CODE` | OTP akışıyla otomatik token alımı (dev'deki sabit/bypass kod) |
| `ACCESS_TOKEN` | Hazır token — verilirse OTP akışı atlanır |
| `UNKNOWN_EMAIL` | Negatif senaryolar için kayıtlı olmayan e-posta |
| `JIRA_*` | Panel/RAG Jira entegrasyonu (opsiyonel) |

**Auth akışı:** `POST /v1/auth/otp/request` → `POST /v1/auth/otp/verify` →
`data.accessToken`. `ACCESS_TOKEN` ya da `TEST_EMAIL`+`OTP_CODE` yoksa auth
gerektiren testler **skip** edilir — sessizce PASS geçmez.

## Kapsam

| Dosya | İçerik |
|---|---|
| `test_spec_sync.py` | **Ağsız.** endpoints↔spec senkronu, envelope tutarlılığı, baseline bekçiliği |
| `test_auth.py` | Tokensiz erişim, validation reddi, bilinmeyen hesap davranışı |
| `test_smoke.py` | `/auth/me`, çekirdek liste uçları, sayfalama, geçersiz token reddi |

## Contract Testing (Schemathesis)

Canlı API'nin `contract/openapi.json`'a uyumunu doğrular. Schemathesis **`examples`
fazı**: her operasyon için yalnızca dokümante örnek istek gönderilir (fuzzing yok);
yanıtın **status / şema / content-type** sözleşmeye uyup uymadığı kontrol edilir.

**Güvenlik:** varsayılan koşum **yalnızca GET**'tir. Örnekler gerçek gövdeler
olduğundan `POST/PUT/PATCH/DELETE` çalıştırmak canlı ortamda **veri yaratır ve
değiştirir**.

```bash
./contract/run.sh                            # güvenli varsayılan (sadece GET)
INCLUDE_SIDE_EFFECTS=1 ./contract/run.sh     # TÜM metotlar — canlı veri değişir!
AUTH_TOKEN=<jwt> ./contract/run.sh           # authlı uçlar için
```

Windows: `.\contract\run.ps1` (aynı değişkenler `$env:` ile).
Rapor: `reports/contract-junit.xml`

Bulgular: [`DISCREPANCIES.md`](./DISCREPANCIES.md)

## QA Panosu

161 path / 237 operasyon tek ekranda: dokümante örnek istek, beklenen şema, bilinen
envelope sapmaları ve **canlı test** butonu.

```bash
.venv/bin/python qa-dashboard/server.py      # http://127.0.0.1:8777
QA_PANEL_PORT=8778 .venv/bin/python qa-dashboard/server.py
```

- Panelden OTP ile giriş yapılır; **token yalnızca bellekte tutulur, diske yazılmaz**.
- Mutating operasyonlar açık onay ister; yanıt gövdesindeki PII maskelenir.
- Sunucu yalnızca `127.0.0.1`'e bağlanır.
- Kart üzerindeki ▲ işareti o operasyonda bilinen bir envelope sapması olduğunu gösterir.

## Yapı

```
qa_core/
  resolver.py                    # path parametrelerini canlıdan çözümler (sweep + panel paylaşır)
contract/
  opras.postman_collection.json  # kaynak koleksiyon (sözleşmenin kökü)
  sweep.py                       # canlı GET taraması -> tablo/markdown rapor
  postman_to_openapi.py          # koleksiyon -> OpenAPI 3.0 bundle
  gen_endpoints.py               # openapi.json -> tests/api/endpoints.py
  openapi.json                   # üretilmiş sözleşme
  envelope_exceptions.json       # bilinen envelope sapmaları baseline'ı
  run.sh / run.ps1               # Schemathesis koşum betikleri
tests/
  conftest.py                    # config, misafir + authlı client, OTP akışı, şema yükleyici
  api/
    endpoints.py                 # ÜRETİLMİŞ — elle düzenleme
    test_*.py                    # modül başına testler
  utils/
    assertions.py                # assert_status / assert_schema / assert_response_time
    factories.py                 # benzersiz veri + spec'ten dokümante örnek çekme
schemas/                         # success / error envelope şemaları
qa-dashboard/
  build_registry.py              # openapi.json -> registry.json
  link_jira.py                   # TP kartlarını içeriğine göre endpoint'lere bağlar
  analyze.py                     # kural tabanlı otomatik yorum motoru
  server.py                      # yerel pano sunucusu (stdlib + requests)
  index.html                     # tek dosya UI
rag/                             # QA bilgi tabanı (BM25, offline)
```

## Canlı GET taraması

`contract/sweep.py` her GET operasyonunu çağırıp tek satırlık sonuç üretir: alınan
status, dokümante mi, envelope uyumu, şema sapması, süre, gövde önizlemesi (PII maskeli).

```bash
.venv/bin/python contract/sweep.py                     # tablo
.venv/bin/python contract/sweep.py --md rapor.md       # markdown rapor
.venv/bin/python contract/sweep.py --service Customers
.venv/bin/python contract/sweep.py --no-resolve        # yer tutucu ID (eski davranış)
```

Path parametreleri **varsayılan olarak canlıdan çözümlenir** (`qa_core/resolver.py`):
yer tutucu ID kullanıldığında uçlar 404 döner, 404 sözleşmeye uygun olduğu için sonuç
"uyumlu" görünür ve yanıt gövdesi hiç doğrulanmaz. Çözümleme bu kör noktayı kapatır —
ilk koşumda **19 gizli şema sapması** ortaya çıkardı.

## Bilinen kısıtlar

- `otp/request` hız sınırlı (`OTP_LOOKUP_RATE_LIMITED`); negatif testler test hesabını
  kilitlememek için bilinçli olarak lookup öncesi validation'a takılır.
- 4 internal servis ucu (`{{project_url}}` / `{{file_url}}`) gateway sözleşmesi dışında.
- Sweep'te 8 uçta path parametresi çözülemiyor (ilgili koleksiyonda kayıt yok) —
  o uçlar 404 dönüyor ve gövdeleri doğrulanmıyor.
- Jira hesabında `TRANSITION_ISSUES`/`EDIT_ISSUES` yetkisi yok; yalnızca yorum yazılabilir.
