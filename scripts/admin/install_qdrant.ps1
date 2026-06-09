<#
.SYNOPSIS
Install and register Qdrant as a Windows Service for IMDR.

.DESCRIPTION
Idempotent installer. Re-running is safe -- it skips steps that are
already done.

What it does:
  1. Verifies it's running elevated.
  2. Downloads three archives to a temp dir:
       - Qdrant (v1.18.0) from the qdrant GitHub release
       - NSSM (2.24) from nssm.cc (falls back to the CI build URL if the
         primary endpoint 503s)
       - Qdrant web UI (dist-qdrant.zip) from qdrant-web-ui — the
         Windows qdrant binary doesn't bundle the dashboard
  3. Extracts:
       - qdrant.exe -> C:\IMDR_LOCAL\qdrant\
       - nssm.exe   -> C:\IMDR_LOCAL\nssm\
       - web UI     -> C:\IMDR_LOCAL\qdrant\static\
  4. Creates C:\IMDR_LOCAL\qdrant\{storage,snapshots}\
  5. Copies the repo config (config\qdrant\production.yaml) to
     C:\ProgramData\Qdrant\config.yaml -- the service reads from there.
  6. Registers the Qdrant Windows Service via NSSM, pointing at the
     copied config, with AppDirectory set so the dashboard's ./static
     resolves and stdout/stderr rotated at 10 MB.
  7. Starts the service and pings http://127.0.0.1:6333/ to confirm.

Re-run this script after editing config\qdrant\production.yaml to push
the new config to ProgramData and restart the service.

.NOTES
Must be run from an elevated PowerShell. The script verifies this and
exits if not.
#>

[CmdletBinding()]
param(
    [string]$QdrantVersion = "1.18.0",
    [string]$NssmVersion   = "2.24",
    # Binary, web UI, and data all share the same root so the service can
    # find ./static for the dashboard via AppDirectory = $InstallRoot.
    [string]$InstallRoot   = "C:\IMDR_LOCAL\qdrant",
    [string]$NssmRoot      = "C:\IMDR_LOCAL\nssm",
    [string]$DataRoot      = "C:\IMDR_LOCAL\qdrant",
    [string]$ConfigDest    = "C:\ProgramData\Qdrant\config.yaml",
    [string]$ServiceName   = "Qdrant",
    # Optional: override the repo config path (e.g. when running the
    # script from a C:\ copy that isn't inside the IMDR repo).
    [string]$RepoConfig    = ""
)

$ErrorActionPreference = "Stop"

function Test-Admin {
    $identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "ERROR: this installer must run from an elevated PowerShell." -ForegroundColor Red
    Write-Host "       Re-launch PowerShell as Administrator and re-run." -ForegroundColor Red
    exit 1
}

if (-not $RepoConfig) {
    $RepoRoot   = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $RepoConfig = Join-Path $RepoRoot "config\qdrant\production.yaml"
}

if (-not (Test-Path $RepoConfig)) {
    Write-Host "ERROR: repo config not found at $RepoConfig" -ForegroundColor Red
    Write-Host "       Pass -RepoConfig <path> if running outside the repo." -ForegroundColor Red
    exit 1
}

Write-Host "=== IMDR Qdrant installer ==="
Write-Host "  qdrant version : $QdrantVersion"
Write-Host "  nssm   version : $NssmVersion"
Write-Host "  binary install : $InstallRoot"
Write-Host "  data root      : $DataRoot"
Write-Host "  config (live)  : $ConfigDest"
Write-Host "  config (src)   : $RepoConfig"
Write-Host ""

# --- 1. Download archives -------------------------------------------------
$TmpRoot = Join-Path $env:TEMP "imdr-qdrant-install"
New-Item -ItemType Directory -Force -Path $TmpRoot | Out-Null
$QdrantZip   = Join-Path $TmpRoot "qdrant-$QdrantVersion.zip"
$NssmZip     = Join-Path $TmpRoot "nssm-$NssmVersion.zip"
$WebUiZip    = Join-Path $TmpRoot "qdrant-web-ui.zip"
$QdrantUrl   = "https://github.com/qdrant/qdrant/releases/download/v$QdrantVersion/qdrant-x86_64-pc-windows-msvc.zip"
# nssm.cc release endpoint occasionally 503s; CI build is the same binary
# from the same publisher and is more reliable.
$NssmUrlPrim = "https://nssm.cc/release/nssm-$NssmVersion.zip"
$NssmUrlFb   = "https://nssm.cc/ci/nssm-2.24-101-g897c7ad.zip"
$WebUiUrl    = "https://github.com/qdrant/qdrant-web-ui/releases/latest/download/dist-qdrant.zip"

