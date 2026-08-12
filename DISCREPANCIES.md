# Sözleşme Bulguları — OPRAS API

Kaynak: `OPRAS API.postman_collection.json` (391 request, 1041 kayıtlı örnek yanıt)
Analiz: `contract/postman_to_openapi.py` → `contract/openapi.json` → envelope doğrulaması
Tarih: 2026-08-12

Bu belge **koleksiyon ile envelope sözleşmesi arasındaki** farkları listeler. Henüz
canlı ortama karşı koşum yapılmadı (`BASE_URL` tanımlı değil); buradaki bulgular
dokümanın kendi iç tutarlılığından çıkmıştır. Canlı koşum yapıldığında ikinci bir
fark kümesi (doküman ↔ canlı) oluşacaktır.

Makine tarafından okunan baseline: [`contract/envelope_exceptions.json`](./contract/envelope_exceptions.json)
— `pytest -m schema` bu listeyi kullanır: listedeki sapmalar testi kırmaz, **listede
olmayan yeni bir sapma kırar**. Sapma düzeltilince girdi listeden silinmelidir.

## Özet

| Kategori | Adet | Ne demek |
|---|---:|---|
| `envelope-disi` | 3 | **Gerçek bulgu** — global envelope uygulanmamış |
| `yanlis-status-eslemesi` | 1 | **Gerçek bulgu** — örnek/davranış uyuşmazlığı |
| `placeholder-dsl` | 4 | Doküman borcu — örnek gövde assertion yer tutucusu içeriyor |
| `eksik-ornek` | 21 | Doküman borcu — örnek kısaltılmış |
| `mesru-istisna` | 2 | Kural dışı ama doğru |

Beklenen envelope:

```jsonc
// başarı
{ "success": true, "data": …, "meta": {…}?, "correlationId": "…"?, "timestamp": "…"? }
// hata
{ "success": false, "error": { "code": "…", "message": "…", "errors": [{field, message}]? } }
```

---

## 1. Global envelope uygulanmamış (3) — GERÇEK BULGU

`projects/notes` uçlarındaki **403** yanıtları envelope yerine NestJS'in varsayılan
exception filter çıktısını döndürüyor:

| Operasyon | Dönen gövde |
|---|---|
| `POST /v1/projects/{projectId}/notes` [403] | `{"statusCode":403,"message":"Cannot add notes to a closed project","error":"Forbidden"}` |
| `PATCH /v1/projects/{projectId}/notes/{noteId}` [403] | `{"statusCode":403,"message":"You can only edit your own notes","error":"Forbidden"}` |
| `DELETE /v1/projects/{projectId}/notes/{noteId}` [403] | `{"statusCode":403,"message":"You can only delete your own notes","error":"Forbidden"}` |

**Neden önemli:** İstemci tarafı hata işleme `error.code` üzerinden yazılıyorsa bu üç
yolda kırılır — `success` alanı da yok, `error` bir nesne değil string. Diğer tüm
403'ler (`ERR_FORBIDDEN`) envelope'a uyuyor; yani sorun global filter'ın bu
controller'da devrede olmaması.

**Doğrulanacak:** Bu davranış canlıda da böyle mi, yoksa yalnızca örnek mi eski?
Canlı testte `POST /v1/projects/{id}/notes` kapalı bir projeye karşı çağrılmalı.

## 2. Başarı gövdesi hata status'u altında (1) — GERÇEK BULGU

| Operasyon | Sorun |
|---|---|
| `POST /v1/quotes/{quoteId}/send` [422] | 422 altında `{"success":true,"data":{"status":"sent",…}}` dokümante edilmiş |

Ya örnek yanlış status'a yerleştirilmiş ya da uç gerçekten 422 ile başarı dönüyor.
İkincisi doğruysa istemci mantığı bozulur.

## 3. Assertion yer tutucusu içeren örnekler (4)

Örnek gövdeler gerçek veri değil, test ifadesi içeriyor (`$string`, `$gte:2`, `$uuid`,
`$contains:…`). Bu uçlarda şema doğrulaması yapılamıyor:

- `GET /v1/requests/{requestId}/activities` [200] — `"metadata": "$string"`, `"total": "$gte:1"`
- `GET /v1/projects/drafts` [200] — `"data": "$array"`, `"meta": {"total": "$gte:2"}`
- `PATCH /v1/projects/{projectId}` [400] — `errors[]` içinde `$contains:…`
- `DELETE /v1/cms/events/{cmsEventId}/price-groups/{cmsPriceGroupBusId}` [404] — `error.code` yok

## 4. Kısaltılmış örnekler (21)

İki alt kalıp:

- **`{"success": false}`** — `error` nesnesi hiç yazılmamış (13 operasyon; `requests`,
  `tasks`, `notifications`, `quotes`, `projects/drafts`, `customers/preferences`)
- **`error.message` eksik** — sadece `code` var (8 operasyon; `INVALID_MANAGER`,
  `INVALID_DEPARTMENT`, `LAT_LNG_REQUIRED_TOGETHER`, `EXPENSE_APPROVED_LOCKED` …)

Canlı yanıt `message` döndürüyorsa örnek eksiktir; döndürmüyorsa API eksiktir —
istemci kullanıcıya gösterecek metin bulamaz. Canlı koşumda ayrışacak.

## 5. Meşru istisnalar (2)

Envelope beklenmeyen, doğru davranan uçlar:

- `GET /health` — standart health-check gövdesi (`{status, info, details}`)
- `GET /v1/files/{fileId}/download` — binary içerik döndürür, JSON değil

