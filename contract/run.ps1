# Contract testi — canli OPRAS API'sini contract/openapi.json sozlesmesine karsi dogrular.
# run.sh'in Windows PowerShell karsiligi.
#
# GUVENLIK: varsayilan olarak YALNIZCA GET operasyonlari kosar. Ornekler gercek
# govdeler oldugu icin mutating metotlar canli ortamda VERI YARATIR/DEGISTIRIR.
#
#   .\contract\run.ps1                                  # guvenli varsayilan (sadece GET)
#   $env:INCLUDE_SIDE_EFFECTS="1"; .\contract\run.ps1    # TUM metotlar — canli veri degisir!
#   $env:AUTH_TOKEN="<jwt>"; .\contract\run.ps1          # authli uclar icin Bearer token

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# .env yukle (KEY=VALUE satirlari)
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $name = $matches[1]
            $value = $matches[2].Trim()
            if (-not [Environment]::GetEnvironmentVariable($name)) {
                [Environment]::SetEnvironmentVariable($name, $value)
            }
        }
    }
}

if (-not $env:BASE_URL) {
    Write-Error "BASE_URL tanimli degil (.env doldur ya da `$env:BASE_URL=... ile ver)"
    exit 2
}

if (-not (Test-Path "contract/openapi.json")) {
    Write-Error "contract/openapi.json yok — once: python contract/postman_to_openapi.py"
    exit 2
}

$ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
$tenant = if ($env:TENANT_ID) { $env:TENANT_ID } else { "DEMO_TENANT" }

$schemaArgs = @(
    "contract/openapi.json"
    "-u", $env:BASE_URL
    "--phases", "examples"
    "-c", "status_code_conformance,content_type_conformance,response_schema_conformance,not_a_server_error"
    "-H", "User-Agent: $ua"
    "-H", "x-tenant-id: $tenant"
    "--max-response-time", "15"
    "--report", "junit"
    "--report-junit-path", "reports/contract-junit.xml"
)

$token = if ($env:AUTH_TOKEN) { $env:AUTH_TOKEN } else { $env:ACCESS_TOKEN }
if ($token) {
    $schemaArgs += @("-H", "Authorization: Bearer $token")
}

if ($env:INCLUDE_SIDE_EFFECTS -ne "1") {
    foreach ($method in @("POST", "PUT", "PATCH", "DELETE")) {
        $schemaArgs += @("--exclude-method", $method)
    }
} else {
    Write-Warning "mutating metotlar DAHIL — $($env:BASE_URL) uzerinde veri yaratilacak/degisecek."
}

New-Item -ItemType Directory -Force -Path "reports" | Out-Null
$authState = if ($token) { "yes" } else { "no" }
$sideState = if ($env:INCLUDE_SIDE_EFFECTS) { $env:INCLUDE_SIDE_EFFECTS } else { "0" }
Write-Host "> Contract run -> $($env:BASE_URL)  (tenant: $tenant, side-effects: $sideState, auth: $authState)"

schemathesis run @schemaArgs
exit $LASTEXITCODE
