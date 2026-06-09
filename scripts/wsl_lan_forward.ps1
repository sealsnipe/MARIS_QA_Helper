#Requires -Version 5.1
<#
.SYNOPSIS
  Forward a TCP port from Windows (LAN) to the current WSL2 instance.

.DESCRIPTION
  WSL2 exposes dev servers on its virtual IP (e.g. 172.31.x.x). localhost works
  automatically, but LAN clients hitting the Windows host IP need portproxy + firewall.

.EXAMPLE
  .\wsl_lan_forward.ps1 setup
  .\wsl_lan_forward.ps1 setup -Port 8090
  .\wsl_lan_forward.ps1 remove
  .\wsl_lan_forward.ps1 status
#>
param(
    [ValidateSet("setup", "remove", "status")]
    [string]$Action = "setup",

    [int]$Port = 8090,

    [string]$WslDistro = ""
)

$ErrorActionPreference = "Stop"
$FirewallRuleName = "WSL Dev Port $Port"

function Get-WslIpAddress {
    param([string]$Distro)
    $args = @("hostname", "-I")
    if ($Distro) {
        $args = @("-d", $Distro) + $args
    }
    $raw = & wsl.exe @args 2>$null
    if (-not $raw) {
        throw "WSL IP nicht ermittelbar. Läuft WSL?"
    }
    $ip = ($raw.Trim() -split "\s+")[0]
    if ($ip -notmatch "^\d+\.\d+\.\d+\.\d+$") {
        throw "Ungültige WSL IP: '$ip'"
    }
    return $ip
}

function Get-LanIpv4Addresses {
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notmatch "^(127\.|169\.254\.)" -and
            $_.PrefixOrigin -ne "WellKnown"
        } |
        Select-Object -ExpandProperty IPAddress -Unique
}

function Show-PortProxyRules {
    $rules = netsh interface portproxy show v4tov4 | Select-String "^\d"
    if (-not $rules) {
        Write-Host "  (keine portproxy-Regeln)"
        return
    }
    $rules | ForEach-Object { Write-Host "  $_" }
}

function Test-Admin {
    $principal = New-Object Security.Principal.WindowsPrincipal(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Ensure-Admin {
    if (Test-Admin) { return }
    $self = $PSCommandPath
    $argList = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$self`"",
        "-Action", $Action,
        "-Port", $Port
    )
    if ($WslDistro) {
        $argList += @("-WslDistro", $WslDistro)
    }
    Write-Host "Administrator-Rechte noetig - UAC-Dialog oeffnet sich ..."
    Start-Process powershell.exe -Verb RunAs -Wait -ArgumentList $argList
    exit $LASTEXITCODE
}

function Remove-PortForward {
    param([string]$ListenAddress, [int]$ListenPort)
    netsh interface portproxy delete v4tov4 listenaddress=$ListenAddress listenport=$ListenPort 2>$null | Out-Null
}

function Add-PortForward {
    param([string]$ListenAddress, [int]$ListenPort, [string]$ConnectAddress, [int]$ConnectPort)
    netsh interface portproxy add v4tov4 `
        listenaddress=$ListenAddress listenport=$ListenPort `
        connectaddress=$ConnectAddress connectport=$ConnectPort | Out-Null
}

function Ensure-FirewallRule {
    param([int]$LocalPort, [string]$RuleName)
    $existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Firewall-Regel existiert bereits: $RuleName"
        return
    }
    New-NetFirewallRule `
        -DisplayName $RuleName `
        -Direction Inbound `
        -LocalPort $LocalPort `
        -Protocol TCP `
        -Action Allow | Out-Null
    Write-Host "  OK Firewall-Regel angelegt: $RuleName"
}

switch ($Action) {
    "status" {
        $wslIp = Get-WslIpAddress -Distro $WslDistro
        Write-Host "WSL IP:        $wslIp"
        Write-Host "Ziel-Port:     $Port"
        Write-Host "LAN-IPs:"
        $lanIps = Get-LanIpv4Addresses
        if ($lanIps) {
            $lanIps | ForEach-Object { Write-Host "  http://${_}:$Port" }
        } else {
            Write-Host "  (keine LAN-IPv4 gefunden)"
        }
        Write-Host "portproxy:"
        Show-PortProxyRules
        Write-Host "Firewall:"
        $rule = Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue
        if ($rule) {
            Write-Host "  OK $FirewallRuleName"
        } else {
            Write-Host "  FEHLT $FirewallRuleName"
        }
        exit 0
    }

    "remove" {
        Ensure-Admin
        Remove-PortForward -ListenAddress "0.0.0.0" -ListenPort $Port
        $fw = Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue
        if ($fw) {
            Remove-NetFirewallRule -DisplayName $FirewallRuleName
            Write-Host "  OK Firewall-Regel entfernt"
        }
        Write-Host "Port-Weiterleitung für :$Port entfernt."
        exit 0
    }

    "setup" {
        Ensure-Admin
        $wslIp = Get-WslIpAddress -Distro $WslDistro
        Write-Host "WSL IP: $wslIp"
        Write-Host "Port-Weiterleitung 0.0.0.0:$Port -> ${wslIp}:$Port"

        Remove-PortForward -ListenAddress "0.0.0.0" -ListenPort $Port
        Add-PortForward -ListenAddress "0.0.0.0" -ListenPort $Port -ConnectAddress $wslIp -ConnectPort $Port
        Write-Host "  OK portproxy gesetzt"

        Ensure-FirewallRule -LocalPort $Port -RuleName $FirewallRuleName

        Write-Host ""
        Write-Host "LAN-Zugriff (nach ./scripts/dev_local.sh start):"
        $lanIps = Get-LanIpv4Addresses
        if ($lanIps) {
            $lanIps | ForEach-Object { Write-Host "  http://${_}:$Port" }
        } else {
            Write-Host "  http://<windows-lan-ip>:$Port"
        }
        Write-Host ""
        Write-Host "Hinweis: Nach wsl --shutdown WSL-IP neu ermitteln: ./scripts/wsl_lan_forward.sh setup"
        exit 0
    }
}
