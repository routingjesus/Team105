#Requires -Version 5.1
<#
.SYNOPSIS
    End-user launcher for the portable Team105 wizard zip (SPEC-018).

.DESCRIPTION
    Starts the bundled FastAPI API on port 8080 and the prebuilt Next UI on a
    free port (prefer 3000). No Node/Python bootstrap, no npm install, and no
    next build - missing runtimes or UI paths fail with a named error.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\launch-portable.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# --- Constants --------------------------------------------------------------
$RequiredApiPort  = 8080
$PreferredUiPort  = 3000
$ApiReadyTimeout  = 90
$UiReadyTimeout   = 120

# Bundle root is the parent of scripts\ (...\Team105-Wizard\).
$BundleRoot = Split-Path -Parent $PSScriptRoot
$AppDir     = Join-Path $BundleRoot 'app'
$NodeExe    = Join-Path $BundleRoot 'runtime\node\node.exe'
$PythonExe  = Join-Path $BundleRoot 'runtime\python\python.exe'
$ServerJs   = Join-Path $AppDir 'server.js'
$BackendMain = Join-Path $AppDir 'backend\main.py'
$LocationDb = Join-Path $AppDir 'backend\data\location_db.xlsx'
$DrConfig   = Join-Path $AppDir 'backend\data\DRProject.config'

$script:Children  = New-Object System.Collections.ArrayList
$script:TempFiles = New-Object System.Collections.ArrayList

# --- Output helpers ---------------------------------------------------------
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [ok]   $msg" -ForegroundColor Green }
function Write-Info($msg)  { Write-Host "    $msg" }
function Write-Warn2($msg) { Write-Host "    [warn] $msg" -ForegroundColor Yellow }

function Stop-WithError($step, $fallback) {
    Write-Host ""
    Write-Host "ERROR: $step" -ForegroundColor Red
    if ($fallback) { Write-Host "Hint: $fallback" -ForegroundColor Yellow }
    exit 1
}

