$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $ScriptDir "start_remote_access.bat"

if (!(Test-Path $StartScript)) {
    throw "start_remote_access.bat not found: $StartScript"
}

$TaskName = "AzmusERPRemoteAccess"
$Action = New-ScheduledTaskAction -Execute $StartScript
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Starts Azmus ERP local backend/frontend and Cloudflare Tunnel when the server user logs in." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Trigger: current user logon ($env:USERDOMAIN\$env:USERNAME)"
Write-Host "Start now with:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"