function Download-WithFallback($urls, $out) {
    foreach ($u in $urls) {
        try {
            Invoke-WebRequest -Uri $u -OutFile $out -UseBasicParsing -TimeoutSec 30
            return
        } catch {
            Write-Host "    download failed at $u : $($_.Exception.Message.Split([Environment]::NewLine)[0])" -ForegroundColor Yellow
        }
    }
    throw "could not download from any source: $($urls -join ', ')"
}

if (-not (Test-Path $QdrantZip)) {
    Write-Host "[1/8] downloading qdrant $QdrantVersion..."
    Download-WithFallback @($QdrantUrl) $QdrantZip
} else {
    Write-Host "[1/8] qdrant zip already in temp -- skipping download"
}

if (-not (Test-Path $NssmZip)) {
    Write-Host "[2/8] downloading nssm $NssmVersion..."
    Download-WithFallback @($NssmUrlPrim, $NssmUrlFb) $NssmZip
} else {
    Write-Host "[2/8] nssm zip already in temp -- skipping download"
}

if (-not (Test-Path $WebUiZip)) {
    Write-Host "[3/8] downloading qdrant web UI..."
    Download-WithFallback @($WebUiUrl) $WebUiZip
} else {
    Write-Host "[3/8] web UI zip already in temp -- skipping download"
}

# --- 2. Extract binaries --------------------------------------------------
function Ensure-Dir($p) { New-Item -ItemType Directory -Force -Path $p | Out-Null }

Ensure-Dir $InstallRoot
$QdrantExe = Join-Path $InstallRoot "qdrant.exe"
if (-not (Test-Path $QdrantExe)) {
    Write-Host "[4/8] extracting qdrant to $InstallRoot..."
    $stage = Join-Path $TmpRoot "qdrant-stage"
    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
    Expand-Archive -Path $QdrantZip -DestinationPath $stage
    # The zip contains qdrant.exe at the root.
    Copy-Item -Path (Join-Path $stage "*") -Destination $InstallRoot -Recurse -Force
} else {
    Write-Host "[4/8] qdrant.exe already at $QdrantExe -- skipping extract"
}

Ensure-Dir $NssmRoot
$NssmExe = Join-Path $NssmRoot "nssm.exe"
if (-not (Test-Path $NssmExe)) {
    Write-Host "[5/8] extracting nssm to $NssmRoot..."
    $stage = Join-Path $TmpRoot "nssm-stage"
    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
    Expand-Archive -Path $NssmZip -DestinationPath $stage
    # nssm zip layout: nssm-2.24\win64\nssm.exe (or nssm-x.x-XXX\win64\)
    $src = Get-ChildItem -Path $stage -Recurse -Filter "nssm.exe" |
        Where-Object { $_.FullName -match "win64" } |
        Select-Object -First 1
    if (-not $src) {
        throw "nssm.exe (win64) not found inside $NssmZip"
    }
    Copy-Item -Path $src.FullName -Destination $NssmExe -Force
} else {
    Write-Host "[5/8] nssm.exe already at $NssmExe -- skipping extract"
}

