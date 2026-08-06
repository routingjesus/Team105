#Requires -Version 5.1
<#
.SYNOPSIS
    Build a portable Windows zip of the Team105 dataset wizard (SPEC-018).

.DESCRIPTION
    Downloads pinned Node + embeddable CPython, vendors backend requirements,
    builds the Next UI with API_PROXY_TARGET fixed to http://127.0.0.1:8080
    (standalone output), and assembles Team105-Wizard-win-x64.zip. Run on a
    developer/CI machine that can reach the network; the resulting zip needs
    no Node/Python/Git on the end-user PC.

.PARAMETER OutDir
    Staging + zip output directory (default: <repo>\build\portable).

.PARAMETER SkipRuntimeDownload
    Reuse existing runtime\node and runtime\python under OutDir\Team105-Wizard
    if present (still reinstalls Python site-packages and rebuilds the UI).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\package-portable.ps1
#>
[CmdletBinding()]
param(
    [string]$OutDir = '',
    [switch]$SkipRuntimeDownload
)

$ErrorActionPreference = 'Stop'

# --- Constants --------------------------------------------------------------
# Keep Node pin aligned with scripts/run-local.ps1.
$NodeVersion   = 'v24.19.0'
$PythonVersion = '3.12.8'
$ApiProxyTarget = 'http://127.0.0.1:8080'

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) {
    $OutDir = Join-Path $RepoRoot 'build\portable'
}
$StageRoot   = Join-Path $OutDir 'Team105-Wizard'
$ZipPath     = Join-Path $OutDir 'Team105-Wizard-win-x64.zip'
$CacheDir    = Join-Path $OutDir 'cache'
$NodeZipName = "node-$NodeVersion-win-x64.zip"
$PyZipName   = "python-$PythonVersion-embed-amd64.zip"

# --- Output helpers ---------------------------------------------------------
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [ok]   $msg" -ForegroundColor Green }
function Write-Info($msg)  { Write-Host "    $msg" }

function Stop-WithError($step, $fallback) {
    Write-Host ""
    Write-Host "ERROR: $step" -ForegroundColor Red
    if ($fallback) { Write-Host "Manual fallback: $fallback" -ForegroundColor Yellow }
    exit 1
}

function Get-DownloaderUrl([string]$Url, [string]$OutFile) {
    Write-Info "Downloading $Url"
    try {
        # BitsTransfer / WebClient release the file handle more reliably than
        # Invoke-WebRequest before Expand-Archive on some Windows hosts (AV lock).
        $wc = New-Object System.Net.WebClient
        try {
            $wc.DownloadFile($Url, $OutFile)
        } finally {
            $wc.Dispose()
        }
    } catch {
        Stop-WithError "Download failed: $Url ($($_.Exception.Message))" `
            "Download the file manually to '$OutFile' and re-run with -SkipRuntimeDownload after placing extracted runtimes, or fix network/TLS."
    }
}

function Expand-ZipReliable([string]$ZipPath, [string]$DestDir) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path $DestDir) {
        # ExtractToDirectory (Framework) refuses non-empty destinations.
        Remove-Item -LiteralPath $DestDir -Recurse -Force
    }
    [void](New-Item -ItemType Directory -Force -Path $DestDir)
    # Copy first: AV / Explorer often keeps a share lock on the download path.
    $zipCopy = Join-Path ([System.IO.Path]::GetTempPath()) ("team105-zip-{0}-{1}.zip" -f $PID, [Guid]::NewGuid().ToString('N'))
    $attempts = 0
    while ($true) {
        try {
            Copy-Item -LiteralPath $ZipPath -Destination $zipCopy -Force
            [System.IO.Compression.ZipFile]::ExtractToDirectory($zipCopy, $DestDir)
            return
        } catch {
            $attempts++
            if ($attempts -ge 8) {
                Stop-WithError "Could not extract '$ZipPath' ($($_.Exception.Message))" `
                    "Close anything locking the zip (Explorer preview, antivirus), then re-run."
            }
            Start-Sleep -Seconds 2
        } finally {
            Remove-Item -LiteralPath $zipCopy -Force -ErrorAction SilentlyContinue
        }
    }
}

