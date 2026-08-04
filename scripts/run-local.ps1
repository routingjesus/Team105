#Requires -Version 5.1
<#
.SYNOPSIS
    One-command local runner for the Team105 dataset-creation wizard (SPEC-004).

.DESCRIPTION
    Bootstraps missing prerequisites without admin (Node, uv, the Python venv +
    backend requirements, and npm install), starts the FastAPI backend and the
    Next.js UI wired together through a same-origin proxy, waits until the API
    responds, then opens the wizard in a browser. Optionally exposes a public
    Cloudflare quick tunnel with -Share. Kills the whole child process tree on
    Ctrl+C or when any service dies.

.PARAMETER Share
    Start a Cloudflare quick tunnel to the UI and print a public
    https://<random>.trycloudflare.com URL. Opt-in; off by default.

.PARAMETER Dev
    Run the UI with `next dev` (hot reload) instead of a production build.

.PARAMETER CheckOnly
    Report readiness (tools, ports, execution policy) and exit without
    installing anything or starting any servers.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1 -Share
#>
[CmdletBinding()]
param(
    [switch]$Share,
    [switch]$Dev,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'

# --- Constants --------------------------------------------------------------
# Pinned to a build known-good on the team's bootcamp image. Bump when needed;
# any already-installed Node is detected and reused regardless of this value.
$NodeVersion      = 'v24.19.0'
$PreferredApiPort = 8080
$PreferredUiPort  = 3000
$ApiReadyTimeout  = 90
$UiReadyTimeout   = 120
$ToolsDir         = Join-Path $env:USERPROFILE 'tools'
$RepoRoot         = Split-Path -Parent $PSScriptRoot
$VenvPython       = Join-Path $RepoRoot '.venv\Scripts\python.exe'

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
    if ($fallback) { Write-Host "Manual fallback: $fallback" -ForegroundColor Yellow }
    exit 1
}

# --- Tool discovery ---------------------------------------------------------
function Find-NodeDir {
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) { return (Split-Path -Parent $cmd.Source) }
    $pinned = Join-Path $ToolsDir "node-$NodeVersion-win-x64"
    if (Test-Path (Join-Path $pinned 'node.exe')) { return $pinned }
    if (Test-Path $ToolsDir) {
        $found = Get-ChildItem $ToolsDir -Directory -Filter 'node-*-win-x64' -ErrorAction SilentlyContinue |
            Where-Object { Test-Path (Join-Path $_.FullName 'node.exe') } |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (Test-Path $candidate) { return $candidate }
    return $null
}

function Find-Cloudflared {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Join-Path $ToolsDir 'cloudflared.exe'
    if (Test-Path $candidate) { return $candidate }
    return $null
}

# --- Installers (all user-local, no admin) ----------------------------------
function Install-NodeDir {
    Write-Step "Node not found - installing $NodeVersion (user-local, no admin)"
    [void](New-Item -ItemType Directory -Force -Path $ToolsDir)
    $zip = Join-Path $env:TEMP "node-$NodeVersion-win-x64.zip"
    $url = "https://nodejs.org/dist/$NodeVersion/node-$NodeVersion-win-x64.zip"
    try {
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    } catch {
        Stop-WithError "Could not download Node from $url ($($_.Exception.Message))." `
            "Download node-$NodeVersion-win-x64.zip, extract it under '$ToolsDir', then re-run."
    }
    try {
        Expand-Archive -Path $zip -DestinationPath $ToolsDir -Force
    } finally {
        Remove-Item $zip -ErrorAction SilentlyContinue
    }
    $dir = Join-Path $ToolsDir "node-$NodeVersion-win-x64"
    if (-not (Test-Path (Join-Path $dir 'node.exe'))) {
        Stop-WithError "Node was downloaded but node.exe is not in '$dir'." `
            "Extract the zip so that node.exe lands directly inside '$dir'."
    }
    Write-Ok "Node installed at $dir"
    return $dir
}

function Install-Uv {
    Write-Step "uv not found - installing (user-local, no admin)"
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    } catch {
        Stop-WithError "The uv installer failed ($($_.Exception.Message))." `
            "Install uv per https://docs.astral.sh/uv/getting-started/installation/ so uv.exe is on PATH or in '%USERPROFILE%\.local\bin', then re-run."
    }
    $uv = Find-Uv
    if (-not $uv) {
        Stop-WithError "The uv installer ran but uv.exe was not found." `
            "Ensure uv.exe is in '%USERPROFILE%\.local\bin' or on PATH, then re-run."
    }
    Write-Ok "uv installed at $uv"
    return $uv
}

