#Requires -Version 5.1
<#
.SYNOPSIS
  Build the Qf Direct Invest Tracker desktop app for Windows (NSIS installer).

.DESCRIPTION
  Two-stage build:
    1. Bundle the Python/FastAPI backend into a standalone binary via PyInstaller.
    2. Build the Electron + Vite frontend and package it with electron-builder (NSIS).

.PARAMETER FrontendOnly
  Skip the PyInstaller backend build and only rebuild the frontend/Electron app.

.EXAMPLE
  .\scripts\build-desktop-win.ps1                # full rebuild
  .\scripts\build-desktop-win.ps1 -FrontendOnly  # skip backend, rebuild frontend only

.NOTES
  Prerequisites (first run only):
    cd backend; python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt pyinstaller
    cd ..\frontend; npm install
#>
param(
    [switch]$FrontendOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root     = Split-Path -Parent $PSScriptRoot
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

Write-Host "============================================================"
Write-Host "  Qf Direct Invest Tracker -- Windows desktop build"
Write-Host "============================================================"

# ── 1. Backend (PyInstaller) ─────────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Host ""
    Write-Host ">>> [1/3] Building Python backend binary..."

    $venvPython = Join-Path $Backend ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Host "    ERROR: backend\.venv not found." -ForegroundColor Red
        Write-Host "    Run once to set up:"
        Write-Host "      cd backend"
        Write-Host "      python -m venv .venv"
        Write-Host "      .venv\Scripts\pip install -r requirements.txt pyinstaller"
        exit 1
    }

    $pyinstaller = Join-Path $Backend ".venv\Scripts\pyinstaller.exe"
    if (-not (Test-Path $pyinstaller)) {
        Write-Host "    ERROR: pyinstaller not found in venv." -ForegroundColor Red
        Write-Host "    Run:  .venv\Scripts\pip install pyinstaller"
        exit 1
    }

    Push-Location $Backend
    try {
        if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
        if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist" }

        & $pyinstaller backend.spec
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (exit code $LASTEXITCODE)" }

        Write-Host "    Backend binary: dist\investments-backend\"
    }
    finally {
        Pop-Location
    }

    # ── 1b. Patch missing Conda DLLs ─────────────────────────────────────────
    #   When Python is installed via Miniconda/Anaconda, certain DLLs live in
    #   Library\bin and PyInstaller cannot locate them automatically.
    Write-Host ""
    Write-Host ">>> [2/3] Checking for missing Conda DLLs..."

    $distInternal = Join-Path $Backend "dist\investments-backend\_internal"
    $condaBin     = $null

    # Walk up from the Python executable to find the conda Library\bin
    $pythonDir = Split-Path (& $venvPython -c "import sys; print(sys.base_prefix)")
    $candidatePaths = @(
        (Join-Path $pythonDir "Library\bin"),
        "C:\ProgramData\miniconda3\Library\bin",
        "$env:USERPROFILE\miniconda3\Library\bin",
        "$env:USERPROFILE\anaconda3\Library\bin"
    )
    foreach ($p in $candidatePaths) {
        if (Test-Path $p) { $condaBin = $p; break }
    }

    $dllsToCopy = @("sqlite3.dll", "libmpdec-4.dll", "liblzma.dll", "LIBBZ2.dll", "libexpat.dll", "ffi.dll")
    $copied = 0

    foreach ($dll in $dllsToCopy) {
        $destFile = Join-Path $distInternal $dll
        if (Test-Path $destFile) { continue }

        if ($condaBin) {
            $srcFile = Join-Path $condaBin $dll
            if (Test-Path $srcFile) {
                Copy-Item $srcFile $destFile
                Write-Host "    Copied $dll"
                $copied++
            }
        }
    }

    if ($copied -eq 0) {
        Write-Host "    No missing DLLs to patch (all present or non-Conda Python)."
    }
}
else {
    Write-Host ""
    Write-Host ">>> [1/3] Skipping backend build (-FrontendOnly flag set)"
    Write-Host ">>> [2/3] Skipping DLL patch  (-FrontendOnly flag set)"
}

# ── 2. Pre-populate electron-builder winCodeSign cache ────────────────────────
#   The winCodeSign-2.6.0.7z archive contains macOS symlinks that fail to
#   extract without Developer Mode or admin privileges. We extract it ourselves
#   (ignoring the harmless symlink errors) so electron-builder finds it cached.
Write-Host ""
$cacheDir = Join-Path $env:LOCALAPPDATA "electron-builder\Cache\winCodeSign\winCodeSign-2.6.0"
if (-not (Test-Path $cacheDir)) {
    Write-Host ">>> Preparing electron-builder winCodeSign cache..."

    $sevenZip = Join-Path $Frontend "node_modules\7zip-bin\win\x64\7za.exe"
    if (-not (Test-Path $sevenZip)) {
        Write-Host "    7za.exe not found -- run 'npm install' in frontend/ first." -ForegroundColor Red
        exit 1
    }

    $archiveUrl = "https://github.com/electron-userland/electron-builder-binaries/releases/download/winCodeSign-2.6.0/winCodeSign-2.6.0.7z"
    $archivePath = Join-Path $env:TEMP "winCodeSign-2.6.0.7z"

    Write-Host "    Downloading winCodeSign-2.6.0..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath -UseBasicParsing

    New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null

    Write-Host "    Extracting (symlink warnings for macOS files are expected)..."
    & $sevenZip x -bd $archivePath "-o$cacheDir" 2>&1 | Out-Null
    # Exit code 2 = warnings (symlinks) -- safe to ignore on Windows
    Write-Host "    winCodeSign cache ready."
}
else {
    Write-Host ">>> winCodeSign cache already present -- skipping."
}

# ── 3. Frontend (Electron + Vite) ────────────────────────────────────────────
Write-Host ""
Write-Host ">>> [3/3] Building Electron app..."

Push-Location $Frontend
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "    node_modules not found -- running npm install..."
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    }

    # Disable auto code-signing discovery (no certificate needed for local builds)
    $env:CSC_IDENTITY_AUTO_DISCOVERY = "false"

    npm run electron:build
    if ($LASTEXITCODE -ne 0) { throw "electron-builder failed (exit code $LASTEXITCODE)" }
}
finally {
    Pop-Location
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================"
Write-Host "  Build complete!"
Write-Host ""

$installers = Get-ChildItem -Path (Join-Path $Frontend "release") -Filter "*.exe" -ErrorAction SilentlyContinue
if ($installers) {
    foreach ($f in $installers) {
        $sizeMB = [math]::Round($f.Length / 1MB, 1)
        Write-Host "  $($f.Name)  ($sizeMB MB)"
    }
}
else {
    Get-ChildItem -Path (Join-Path $Frontend "release")
}

Write-Host "============================================================"
