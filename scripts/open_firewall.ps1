param(
    [int]$Port = 4000,
    [string]$RuleName = "DailyBook TCP"
)
$ErrorActionPreference = "Stop"
if ($Port -lt 1024 -or $Port -gt 65535) { throw "Port must be between 1024 and 65535." }
$displayName = "$RuleName $Port"
New-NetFirewallRule -DisplayName $displayName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Private
Write-Host "Firewall rule created for TCP port $Port on the Private profile."