function Install-Cloudflared {
    Write-Step "cloudflared not found - downloading (user-local, no admin)"
    [void](New-Item -ItemType Directory -Force -Path $ToolsDir)
    $dest = Join-Path $ToolsDir 'cloudflared.exe'
    $url = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
    try {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
    } catch {
        Stop-WithError "Could not download cloudflared from $url ($($_.Exception.Message))." `
            "Download cloudflared-windows-amd64.exe from Cloudflare's GitHub releases, save it as '$dest', then re-run with -Share."
    }
    Write-Ok "cloudflared downloaded to $dest"
    return $dest
}

# True when .venv exists and can already import the backend's runtime deps, so
# no uv install/venv creation is needed (the API runs via .venv's python).
function Test-BackendReady {
    if (-not (Test-Path $VenvPython)) { return $false }
    & $VenvPython -c "import uvicorn, fastapi" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-Backend {
    Push-Location $RepoRoot
    try {
        if (Test-BackendReady) {
            Write-Ok "Backend venv + dependencies present"
            return
        }
        # uv is only needed to build the venv / install deps; the API itself
        # runs via .venv\Scripts\python.exe and never needs uv on PATH.
        $env:UV_SYSTEM_CERTS = 'true'   # required behind corporate TLS interception (UV_NATIVE_TLS is deprecated)
        $uv = Find-Uv
        if (-not $uv) {
            $uv = Install-Uv
            $env:Path = "$(Split-Path -Parent $uv);$env:Path"
        }
        if (-not (Test-Path $VenvPython)) {
            Write-Step "Creating Python venv (.venv)"
            & $uv venv --python 3.12 .venv
            if ($LASTEXITCODE -ne 0) {
                Stop-WithError "uv could not create the .venv (exit $LASTEXITCODE)." `
                    "Run: `$env:UV_SYSTEM_CERTS='true'; uv venv --python 3.12 .venv"
            }
        }
        Write-Step "Installing backend requirements into .venv"
        & $uv pip install --python $VenvPython -r backend/requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "uv pip install failed (exit $LASTEXITCODE)." `
                "Run: `$env:UV_SYSTEM_CERTS='true'; uv pip install --python .venv\Scripts\python.exe -r backend/requirements.txt"
        }
        Write-Ok "Backend dependencies ready"
    } finally {
        Pop-Location
    }
}