function Assert-RequiredPath([string]$Path, [string]$What) {
    if (-not (Test-Path -LiteralPath $Path)) {
        Stop-WithError ("Missing required {0} at:{1}  {2}" -f $What, [Environment]::NewLine, $Path) `
            'Re-extract the zip (do not move files out of the Team105-Wizard folder), or ask the packager to rebuild the bundle. This launcher will not download or rebuild on your machine.'
    }
}

# --- Ports (same dual-stack probe pattern as scripts/run-local.ps1) ---------
function Test-PortListening([int]$Port) {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }
    return $false
}

function Test-PortFree([int]$Port) {
    if (Test-PortListening $Port) { return $false }
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::IPv6Any, $Port)
        $listener.Server.DualMode = $true
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { try { $listener.Stop() } catch {} }
    }
}

function Get-FreePort([int]$Preferred) {
    if (Test-PortFree $Preferred) { return $Preferred }
    for ($candidate = $Preferred + 1; $candidate -lt $Preferred + 50; $candidate++) {
        if (Test-PortFree $candidate) { return $candidate }
    }
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::IPv6Any, 0)
    $listener.Server.DualMode = $true
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()
    return $port
}

# --- Process management -----------------------------------------------------
function Start-Tracked {
    param(
        [Parameter(Mandatory)][string]$File,
        [Parameter(Mandatory)][string[]]$ArgList,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [string]$StdOut,
        [string]$StdErr
    )
    $params = @{
        FilePath         = $File
        ArgumentList     = $ArgList
        WorkingDirectory = $WorkingDirectory
        PassThru         = $true
        NoNewWindow      = $true
    }
    if ($StdOut) { $params['RedirectStandardOutput'] = $StdOut }
    if ($StdErr) { $params['RedirectStandardError'] = $StdErr }
    $proc = Start-Process @params
    [void]$script:Children.Add($proc)
    return $proc
}

function Test-ChildExited($proc) {
    if ($null -eq $proc) { return $false }
    try { return $proc.HasExited } catch { return $false }
}

function Stop-AllChildren {
    foreach ($proc in $script:Children) {
        if ($null -ne $proc -and -not (Test-ChildExited $proc)) {
            & taskkill /PID $proc.Id /T /F 2>$null | Out-Null
        }
    }
    foreach ($f in $script:TempFiles) { Remove-Item $f -ErrorAction SilentlyContinue }
}

function Wait-HttpReady([string]$Url, [int]$TimeoutSec, [string]$What) {
    Write-Step "Waiting for $What ($Url)"
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        foreach ($proc in $script:Children) {
            if (Test-ChildExited $proc) {
                Write-Warn2 "A service exited before $What became ready."
                return $false
            }
        }
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                Write-Ok "$What is ready"
                return $true
            }
        } catch {
            # not up yet
        }
        Start-Sleep -Milliseconds 750
    }
    Write-Warn2 "$What did not become ready within $TimeoutSec s."
    return $false
}

function Test-BackendImport {
    Push-Location $AppDir
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $PythonExe -c "import backend.main" 2>$null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $eap
        Pop-Location
    }
}

# ============================================================================
# Main
# ============================================================================
Write-Host ""
Write-Host "Team105 dataset wizard - portable launcher" -ForegroundColor White
Write-Info "Bundle: $BundleRoot"

Assert-RequiredPath $NodeExe 'embedded Node runtime (node.exe)'
Assert-RequiredPath $PythonExe 'embedded Python runtime (python.exe)'
Assert-RequiredPath $ServerJs 'prebuilt Next UI (server.js)'
Assert-RequiredPath $BackendMain 'FastAPI backend (backend\main.py)'
Assert-RequiredPath $LocationDb 'location database (backend\data\location_db.xlsx)'
Assert-RequiredPath $DrConfig 'DRProject template (backend\data\DRProject.config)'

if (-not (Test-BackendImport)) {
    Stop-WithError 'Embedded Python cannot import backend.main (runtime or site-packages may be corrupt).' `
        'Re-extract a fresh zip from the packager. This launcher will not repair or download packages.'
}
Write-Ok 'Embedded runtimes and prebuilt UI present'

if (-not (Test-PortFree $RequiredApiPort)) {
    Stop-WithError ("API port {0} is unavailable (already in use or not bindable)." -f $RequiredApiPort) `
        ("Stop whatever is using port {0} and re-run. The portable UI is built to proxy to http://127.0.0.1:{0} only - this launcher will not move the API to another port." -f $RequiredApiPort)
}
Write-Ok ("API port {0} is free" -f $RequiredApiPort)

$uiPort = Get-FreePort $PreferredUiPort
if ($uiPort -eq $RequiredApiPort) { $uiPort = Get-FreePort ($PreferredUiPort + 1) }
Write-Ok ("UI port {0}" -f $uiPort)

$uiUrl     = "http://127.0.0.1:$uiPort"
$wizardUrl = "$uiUrl/datasets/new"

# Prepend embedded Node for any child that expects it on PATH.
$env:Path = "$(Split-Path -Parent $NodeExe);$env:Path"
$env:NODE_ENV = 'production'
$env:PORT = "$uiPort"
$env:HOSTNAME = '127.0.0.1'
# Avoid picking up a developer's user-site packages on the end-user machine.
$env:PYTHONNOUSERSITE = '1'

try {
    Write-Step ("Starting API (uvicorn) on 127.0.0.1:{0}" -f $RequiredApiPort)
    $api = Start-Tracked -File $PythonExe -ArgList @(
        '-m', 'uvicorn', 'backend.main:app',
        '--host', '127.0.0.1',
        '--port', "$RequiredApiPort"
    ) -WorkingDirectory $AppDir

    Write-Step ("Starting UI (node server.js) on port {0}" -f $uiPort)
    $ui = Start-Tracked -File $NodeExe -ArgList @('server.js') -WorkingDirectory $AppDir

    $apiReady = Wait-HttpReady "http://127.0.0.1:$RequiredApiPort/openapi.json" $ApiReadyTimeout 'API'
    if (-not $apiReady) {
        Stop-WithError ("The API did not respond on port {0}." -f $RequiredApiPort) `
            'Check that the extract folder is writable and that antivirus did not quarantine runtime\python.'
    }

    $uiReady = Wait-HttpReady $uiUrl $UiReadyTimeout 'UI'
    if (-not $uiReady) {
        Stop-WithError ("The UI did not respond on port {0}." -f $uiPort) `
            'Check that antivirus did not quarantine runtime\node or app\server.js.'
    }

    Write-Step 'Opening the wizard'
    Write-Ok $wizardUrl
    Start-Process $wizardUrl | Out-Null

    Write-Host ""
    Write-Host 'Stack is up. Press Ctrl+C to stop everything.' -ForegroundColor White
    Write-Info 'Optional geocoding needs TRIMBLE_MAPS_API_KEY in your environment (not shipped in this zip).'
    while ($true) {
        Start-Sleep -Seconds 1
        if (Test-ChildExited $api) { Write-Warn2 'API process exited - shutting down.'; break }
        if (Test-ChildExited $ui)  { Write-Warn2 'UI process exited - shutting down.';  break }
    }
} finally {
    Write-Host ""
    Write-Step 'Stopping all services'
    Stop-AllChildren
    Write-Ok 'Done.'
}