---

## Sözleşme dışı bırakılanlar

Aşağıdaki 4 istek gateway'i **bypass edip doğrudan servise** gidiyor (koleksiyonda
`{{project_url}}` / `{{file_url}}` değişkenleriyle). Farklı bir sunucu oldukları için
gateway sözleşmesine dahil edilmedi — aksi halde her koşumda sahte hata üretirlerdi:

| İstek | Host değişkeni |
|---|---|
| `GET /internal/customer-stats/{customerId}` | `{{project_url}}` |
| `GET /internal/customer-stats/tenant-revenue/{tenantId}` | `{{project_url}}` |
| `POST /internal/customer-stats/batch` | `{{project_url}}` |
| `POST /internal/files/link` | `{{file_url}}` |

Bu uçlar test edilecekse ayrı bir spec + ayrı `BASE_URL` ile ele alınmalı.

---

# Canlı Koşum Bulguları

Ortam: `https://api.opras-test.site` · Tenant: `DEMO_TENANT` · Hesap: `admin@opras.dev` (rol Admin)
Koşum: `contract/sweep.py` — 102 GET operasyonu, token'lı · 2026-08-12

| Ölçüm | Sonuç |
|---|---:|
| Toplam GET operasyonu | 102 |
| 2xx dönen | 49 |
| Dokümante olmayan status | 33 |
| Envelope sapması | 1 |
| Şema sapması | 9 |

## C1. Liste envelope'u dokümandan yapısal olarak farklı — YÜKSEK ÖNCELİK

Koleksiyon çekirdek liste uçlarını **iç içe** (`data.data[]` + `data.meta`) gösteriyor;
canlı **düz** (`data[]` + kök seviye `meta`) dönüyor.

| Endpoint | Canlı | Doküman |
|---|---|---|
| `GET /v1/customers` | `data[] + meta` | `data.data[] + data.meta` |
| `GET /v1/projects` | `data[] + meta` | `data.data[] + data.meta` |
| `GET /v1/tasks` | `data[] + meta` | `data.data[] + data.meta` |
| `GET /v1/requests` | `data[] + meta` | `data.data[] + data.meta` |
| `GET /v1/quotes` | `data[] + meta` | `data.data[] + data.meta` |
| `GET /v1/users` | `data[] + meta` | `data.data[] + data.meta` |
| `GET /v1/approvals` | `data[] + meta` | `data.data[] + data.meta` |
| `GET /v1/expenses` | `data[] + meta` | `data[]` (meta yok) |
| `GET /v1/departments` | `data[] + meta` | `data[]` (meta yok) |

Uyumlu olanlar: `/v1/roles`, `/v1/notifications`, `/v1/cms/schools`.

**Neden önemli:** FE `response.data.data` okuyorsa 7 çekirdek ekranda liste boş gelir.
Alan adları da kaymış — `/v1/quotes` canlıda `quoteCode`, dokümanda `code`.

**Karar gerekli:** doküman mı eski, API mi değişti? Kaynak-of-truth netleşmeden
FE entegrasyonu riskli.

## C2. Dokümante edilmemiş `null` değerler

| Endpoint | Alan | Canlı | Doküman |
|---|---|---|---|
| `GET /v1/lookups/users` | `data[].departmentName` | `null` | `"Operasyon"` (string) |
| `GET /v1/sidebar/menu` | `data.dashboard.count` | `null` | `$number` |
| `GET /v1/auth/me` | `data.tenantId` | `null` | `uuid` |

Departmanı olmayan kullanıcı `null` döndürüyor; şema `string` diyor. Tip olarak
`string` bekleyen istemci kırılır — alanlar `nullable` işaretlenmeli.

`/v1/auth/me` → `tenantId: null` multi-tenant bir sistemde ayrıca teyit gerektirir
(test: `test_me_carries_tenant_context`, xfail olarak izleniyor).

## C3. Detay uçlarında 404 dokümante değil (32 operasyon)

Var olmayan bir ID ile çağrıldığında 404 dönen ama bunu dokümante etmeyen uçlar:
`/v1/projects/{projectId}`, `/v1/tasks/{taskId}`, `/v1/quotes/{quoteId}`,
`/v1/requests/{requestId}`, `/v1/roles/{roleId}`, `/v1/cms/*/{id}` ailesi …

Davranış doğru (envelope'a uyan 404), eksik olan dokümantasyon.

## C4. 401 neredeyse hiç dokümante değilmiş

Tokensiz koşumda 102 GET ucunun **97'si** 401 döndü; koleksiyon bunu yalnızca ~5
operasyonda dokümante etmiş. Davranış doğru, dokümantasyon eksik.

## Açık sorular

- **Canlı ortam adresi** — `BASE_URL` henüz tanımlı değil; canlı koşum yapılamadı.
- **Rate limit** — `otp/request` `OTP_LOOKUP_RATE_LIMITED` (429) döndürüyor. Otomasyonun
  hesabı kilitlememesi için negatif testler bilinçli olarak lookup öncesi validation'a
  takılacak şekilde yazıldı (`tests/api/test_auth.py`).
- **Hesap numaralandırma** — kayıtlı olmayan e-posta `404 USER_NOT_FOUND` +
  *"Bu e-posta adresi sistemde kayıtlı değil"* döndürüyor. Bilinçli bir ürün kararı
  olabilir; değilse geçerli/geçersiz e-posta ayrımı yapılmamalı.