function Ensure-FrontendDeps($npmCmd) {
    if (Test-Path (Join-Path $RepoRoot 'node_modules')) {
        Write-Ok "node_modules present"
        return
    }
    Write-Step "Installing frontend dependencies (npm install)"
    Push-Location $RepoRoot
    try {
        # npm.cmd, not npm.ps1: PowerShell execution policy blocks the .ps1 shim.
        & $npmCmd install
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "npm install failed (exit $LASTEXITCODE)." `
                "Run 'npm.cmd install' from the repo root; if a Group-Policy execution policy blocks npm, ask IT or use npm.cmd explicitly."
        }
        Write-Ok "Frontend dependencies ready"
    } finally {
        Pop-Location
    }
}

# --- Ports ------------------------------------------------------------------
function Test-PortListening([int]$Port) {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }
    return $false
}

# A port is "free" only if nothing is listening on ANY interface/family and we
# can actually bind it dual-stack. Node binds :: (IPv6 + IPv4 via v4-mapped),
# so an IPv4-only probe would miss an existing IPv6 listener; the dual-stack
# bind mirrors Node and also catches reserved-but-not-listening ports.
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
    # Last resort: let the OS assign an ephemeral port.
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::IPv6Any, 0)
    $listener.Server.DualMode = $true
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()
    return $port
}

# --- Execution policy -------------------------------------------------------
function Get-RestrictivePolicyScopes {
    $blocked = @()
    foreach ($scope in @('MachinePolicy', 'UserPolicy')) {
        $value = Get-ExecutionPolicy -Scope $scope
        if ($value -in @('Restricted', 'AllSigned')) { $blocked += "$scope=$value" }
    }
    return $blocked
}

# --- Proxy mode -------------------------------------------------------------
# Force the client into same-origin proxy mode by ensuring .env.local sets an
# empty NEXT_PUBLIC_API_BASE_URL. .env.local (gitignored) outranks any stale
# absolute value in .env, so requests use relative /api/... paths through the
# Next proxy regardless of what a developer left in .env.
function Set-ProxyModeEnvLocal {
    $envLocal = Join-Path $RepoRoot '.env.local'
    $line = 'NEXT_PUBLIC_API_BASE_URL='
    if (Test-Path $envLocal) {
        $content = @(Get-Content $envLocal)
        if ($content -match '^\s*NEXT_PUBLIC_API_BASE_URL=') {
            $content = $content -replace '^\s*NEXT_PUBLIC_API_BASE_URL=.*$', $line
        } else {
            $content += $line
        }
        Set-Content -Path $envLocal -Value $content
    } else {
        Set-Content -Path $envLocal -Value $line
    }
    Write-Ok "Proxy mode set (.env.local -> relative /api calls)"
}

# --- Process management -----------------------------------------------------
function Start-Tracked([string]$File, [string[]]$ArgList, [string]$StdOut, [string]$StdErr) {
    $params = @{
        FilePath         = $File
        ArgumentList     = $ArgList
        WorkingDirectory = $RepoRoot
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
            # taskkill /T tears down the whole tree: Windows has no SIGINT
            # propagation to grandchildren (uvicorn reloader, next workers).
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

# ============================================================================
# Main
# ============================================================================
Write-Host ""
Write-Host "Team105 dataset wizard - local runner" -ForegroundColor White
Write-Info "Repo: $RepoRoot"

# ---- -CheckOnly: report and exit (no install, no servers) ------------------
if ($CheckOnly) {
    Write-Step "Readiness check (no servers started)"

    $nodeDir = Find-NodeDir
    if ($nodeDir) { Write-Ok "Node found: $nodeDir" }
    else { Write-Warn2 "Node NOT found - launcher would install $NodeVersion" }

    if (Test-BackendReady) {
        Write-Ok "Backend venv + dependencies present (uv not needed)"
    } else {
        $uv = Find-Uv
        if ($uv) { Write-Ok "uv found: $uv (will build/refresh .venv)" }
        else { Write-Warn2 "uv NOT found and .venv incomplete - launcher would install uv, then build .venv + backend deps" }
    }

    if (Test-Path (Join-Path $RepoRoot '.venv')) { Write-Ok ".venv present" }
    else { Write-Warn2 ".venv absent - launcher would create it + install backend deps" }

    if (Test-Path (Join-Path $RepoRoot 'node_modules')) { Write-Ok "node_modules present" }
    else { Write-Warn2 "node_modules absent - launcher would run npm install" }

    if (Test-PortFree $PreferredApiPort) { Write-Ok "API port $PreferredApiPort is free" }
    else { Write-Warn2 "API port $PreferredApiPort is busy - launcher would probe a random free port" }

    if (Test-PortFree $PreferredUiPort) { Write-Ok "UI port $PreferredUiPort is free" }
    else { Write-Warn2 "UI port $PreferredUiPort is busy - launcher would probe a random free port" }

    Write-Info "Execution policy (process): $(Get-ExecutionPolicy -Scope Process)"
    $restrictive = Get-RestrictivePolicyScopes
    if ($restrictive.Count -gt 0) {
        Write-Warn2 "Group-Policy execution policy in effect: $($restrictive -join ', '). npm.cmd is used to avoid npm.ps1, but a fully locked policy may still block tooling - contact IT if bootstrap fails."
    } else {
        Write-Ok "No restrictive Group-Policy execution policy detected"
    }

    $cf = Find-Cloudflared
    if ($cf) { Write-Ok "cloudflared found: $cf (for -Share)" }
    else { Write-Info "cloudflared not found - only needed for -Share; launcher would download it then." }

    Write-Host ""
    Write-Ok "Check complete. Re-run without -CheckOnly to start the stack."
    exit 0
}

# ---- Bootstrap -------------------------------------------------------------
$nodeDir = Find-NodeDir
if (-not $nodeDir) { $nodeDir = Install-NodeDir }
# Prepend the tool dir in-session: a running shell does not inherit PATH edits,
# and user-local installs create no global shim without Developer Mode/admin.
$env:Path = "$nodeDir;$env:Path"
$npmCmd = Join-Path $nodeDir 'npm.cmd'
Write-Ok "Node $(& (Join-Path $nodeDir 'node.exe') --version)"

Ensure-Backend
Ensure-FrontendDeps $npmCmd

# ---- Port selection (before build: rewrites bake the target at build time) -
$apiPort = Get-FreePort $PreferredApiPort
$uiPort  = Get-FreePort $PreferredUiPort
if ($uiPort -eq $apiPort) { $uiPort = Get-FreePort ($PreferredUiPort + 1) }
Write-Ok "API port $apiPort / UI port $uiPort"

Set-ProxyModeEnvLocal
$env:API_PROXY_TARGET = "http://127.0.0.1:$apiPort"

$uiUrl     = "http://localhost:$uiPort"
$wizardUrl = "$uiUrl/datasets/new"

# ---- Start services + wait + open (teardown guaranteed in finally) ---------
try {
    Write-Step "Starting API (uvicorn) on 127.0.0.1:$apiPort"
    $api = Start-Tracked $VenvPython @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', "$apiPort")

    if ($Dev) {
        Write-Step "Starting UI (next dev) on port $uiPort"
        $ui = Start-Tracked $npmCmd @('run', 'dev', '--', '-p', "$uiPort")
    } else {
        Write-Step "Building UI (next build) - API_PROXY_TARGET=$env:API_PROXY_TARGET"
        Push-Location $RepoRoot
        try {
            & $npmCmd run build
            $buildExit = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($buildExit -ne 0) {
            Stop-WithError "next build failed (exit $buildExit)." `
                "Run 'npm.cmd run build' from the repo root and fix the reported error, then re-run. Use -Dev to skip the production build."
        }
        Write-Step "Starting UI (next start) on port $uiPort"
        $ui = Start-Tracked $npmCmd @('run', 'start', '--', '-p', "$uiPort")
    }

    $apiReady = Wait-HttpReady "http://127.0.0.1:$apiPort/openapi.json" $ApiReadyTimeout "API"
    if (-not $apiReady) {
        Stop-WithError "The API did not respond on port $apiPort." `
            "Check the uvicorn output above; run '.venv\Scripts\python.exe -m uvicorn backend.main:app --port $apiPort' manually to see the error."
    }

    $uiReady = Wait-HttpReady $uiUrl $UiReadyTimeout "UI"
    if (-not $uiReady) {
        Stop-WithError "The UI did not respond on port $uiPort." `
            "Check the Next.js output above; try -Dev for a faster-starting dev server."
    }

    Write-Step "Opening the wizard"
    Write-Ok $wizardUrl
    Start-Process $wizardUrl | Out-Null

    if ($Share) {
        $cf = Find-Cloudflared
        if (-not $cf) { $cf = Install-Cloudflared }
        Write-Step "Starting Cloudflare quick tunnel to $uiUrl"
        $cfOut = Join-Path $env:TEMP "team105-cf-out-$PID.log"
        $cfErr = Join-Path $env:TEMP "team105-cf-err-$PID.log"
        [void]$script:TempFiles.Add($cfOut)
        [void]$script:TempFiles.Add($cfErr)
        $tunnel = Start-Tracked $cf @('tunnel', '--url', $uiUrl) $cfOut $cfErr

        $publicUrl = $null
        $tunnelDeadline = (Get-Date).AddSeconds(30)
        while ((Get-Date) -lt $tunnelDeadline -and -not $publicUrl) {
            if (Test-ChildExited $tunnel) { break }
            foreach ($logFile in @($cfErr, $cfOut)) {
                if (Test-Path $logFile) {
                    $m = Select-String -Path $logFile -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue |
                        Select-Object -First 1
                    if ($m) { $publicUrl = $m.Matches[0].Value; break }
                }
            }
            Start-Sleep -Milliseconds 500
        }

        Write-Host ""
        if ($publicUrl) {
            Write-Host "  Public URL: $publicUrl/datasets/new" -ForegroundColor Green
            Write-Warn2 "Security: this ephemeral URL is world-reachable and bypasses your firewall. Treat it as a secret, only the proxied frontend is exposed, and never demo with real PII or production credentials."
        } else {
            Write-Warn2 "Tunnel started but no trycloudflare.com URL was captured yet. Check the cloudflared output; the URL usually appears within a few seconds."
        }
    }

    Write-Host ""
    Write-Host "Stack is up. Press Ctrl+C to stop everything." -ForegroundColor White
    while ($true) {
        Start-Sleep -Seconds 1
        if (Test-ChildExited $api) { Write-Warn2 "API process exited - shutting down."; break }
        if (Test-ChildExited $ui)  { Write-Warn2 "UI process exited - shutting down.";  break }
        if ($Share -and (Test-ChildExited $tunnel)) { Write-Warn2 "Tunnel exited - shutting down."; break }
    }
} finally {
    Write-Host ""
    Write-Step "Stopping all services"
    Stop-AllChildren
    Write-Ok "Done."
}
