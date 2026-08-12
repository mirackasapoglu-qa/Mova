#!/usr/bin/env bash
#
# Contract testi — canli OPRAS API'sini contract/openapi.json sozlesmesine karsi dogrular.
#
# Schemathesis "examples" fazi: her operasyon icin yalnizca DOKUMANTE EDILEN ornek
# istek gonderilir (fuzzing YOK); yanitin status / sema / content-type sozlesmeye
# uyup uymadigi kontrol edilir. Sozlesme Postman koleksiyonundan uretildigi icin
# bu kosum "koleksiyon ile canli API arasindaki kayma"yi olcer.
#
# GUVENLIK: varsayilan olarak YALNIZCA GET operasyonlari kosar. Ornekler gercek
# govdeler oldugu icin POST/PATCH/PUT/DELETE calistirmak canli ortamda VERI YARATIR
# ve DEGISTIRIR. Mutating kosum bilincli bir karardir:
#
#   ./contract/run.sh                              # guvenli varsayilan (sadece GET)
#   INCLUDE_SIDE_EFFECTS=1 ./contract/run.sh       # TUM metotlar — canli veri degisir!
#   AUTH_TOKEN=<jwt> ./contract/run.sh             # authli uclar icin Bearer token
#
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then set -a; . ./.env; set +a; fi

if [ -z "${BASE_URL:-}" ]; then
  echo "HATA: BASE_URL tanimli degil (.env doldur ya da BASE_URL=... ile ver)" >&2
  exit 2
fi

if [ ! -f contract/openapi.json ]; then
  echo "HATA: contract/openapi.json yok — once: python contract/postman_to_openapi.py" >&2
  exit 2
fi

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TENANT="${TENANT_ID:-DEMO_TENANT}"

ARGS=(
  contract/openapi.json
  -u "$BASE_URL"
  --phases examples
  -c status_code_conformance,content_type_conformance,response_schema_conformance,not_a_server_error
  -H "User-Agent: $UA"
  -H "x-tenant-id: $TENANT"
  --max-response-time 15
  --report junit
  --report-junit-path reports/contract-junit.xml
)

# Token: acikca verilen AUTH_TOKEN, yoksa .env'deki ACCESS_TOKEN
TOKEN="${AUTH_TOKEN:-${ACCESS_TOKEN:-}}"
if [ -n "$TOKEN" ]; then
  ARGS+=( -H "Authorization: Bearer $TOKEN" )
fi

# Yan etkili metotlar varsayilan olarak haric — canli veri korunur.
if [ "${INCLUDE_SIDE_EFFECTS:-0}" != "1" ]; then
  for method in POST PUT PATCH DELETE; do
    ARGS+=( --exclude-method "$method" )
  done
else
  echo "!! UYARI: mutating metotlar DAHIL — $BASE_URL uzerinde veri yaratilacak/degisecek." >&2
fi

mkdir -p reports
echo "> Contract run -> $BASE_URL  (tenant: $TENANT, side-effects: ${INCLUDE_SIDE_EFFECTS:-0}, auth: $([ -n "$TOKEN" ] && echo yes || echo no))"
exec .venv/bin/schemathesis run "${ARGS[@]}"
