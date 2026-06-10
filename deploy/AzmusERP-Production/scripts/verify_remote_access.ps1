param(
    [string]$PublicUiUrl = "",
    [string]$PublicApiUrl = "",
    [string]$LanHost = ""
)

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (!$LanHost) {
    $LanHost = powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "get_lan_ip.ps1")
}

$checks = @(
    @{ Name = "Local API"; Url = "http://127.0.0.1:8000/" },
    @{ Name = "LAN API"; Url = "http://$LanHost`:8000/" },
    @{ Name = "LAN UI"; Url = "http://$LanHost`:5173" }
)

if ($PublicApiUrl) {
    $checks += @{ Name = "Public API"; Url = $PublicApiUrl.TrimEnd("/") + "/" }
}
if ($PublicUiUrl) {
    $checks += @{ Name = "Public UI"; Url = $PublicUiUrl.TrimEnd("/") }
}

foreach ($check in $checks) {
    Write-Host ""
    Write-Host "== $($check.Name): $($check.Url)"
    try {
        $response = Invoke-WebRequest -Uri $check.Url -UseBasicParsing -TimeoutSec 20
        Write-Host "HTTP $($response.StatusCode)"
        if ($check.Name -like "*API") {
            $json = $response.Content | ConvertFrom-Json
            $summary = [ordered]@{
                active_database_path = $json.active_database_path
                database_size = $json.database_size
                table_count = $json.table_count
                orders_count = $json.orders_count
                tasks_count = $json.tasks_count
                documents_count = $json.documents_count
                mes_jobs_count = $json.mes_jobs_count
                users_count = $json.users_count
                database_guard_enabled = $json.database_guard_enabled
            }
            $summary | ConvertTo-Json -Depth 3
        }
    }
    catch {
        Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Manual verification:"
Write-Host "  Office LAN: open http://$LanHost`:5173"
if ($PublicUiUrl) {
    Write-Host "  Mobile internet: disable Wi-Fi and open $PublicUiUrl"
    Write-Host "  External PC: open $PublicUiUrl"
}
else {
    Write-Host "  Public URL not supplied. Re-run with -PublicUiUrl and -PublicApiUrl."
}

