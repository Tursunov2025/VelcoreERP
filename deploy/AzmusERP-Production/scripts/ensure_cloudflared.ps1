# Download cloudflared to D:\AzmusERP\tools if missing.
$ErrorActionPreference = "Stop"

$ToolsDir = "D:\AzmusERP\tools"
$Exe = Join-Path $ToolsDir "cloudflared.exe"

if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
    return (Get-Command cloudflared).Source
}

if (Test-Path $Exe) {
    return $Exe
}

New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null
$Url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
Write-Host "Downloading cloudflared to $Exe ..."
Invoke-WebRequest -Uri $Url -OutFile $Exe
if (!(Test-Path $Exe)) {
    throw "Failed to download cloudflared"
}
Write-Host "Installed: $Exe"
return $Exe
