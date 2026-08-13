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

| Ölçüm | Yer tutucu ID | **Gerçek ID (çözümlemeli)** |
|---|---:|---:|
| Toplam GET operasyonu | 102 | 102 |
| 2xx dönen | 49 | **86** |
| Dokümante olmayan status | 33 | **9** |
| Envelope sapması | 1 | **1** |
| **Şema sapması** | 9 | **28** |

Sağdaki kolon `contract/sweep.py`'nin path parametrelerini canlı koleksiyonlardan
çözümlemesiyle alındı (42 uçta gerçek ID bulundu, 8'inde ilgili koleksiyon boş
olduğu için çözülemedi). Yer tutucu ID kullanıldığında uçlar 404 dönüyor ve 404
sözleşmeye uygun olduğundan sonuç "uyumlu" görünüyordu — **19 şema sapması bu
şekilde maskelenmişti.**

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
| `GET /v1/customers/{id}` | `data.taxNumber` | `null` | `"32266764006"` (string) |
| `GET /v1/customers/{id}` | `data.taxOffice` | `null` | `"Küçükyalı"` (string) |

Bireysel (`customerKind: individual`) müşteride vergi alanları doğal olarak boş;
şema `string` diyor. Alanlar `nullable` işaretlenmeli.

## C2b. Para alanı tip uyuşmazlığı — `totalRevenue`

| Endpoint | Alan | Canlı | Doküman |
|---|---|---|---|
| `GET /v1/customers/{id}` | `data.totalRevenue` | `141591.45` (float) | tamsayı örnek → `integer` |

Dokümante örnekte tam sayı verildiği için şema `integer` çıkarıldı; canlı ondalıklı
dönüyor. `integer` olarak parse eden istemci ya kırılır ya kuruşu yuvarlar.

Ayrıca: para alanının **float** dönmesi hassasiyet açısından riskli. Aynı yanıtta
`quotes` tarafında `totalAmount` **string** (`"15000.00"`) olarak dönüyor — yani para
temsili servisler arasında tutarsız. Tek bir konvansiyon (tercihen string/decimal)
belirlenmeli.

> Bu üç bulgu, path parametresi **gerçek bir ID ile** doldurulduğunda ortaya çıktı.
> Yer tutucu ID kullanıldığında uç 404 döndüğü için sapmalar maskeleniyordu — panelin
> "Gerçek ID getir" özelliği (`/api/resolve/<key>`) tam olarak bu kör noktayı kapatır.

Departmanı olmayan kullanıcı `null` döndürüyor; şema `string` diyor. Tip olarak
`string` bekleyen istemci kırılır — alanlar `nullable` işaretlenmeli.

`/v1/auth/me` → `tenantId: null` multi-tenant bir sistemde ayrıca teyit gerektirir
(test: `test_me_carries_tenant_context`, xfail olarak izleniyor).

## C2c. `permissions` üç ayrı şekle sahip — YÜKSEK ÖNCELİK

Aynı kavram üç farklı yapıda dönüyor:

| Kaynak | Şekil |
|---|---|
| `GET /v1/auth/me` (canlı) | `["DASHBOARD_VIEW", "REQUEST_VIEW", …]` — düz string dizisi |
| `GET /v1/roles/{roleId}` (canlı) | `[{roleId, permissionId, permission:{id, code, category, description}}]` |
| `GET /v1/roles/{roleId}` (doküman) | `[{id, code, category}]` |

Canlı yanıt **ORM join satırını** (`role_permissions`) olduğu gibi dışa veriyor;
gerçek izin bir seviye daha derinde (`permission.code`). Doküman düz nesne dizisi
gösteriyor.

**Etki:** FE `permissions[i].code` okuyorsa `undefined` alır —
`permissions[i].permission.code` yazması gerekir. Şema doğrulaması bu uçta
**309 hata** üretti (103 izin × 3 eksik alan), yani en yüksek sapmalı uç.