function Find-NpmCmd {
    $cmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd = Get-Command npm -ErrorAction SilentlyContinue
    if ($cmd) {
        $dir = Split-Path -Parent $cmd.Source
        $npmCmd = Join-Path $dir 'npm.cmd'
        if (Test-Path $npmCmd) { return $npmCmd }
    }
    $tools = Join-Path $env:USERPROFILE 'tools'
    $pinned = Join-Path $tools "node-$NodeVersion-win-x64\npm.cmd"
    if (Test-Path $pinned) { return $pinned }
    if (Test-Path $tools) {
        $found = Get-ChildItem $tools -Directory -Filter 'node-*-win-x64' -ErrorAction SilentlyContinue |
            Where-Object { Test-Path (Join-Path $_.FullName 'npm.cmd') } |
            Select-Object -First 1
        if ($found) { return (Join-Path $found.FullName 'npm.cmd') }
    }
    return $null
}

function Enable-EmbeddedSitePackages([string]$PythonDir) {
    $pth = Get-ChildItem -LiteralPath $PythonDir -Filter 'python*._pth' -File |
        Select-Object -First 1
    if (-not $pth) {
        Stop-WithError "No python*._pth in embedded Python at '$PythonDir'." `
            "Re-download the official Windows embeddable package."
    }
    $lines = @(Get-Content -LiteralPath $pth.FullName)
    $out = New-Object System.Collections.Generic.List[string]
    $sawSitePackages = $false
    $sawImportSite = $false
    foreach ($line in $lines) {
        if ($line -match '^\s*#\s*import\s+site\s*$') {
            $out.Add('import site')
            $sawImportSite = $true
            continue
        }
        if ($line -match '^\s*import\s+site\s*$') {
            $out.Add('import site')
            $sawImportSite = $true
            continue
        }
        if ($line -match '(?i)Lib\\site-packages') {
            $sawSitePackages = $true
        }
        $out.Add($line)
    }
    if (-not $sawSitePackages) {
        # Insert after the first path entry (usually pythonXXX.zip or '.')
        if ($out.Count -gt 0) {
            $out.Insert(1, 'Lib\site-packages')
        } else {
            $out.Add('Lib\site-packages')
        }
    }
    if (-not $sawImportSite) {
        $out.Add('import site')
    }
    Set-Content -LiteralPath $pth.FullName -Value $out.ToArray() -Encoding ASCII
    Write-Ok "Enabled site-packages in $($pth.Name)"
}

function Add-BundleAppPathToPth([string]$PythonDir) {
    # Embeddable ._pth replaces normal sys.path init: CWD is NOT on sys.path,
    # and PYTHONPATH is ignored. Point at the bundle app/ root (uvicorn's CWD)
    # via a path relative to runtime/python/.
    $pth = Get-ChildItem -LiteralPath $PythonDir -Filter 'python*._pth' -File |
        Select-Object -First 1
    if (-not $pth) {
        Stop-WithError "No python*._pth in '$PythonDir' when adding app path." $null
    }
    $lines = @(Get-Content -LiteralPath $pth.FullName)
    $rel = '..\..\app'
    if ($lines -notcontains $rel) {
        # Keep import site last.
        $out = New-Object System.Collections.Generic.List[string]
        foreach ($line in $lines) {
            if ($line -match '^\s*import\s+site\s*$') {
                $out.Add($rel)
            }
            $out.Add($line)
        }
        if ($out -notcontains $rel) { $out.Add($rel) }
        Set-Content -LiteralPath $pth.FullName -Value $out.ToArray() -Encoding ASCII
    }
    Write-Ok "._pth includes $rel (bundle app root for backend imports)"
}

function Install-EmbeddedPythonDeps([string]$PythonDir, [string]$Requirements) {
    $python = Join-Path $PythonDir 'python.exe'
    $getPip = Join-Path $CacheDir 'get-pip.py'
    if (-not (Test-Path $getPip)) {
        Get-DownloaderUrl 'https://bootstrap.pypa.io/get-pip.py' $getPip
    }
    Write-Step "Bootstrapping pip into embedded Python"
    & $python $getPip --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "get-pip.py failed (exit $LASTEXITCODE)." `
            "Check TLS/network; corporate proxies may need UV_SYSTEM_CERTS-style trust configured for Python."
    }
    Write-Step "Installing backend requirements into embedded Python"
    & $python -m pip install --no-warn-script-location -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "pip install -r backend/requirements.txt failed (exit $LASTEXITCODE)." `
            "Retry on a network that can reach PyPI, or pre-vendor wheels."
    }
    # Smoke import of the heavy stack the API needs.
    & $python -c "import fastapi, uvicorn, pandas, openpyxl, filelock"
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Embedded Python imports failed after pip install." `
            "Inspect site-packages under '$PythonDir\Lib\site-packages'."
    }
    Write-Ok "Python dependencies vendored"
}