# Web UI: qdrant binary on Windows ships WITHOUT the dashboard; it serves
# /dashboard from ./static (relative to the service's CWD, which we set
# to $InstallRoot via NSSM AppDirectory below). Extract dist-qdrant.zip
# to $InstallRoot\static\.
$StaticDir = Join-Path $InstallRoot "static"
$StaticMarker = Join-Path $StaticDir "index.html"
if (-not (Test-Path $StaticMarker)) {
    Write-Host "[6/8] extracting web UI to $StaticDir..."
    $stage = Join-Path $TmpRoot "webui-stage"
    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
    Expand-Archive -Path $WebUiZip -DestinationPath $stage
    # dist-qdrant.zip extracts as a "dist/" folder containing index.html etc.
    $distDir = Get-ChildItem -Path $stage -Directory | Where-Object { Test-Path (Join-Path $_.FullName "index.html") } | Select-Object -First 1
    if (-not $distDir) {
        throw "couldn't find index.html inside $WebUiZip"
    }
    if (Test-Path $StaticDir) { Remove-Item -Recurse -Force $StaticDir }
    Move-Item -Path $distDir.FullName -Destination $StaticDir
} else {
    Write-Host "[6/8] web UI already present at $StaticDir -- skipping extract"
}

# --- 3. Data dirs and live config ----------------------------------------
Write-Host "[7/8] ensuring data dirs + writing live config..."
Ensure-Dir (Join-Path $DataRoot "storage")
Ensure-Dir (Join-Path $DataRoot "snapshots")
Ensure-Dir (Split-Path -Parent $ConfigDest)
Copy-Item -Path $RepoConfig -Destination $ConfigDest -Force
Write-Host "  config copied:  $RepoConfig  ->  $ConfigDest"

# --- 4. Register / refresh NSSM service ----------------------------------
$AppParams  = "--config-path `"$ConfigDest`""
$StdoutLog  = Join-Path $DataRoot "qdrant.log"
$StderrLog  = Join-Path $DataRoot "qdrant.err.log"
$Desc       = "Qdrant vector database for IMDR research RAG. Loopback on 127.0.0.1:6333. Data at $DataRoot."

function Set-ServiceCommon {
    & $NssmExe set $ServiceName AppDirectory    $InstallRoot       | Out-Null
    & $NssmExe set $ServiceName DisplayName     "Qdrant (IMDR vector DB)" | Out-Null
    & $NssmExe set $ServiceName Description     $Desc              | Out-Null
    & $NssmExe set $ServiceName Start           SERVICE_AUTO_START | Out-Null
    & $NssmExe set $ServiceName AppStdout       $StdoutLog         | Out-Null
    & $NssmExe set $ServiceName AppStderr       $StderrLog         | Out-Null
    & $NssmExe set $ServiceName AppRotateFiles  1                  | Out-Null
    & $NssmExe set $ServiceName AppRotateBytes  10485760           | Out-Null
}

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    Write-Host "[8/8] service $ServiceName exists -- refreshing arguments..."
    if ($existing.Status -eq 'Running') {
        Write-Host "  stopping running service..."
        & $NssmExe stop $ServiceName | Out-Null
        Start-Sleep -Seconds 2
    }
    & $NssmExe set $ServiceName Application     $QdrantExe         | Out-Null
    & $NssmExe set $ServiceName AppParameters   $AppParams         | Out-Null
    Set-ServiceCommon
} else {
    Write-Host "[8/8] installing $ServiceName service..."
    & $NssmExe install $ServiceName $QdrantExe $AppParams | Out-Null
    Set-ServiceCommon
}

# --- 5. Start service + health check -------------------------------------
Write-Host "starting service + health check..."
& $NssmExe start $ServiceName | Out-Null

$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 750
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:6333/" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $ok = $true
            break
        }
    } catch {
        # not up yet
    }
}

if ($ok) {
    Write-Host ""
    Write-Host "=== INSTALL OK ===" -ForegroundColor Green
    Write-Host "  service : $ServiceName"
    Write-Host "  url     : http://127.0.0.1:6333"
    Write-Host "  health  : 200 OK"
    Write-Host ""
    Write-Host "Next:"
    Write-Host "  python -m imdr.connectors.qdrant_schema apply"
    Write-Host "  python playground\research\test_qdrant_e2e.py"
    exit 0
} else {
    Write-Host ""
    Write-Host "=== INSTALL DONE, BUT HEALTH CHECK FAILED ===" -ForegroundColor Yellow
    Write-Host "  service registered but :6333 not responding."
    Write-Host "  Check: Get-Service $ServiceName"
    Write-Host "         Get-EventLog -LogName Application -Source $ServiceName -Newest 20"
    exit 2
}