**Öneri:** join satırı yerine düzleştirilmiş bir DTO dönülmeli ve `permissions`
temsili `/auth/me` ile hizalanmalı.

## C2d. Detay uçlarında yaygın nullable eksiği

Gerçek ID ile çağrılan detay uçlarında, doğal olarak boş olabilen alanlar `null`
dönüyor ama şema dolu tip bekliyor:

| Endpoint | `null` dönen alanlar |
|---|---|
| `GET /v1/tasks/{taskId}` | `assignedTo`, `assignedUser`, `dueDate`, `project` |
| `GET /v1/quotes/{quoteId}` | `cancelReason`, `cancelComment`, `cancelledAt`, `cancelledByUser` |
| `GET /v1/customers/{customerId}` | `taxNumber`, `taxOffice`, `vipProfile` |

Atanmamış görev, iptal edilmemiş teklif, bireysel müşteri — hepsi normal durumlar.
Alanlar `nullable` işaretlenmeli. Ayrıca `GET /v1/tasks/{taskId}` yanıtında
`requestService.checkInDate` sözleşmede zorunlu ama canlıda yok, ve
`GET /v1/quotes/{quoteId}` alan adı canlıda `quoteCode`, dokümanda `code`.

## C3. Detay uçlarında 404 dokümante değil (32 operasyon)

Var olmayan bir ID ile çağrıldığında 404 dönen ama bunu dokümante etmeyen uçlar:
`/v1/projects/{projectId}`, `/v1/tasks/{taskId}`, `/v1/quotes/{quoteId}`,
`/v1/requests/{requestId}`, `/v1/roles/{roleId}`, `/v1/cms/*/{id}` ailesi …