function Copy-Tree([string]$Source, [string]$Dest, [string[]]$ExcludeDirNames = @()) {
    if (-not (Test-Path -LiteralPath $Source)) {
        Stop-WithError "Copy source missing: $Source" $null
    }
    if (-not (Test-Path -LiteralPath $Dest)) {
        [void](New-Item -ItemType Directory -Force -Path $Dest)
    }
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        if ($_.PSIsContainer -and ($ExcludeDirNames -contains $_.Name)) { return }
        $target = Join-Path $Dest $_.Name
        if ($_.PSIsContainer) {
            Copy-Tree -Source $_.FullName -Dest $target -ExcludeDirNames $ExcludeDirNames
        } else {
            if ($_.Extension -eq '.pyc') { return }
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

function Copy-BackendTree([string]$DestBackend) {
    $src = Join-Path $RepoRoot 'backend'
    if (Test-Path $DestBackend) { Remove-Item $DestBackend -Recurse -Force }
    [void](New-Item -ItemType Directory -Force -Path $DestBackend)
    Write-Step "Copying backend/ into bundle"
    Copy-Tree -Source $src -Dest $DestBackend -ExcludeDirNames @('__pycache__', '.pytest_cache')
    $needed = @(
        (Join-Path $DestBackend 'main.py'),
        (Join-Path $DestBackend 'data\location_db.xlsx'),
        (Join-Path $DestBackend 'data\DRProject.config')
    )
    foreach ($p in $needed) {
        if (-not (Test-Path $p)) {
            Stop-WithError "Backend copy missing '$p'." "Ensure the repo has backend/data/location_db.xlsx and DRProject.config."
        }
    }
    Write-Ok "backend/ copied (with location_db.xlsx + DRProject.config)"
}

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
    Write-Ok "Proxy mode set for package build (.env.local empty NEXT_PUBLIC_API_BASE_URL)"
}

function Build-NextStandalone([string]$NpmCmd) {
    Write-Step "Building Next standalone (API_PROXY_TARGET=$ApiProxyTarget)"
    Set-ProxyModeEnvLocal
    $env:API_PROXY_TARGET = $ApiProxyTarget
    Push-Location $RepoRoot
    try {
        if (-not (Test-Path (Join-Path $RepoRoot 'node_modules\.bin\next.cmd'))) {
            Write-Step "npm install (next shim missing)"
            # Pipe to Out-Host so stdout is not captured as this function's return value.
            & $NpmCmd install 2>&1 | Out-Host
            if ($LASTEXITCODE -ne 0) {
                Stop-WithError "npm install failed (exit $LASTEXITCODE)." "Fix frontend deps, then re-run."
            }
        }
        & $NpmCmd run build 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "next build failed (exit $LASTEXITCODE)." "Fix build errors, then re-run."
        }
    } finally {
        Pop-Location
    }
    $standalone = Join-Path $RepoRoot '.next\standalone'
    if (-not (Test-Path (Join-Path $standalone 'server.js'))) {
        Stop-WithError "Standalone build missing server.js under .next\standalone." `
            "Confirm next.config.ts has output: 'standalone' and re-run the build."
    }
    Write-Ok "Next standalone build ready"
    # Comma forces a single-element array so callers get one path string.
    return ,$standalone
}

function Publish-Standalone([string]$StandaloneSrc, [string]$AppDest) {
    if (Test-Path $AppDest) { Remove-Item $AppDest -Recurse -Force }
    [void](New-Item -ItemType Directory -Force -Path $AppDest)
    Write-Step "Copying standalone UI into bundle app\"
    Copy-Tree -Source $StandaloneSrc -Dest $AppDest -ExcludeDirNames @('__pycache__')

    $staticSrc = Join-Path $RepoRoot '.next\static'
    $staticDest = Join-Path $AppDest '.next\static'
    if (Test-Path $staticSrc) {
        [void](New-Item -ItemType Directory -Force -Path $staticDest)
        Copy-Tree -Source $staticSrc -Dest $staticDest
        Write-Ok "Copied .next/static into standalone tree"
    } else {
        Stop-WithError "Missing .next\static after build." "Re-run next build."
    }

    $publicSrc = Join-Path $RepoRoot 'public'
    if (Test-Path $publicSrc) {
        $publicDest = Join-Path $AppDest 'public'
        [void](New-Item -ItemType Directory -Force -Path $publicDest)
        Copy-Tree -Source $publicSrc -Dest $publicDest
        Write-Ok "Copied public/ into standalone tree"
    } else {
        Write-Info "No public/ folder in repo - skipping (optional for this app)"
    }
}

function Write-BundleReadme([string]$Dest) {
    # ASCII-only: smart dashes/arrows corrupt @" "@ here-strings under some encodings.
    $lines = @(
        'Team105 Dataset Creation Wizard - portable Windows bundle',
        '=========================================================',
        '',
        'What this is',
        '------------',
        'A self-contained copy of the wizard. You do not need Git, Node, Python, or',
        'a developer toolkit. Extract and double-click to run.',
        '',
        'How to launch',
        '-------------',
        '1. Extract Team105-Wizard-win-x64.zip to a writable folder such as Desktop',
        '   or Documents (not Program Files - the location database must be writable).',
        '2. If Windows SmartScreen blocks the files:',
        '   - Right-click the zip (before extract) > Properties > Unblock > OK, or',
        '   - After extract, in PowerShell:  Unblock-File -Path .\Team105-Wizard\* -Recurse',
        '   - If a blue SmartScreen dialog appears: More info > Run anyway',
        '3. Double-click Team105-Wizard.cmd',
        '',
        'Ports',
        '-----',
        '- The API always uses port 8080. If something else is using 8080, the launcher',
        '  exits with an error - it will not silently pick another API port.',
        '- The UI prefers port 3000 and will use the next free port if needed.',
        '- Then open (or wait for the browser) http://127.0.0.1:<ui-port>/datasets/new',
        '',
        'Optional geocoding',
        '------------------',
        'Core truck/stop generation works offline from the bundled location database.',
        'Manual geocoding (if you use it) needs TRIMBLE_MAPS_API_KEY set in your',
        'Windows environment before launching. No API key is shipped in this zip.',
        '',
        'Stop',
        '----',
        'Close the console window or press Ctrl+C to stop both servers.'
    )
    Set-Content -LiteralPath $Dest -Value $lines -Encoding UTF8
}

function Write-BundleCmd([string]$Dest) {
    $cmd = @(
        '@echo off',
        'REM Portable Team105 wizard launcher (SPEC-018). Process-scoped Bypass only.',
        'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch-portable.ps1" %*'
    )
    Set-Content -LiteralPath $Dest -Value $cmd -Encoding ASCII
}

# ============================================================================
# Main
# ============================================================================
Write-Host ""
Write-Host "Team105 dataset wizard - portable packager" -ForegroundColor White
Write-Info "Repo: $RepoRoot"
Write-Info "Out:  $OutDir"

[void](New-Item -ItemType Directory -Force -Path $CacheDir)
[void](New-Item -ItemType Directory -Force -Path $StageRoot)

$runtimeNode = Join-Path $StageRoot 'runtime\node'
$runtimePy   = Join-Path $StageRoot 'runtime\python'
$appDir      = Join-Path $StageRoot 'app'
$scriptsDir  = Join-Path $StageRoot 'scripts'

# ---- Node runtime ----------------------------------------------------------
$nodeExe = Join-Path $runtimeNode 'node.exe'
if ($SkipRuntimeDownload -and (Test-Path $nodeExe)) {
    Write-Ok "Reusing embedded Node at $runtimeNode"
} else {
    Write-Step "Fetching Node $NodeVersion win-x64"
    $nodeZip = Join-Path $CacheDir $NodeZipName
    if (-not (Test-Path $nodeZip)) {
        Get-DownloaderUrl "https://nodejs.org/dist/$NodeVersion/$NodeZipName" $nodeZip
    }
    $nodeTmp = Join-Path $CacheDir "extract-node-$PID"
    Expand-ZipReliable $nodeZip $nodeTmp
    $nodeInner = Get-ChildItem -LiteralPath $nodeTmp -Directory | Select-Object -First 1
    if (-not $nodeInner -or -not (Test-Path (Join-Path $nodeInner.FullName 'node.exe'))) {
        Stop-WithError "Node zip did not contain a folder with node.exe." $null
    }
    if (Test-Path $runtimeNode) { Remove-Item $runtimeNode -Recurse -Force }
    [void](New-Item -ItemType Directory -Force -Path (Split-Path $runtimeNode))
    Move-Item -LiteralPath $nodeInner.FullName -Destination $runtimeNode
    Remove-Item -LiteralPath $nodeTmp -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path $nodeExe)) {
        Stop-WithError "node.exe missing after extract at '$runtimeNode'." $null
    }
    Write-Ok "Node embedded at $runtimeNode"
}

# ---- Python runtime --------------------------------------------------------
$pythonExe = Join-Path $runtimePy 'python.exe'
$needPyFresh = -not ($SkipRuntimeDownload -and (Test-Path $pythonExe))
if ($needPyFresh) {
    Write-Step "Fetching embeddable CPython $PythonVersion"
    $pyZip = Join-Path $CacheDir $PyZipName
    # If a prior download left an AV lock on the cached zip, fetch under a fresh name.
    if ((Test-Path $pyZip)) {
        try {
            $fs = [System.IO.File]::Open($pyZip, 'Open', 'Read', 'ReadWrite')
            $fs.Close()
        } catch {
            Write-Info "Cached Python zip is locked; downloading a fresh copy"
            $pyZip = Join-Path $CacheDir ("python-{0}-embed-amd64-{1}.zip" -f $PythonVersion, [Guid]::NewGuid().ToString('N').Substring(0, 8))
        }
    }
    if (-not (Test-Path $pyZip)) {
        Get-DownloaderUrl "https://www.python.org/ftp/python/$PythonVersion/$PyZipName" $pyZip
    }
    if (Test-Path $runtimePy) { Remove-Item $runtimePy -Recurse -Force }
    Expand-ZipReliable $pyZip $runtimePy
    if (-not (Test-Path $pythonExe)) {
        Stop-WithError "python.exe missing after extract at '$runtimePy'." $null
    }
    Enable-EmbeddedSitePackages $runtimePy
    Add-BundleAppPathToPth $runtimePy
    Write-Ok "Python embedded at $runtimePy"
} else {
    Write-Ok "Reusing embedded Python at $runtimePy"
    Enable-EmbeddedSitePackages $runtimePy
    Add-BundleAppPathToPth $runtimePy
}

Install-EmbeddedPythonDeps $runtimePy (Join-Path $RepoRoot 'backend\requirements.txt')

# ---- Next standalone + backend ---------------------------------------------
$npmCmd = Find-NpmCmd
if (-not $npmCmd) {
    Stop-WithError "npm.cmd not found on the packaging machine." `
        "Install Node (or run run-local.cmd once), then re-run package-portable.ps1."
}
$standalone = Build-NextStandalone $npmCmd | Select-Object -Last 1
Publish-Standalone $standalone $appDir
Copy-BackendTree (Join-Path $appDir 'backend')

# ---- Launcher + docs -------------------------------------------------------
[void](New-Item -ItemType Directory -Force -Path $scriptsDir)
Copy-Item -LiteralPath (Join-Path $RepoRoot 'scripts\launch-portable.ps1') `
    -Destination (Join-Path $scriptsDir 'launch-portable.ps1') -Force
Write-BundleCmd (Join-Path $StageRoot 'Team105-Wizard.cmd')
Write-BundleReadme (Join-Path $StageRoot 'README.txt')
Write-Ok "Launcher + README.txt staged"

# ---- Zip -------------------------------------------------------------------
Write-Step "Creating $ZipPath"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
# tar -a produces a zip without the long-path / Compress-Archive pitfalls.
Push-Location $OutDir
try {
    & tar -a -cf (Split-Path -Leaf $ZipPath) 'Team105-Wizard'
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "tar zip failed (exit $LASTEXITCODE)." `
            "Create a zip of the Team105-Wizard folder manually from '$StageRoot'."
    }
} finally {
    Pop-Location
}

# ---- Smoke: required zip members -------------------------------------------
Write-Step "Smoke-checking staged layout (pre-zip contents)"
$required = @(
    'Team105-Wizard.cmd',
    'README.txt',
    'scripts\launch-portable.ps1',
    'runtime\node\node.exe',
    'runtime\python\python.exe',
    'app\server.js',
    'app\backend\main.py',
    'app\backend\data\location_db.xlsx',
    'app\backend\data\DRProject.config'
)
foreach ($rel in $required) {
    $p = Join-Path $StageRoot $rel
    if (-not (Test-Path $p)) {
        Stop-WithError "Staged bundle missing '$rel'." "Packaging incomplete - see earlier steps."
    }
}
Write-Ok "Required paths present"
Write-Host ""
Write-Host "Portable zip ready:" -ForegroundColor Green
Write-Host "  $ZipPath"
Write-Info "Distribute that file. End users extract and run Team105-Wizard.cmd."