Davranış doğru (envelope'a uyan 404), eksik olan dokümantasyon.

## C4. 401 neredeyse hiç dokümante değilmiş

Tokensiz koşumda 102 GET ucunun **97'si** 401 döndü; koleksiyon bunu yalnızca ~5
operasyonda dokümante etmiş. Davranış doğru, dokümantasyon eksik.

## C5. Jira kartları ↔ sözleşme drift'i

TP projesindeki 915 kartın 610'u endpoint referansı içeriyor; bunların 505'i (%83)
sözleşmedeki bir operasyonla eşleşti. Eşleşmeyen 164 yol iki gruba ayrılıyor
(tam liste: `reports/jira-unmatched.md`, üretici: `qa-dashboard/link_jira.py`):

**Canlıya sorularak doğrulananlar** (TP-134 üzerinden):

| Endpoint | Canlı | Sonuç |
|---|---|---|
| `GET /v1/sidebar/menu` | **200** | Sözleşmede var, çalışıyor |
| `GET /v1/sidebar/counts` | **404** `ERR_NOT_FOUND` | **Kasıtlı olarak kaldırılmış** — bug değil |
| `GET /v1/navigation/menu` | **404** | Hiç yazılmamış; işlevi `sidebar/menu`'ye taşınmış |

> **Bu bir kusur DEĞİL — kart hijyeni sorunu.** TP-367 (*BE - Sidebar Menü ve Sayı
> API'sinin Yeniden Yapılandırılması*, 2026-07-17, Ready For Release) açıkça şöyle
> diyor: *"Mevcut `GET /v1/sidebar/counts` endpoint'i kaldırılıp yerine her menü öğesi
> için görünürlük ve sayı bilgisini birlikte dönen yeni yapı gelecek: `GET /v1/sidebar/menu`"*.
>
> Yani `visible` (rol bazlı menü, eski `navigation/menu`'nün işi) ve `count`
> (eski `sidebar/counts`) tek uçta birleştirilmiş. 404'ler planlı.

**Asıl risk:** TP-134 (FE, statü **Test**) ve TP-135 (BE, **Ready For Release**) hâlâ
yeniden yapılandırma öncesi yolları kabul kriteri olarak taşıyor. Bu kartları test eden
biri 404 görüp **yanlışlıkla bug açar**. Kartların kabul kriterleri güncellenmeli.
Aynı durumdaki kartlar: `sidebar/counts` geçen 30 kart (TP-83, TP-85, TP-95, TP-107,
TP-118, TP-130, TP-131, TP-240/241/242 …).

**Bonus bulgu — gateway 404'ü envelope uygulamıyor:**

```
GET /v1/navigation/menu  (gateway'de route yok)
  {"message":"Cannot GET /v1/navigation/menu","error":"Not Found","statusCode":404}

GET /v1/sidebar/counts   (servise ulasiyor, route yok)
  {"success":false,"error":{"code":"ERR_NOT_FOUND","message":"Cannot GET /sidebar/counts"}}
```

Bilinmeyen bir yol gateway seviyesinde yakalanırsa NestJS varsayılan gövdesi dönüyor;
servise ulaşırsa envelope uygulanıyor. C1'deki `projects/notes` 403 bulgusuyla aynı kök:
global exception filter her katmanda devrede değil.

**Diğer drift adayları:**

| Kartlarda geçen | Sözleşmede olan | Kart |
|---|---|---:|
| `GET/POST/PATCH /v1/cms/campuses` | yalnızca iç içe: `/v1/cms/schools/{id}/campuses` | 21 |
| `GET /v1/projects/{id}/participants/template` | `/v1/projects/participants/template` (projectId **yok**) | 6 |
| `PATCH /v1/tasks/{id}/status` | sözleşmede yok | 4 |

**Kısaltma kaynaklı (muhtemelen kart metninde `cms` öneki atlanmış):**
`/v1/events`, `/v1/banners`, `/v1/categories` → sözleşmede `/v1/cms/events`,
`/v1/cms/banners`, `/v1/cms/categories`.

Her iki grup da doğrulanmalı: uç gerçekten yok mu, koleksiyonda mı eksik, yoksa
kart mı eski bir yolu referans veriyor?

## C6. Sözleşmede sabit değer gömülü yollar

Koleksiyondaki negatif test istekleri somut değerlerle yazıldığı için 9 yol ayrı
operasyon olarak üretildi:

```
/v1/cms/schools/99999999-9999-4999-8999-999999999999
/v1/cms/schools/not-a-uuid
/v1/customers/00000000-0000-0000-0000-000000000000
/v1/locations/provinces/34/districts
```

Bunlar parametrelenirse 161 path → 159'a iner ve negatif örnekler ilgili
parametreli operasyonun dokümante 404/400 yanıtlarını zenginleştirir.
`contract/postman_to_openapi.py` içinde normalize edilmeli.

## C7. Doğrulanmamış `sortOrder` servisi çökertiyor + kaynak kod sızıntısı — KRİTİK

`GET /v1/customers?sortBy=id&sortOrder=yukari` → **HTTP 500**

Geçersiz enum değeri doğrulanmadan Prisma'ya geçiyor. Yanıt gövdesi (712 karakter)
sunucunun iç yapısını olduğu gibi istemciye veriyor:

```
Invalid `this.prisma.customer.findMany()` invocation in
/root/opras-development/opras-crm-service/src/customers/customers.service.ts:61:28

  58 if (filters?.customerType) where.customerType = filters.customerType;
  → 61   this.prisma.customer.findMany({
           where: { tenantId: "00000000-0000-0000-0000-000000000001", deletedAt: null },
```

**İki ayrı kusur:**

1. **Girdi doğrulama yok** — `sortOrder` bir enum (`asc`/`desc`) olmalı; kabul edilmeyen
   değer 400 ile reddedilmeli, servis çökmemeli. Bir istemci hatası tüm isteği 500'e
   çeviriyor.
2. **Bilgi ifşası** — yanıt mutlak dosya yolunu, kaynak kod satırlarını, ORM sorgusunu
   ve tenant kimliğini sızdırıyor. Ayrıca yol (`/root/...`) servisin **root** kullanıcısı
   ile koştuğunu gösteriyor. Üretimde bu gövde istemciye asla dönmemeli; genel bir
   hata mesajı + `correlationId` yeterli.

Testler: `test_boundary.py::test_invalid_sorting_is_rejected_not_crashing[gecersiz sortOrder]`
ve `test_security.py::test_server_error_does_not_leak_source_code` — ikisi de `xfail`
olarak izleniyor, düzeltilince `XPASS` verip görünür olacak.

> Not: `sortBy=gecersizAlan` ve `sortBy=id; DROP TABLE` **çökmüyor** — yalnızca
> `sortOrder` yolunda doğrulama eksik.

## C8. Güvenlik başlıkları eksik, parmak izi başlığı var

`GET /v1/auth/me` yanıt başlıkları:

| Başlık | Durum |
|---|---|
| `X-Content-Type-Options: nosniff` | **yok** |
| `Strict-Transport-Security` | **yok** |
| `X-Powered-By` | **var** — sunucu teknolojisini ifşa ediyor |

İlk ikisi MIME-sniffing ve protokol düşürme saldırılarına karşı temel korumadır.
`X-Powered-By` kaldırılmalı (NestJS/Express'te tek satır: `app.disable('x-powered-by')`).

Test: `test_security.py::test_security_headers` (`xfail`).

## C9. Dokümante istek gövdesi canlıda reddediliyor — `POST /v1/customers`

Koleksiyonun kendi dokümante ettiği örnek gövde gönderildiğinde **400** dönüyor:

```
POST /v1/customers  (sözleşmedeki örnek gövde)
→ 400 ERR_VALIDATION
   isVip alanı tanınmıyor.
   fullName alanı tanınmıyor.
   firstName alanı boş bırakılamaz.
   lastName alanı boş bırakılamaz.
   nationalId alanı boş bırakılamaz.
```

**Doküman kendi içinde de tutarsız:** örnek `customerKind: "individual"` diyor ama
bir kurumsal alan olan `companyName` ve tanınmayan `fullName` gönderiyor.

**Canlıdan keşfedilen gerçek sözleşme:**

| | |
|---|---|
| Zorunlu | `customerKind` ∈ {`individual`, `corporate`} · `customerType` ∈ {`vip`, `school`, `corporate`, `sports_club`, `other`} |
| `individual` için ek zorunlu | `firstName`, `lastName`, `nationalId` (TC checksum doğrulanıyor) |
| Tanınmayan (reddedilen) | `fullName`, `isVip` |

**Etki:** Dokümana bakarak istek kuran bir istemci doğrudan 400 alır. Doküman bir
talimattır; örneği çalışmıyorsa entegrasyon rehberi olarak işlevsizdir.

Test: `test_crud_customers.py::test_documented_example_is_accepted` (`xfail`).

> **Olumlu bulgu:** API tanımsız alanları sessizce yutmuyor, açıkça reddediyor
> (`forbidNonWhitelisted`). Mass-assignment denemesi de başarısız oldu — gövdede
> gönderilen `tenantId` ve `id` kabul edilmedi. Güvenlik duruşu bu noktada doğru.

## Açık sorular

- **Canlı ortam adresi** — `BASE_URL` henüz tanımlı değil; canlı koşum yapılamadı.
- **Rate limit** — `otp/request` `OTP_LOOKUP_RATE_LIMITED` (429) döndürüyor. Otomasyonun
  hesabı kilitlememesi için negatif testler bilinçli olarak lookup öncesi validation'a
  takılacak şekilde yazıldı (`tests/api/test_auth.py`).
- **Hesap numaralandırma** — kayıtlı olmayan e-posta `404 USER_NOT_FOUND` +
  *"Bu e-posta adresi sistemde kayıtlı değil"* döndürüyor. Bilinçli bir ürün kararı
  olabilir; değilse geçerli/geçersiz e-posta ayrımı yapılmamalı.
