# install.ps1 — Set up the LocalWriter development environment (Windows).
#
# Usage:
#   .\install.ps1          Install dev dependencies
#   .\install.ps1 -Check   Verify environment only

param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"

function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "LocalWriter Development Setup"
Write-Host "=============================="
Write-Host ""

# -- Python ----------------------------------------------------------------

$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1 | Select-Object -First 1
        $python = $cmd
        Write-Ok "Found $ver"
        break
    } catch { }
}

if (-not $python) {
    Write-Err "Python 3.8+ not found. Install Python first."
    exit 1
}

# -- pip -------------------------------------------------------------------

try {
    & $python -m pip --version 2>&1 | Out-Null
    Write-Ok "pip available"
} catch {
    Write-Err "pip not found. Install pip: $python -m ensurepip"
    exit 1
}

# -- PyYAML ----------------------------------------------------------------

try {
    & $python -c "import yaml" 2>&1 | Out-Null
    Write-Ok "PyYAML installed"
} catch {
    if ($Check) {
        Write-Warn "PyYAML not installed (needed for build)"
    } else {
        Write-Host "Installing PyYAML..."
        & $python -m pip install --user pyyaml
        Write-Ok "PyYAML installed"
    }
}

# -- LibreOffice -----------------------------------------------------------

$lo = $null
$loSearchPaths = @(
    "$env:ProgramFiles\LibreOffice\program\soffice.exe",
    "${env:ProgramFiles(x86)}\LibreOffice\program\soffice.exe"
)

foreach ($path in $loSearchPaths) {
    if (Test-Path $path) {
        $lo = $path
        Write-Ok "LibreOffice found at $path"
        break
    }
}

if (-not $lo) {
    if (Get-Command soffice -ErrorAction SilentlyContinue) {
        Write-Ok "LibreOffice found on PATH"
    } else {
        Write-Warn "LibreOffice not found (needed for running the extension)"
    }
}

# -- unopkg ----------------------------------------------------------------

if (Get-Command unopkg -ErrorAction SilentlyContinue) {
    Write-Ok "unopkg available"
} else {
    Write-Warn "unopkg not found (needed for extension installation)"
}

# -- bash (Git for Windows) ------------------------------------------------

$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($bash) {
    Write-Ok "bash available at $($bash.Source)"
} elseif ($Check) {
    Write-Warn "bash not found -- needed by Makefile (install Git for Windows)"
} else {
    Write-Host "Installing Git for Windows via winget..."
    $gitResult = Start-Process -FilePath winget -ArgumentList "install","--id","Git.Git","--accept-package-agreements","--accept-source-agreements" -Wait -PassThru -NoNewWindow 2>$null
    $gitBash = "$env:ProgramFiles\Git\usr\bin"
    if (Test-Path (Join-Path $gitBash "bash.exe")) {
        $env:Path += ";$gitBash"
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($userPath -notlike "*Git*usr*bin*") {
            [Environment]::SetEnvironmentVariable("Path", "$userPath;$gitBash", "User")
        }
        Write-Ok "bash installed and added to PATH -- restart your terminal to use it"
    } elseif (Get-Command bash -ErrorAction SilentlyContinue) {
        Write-Ok "bash installed"
    } else {
        Write-Warn "bash install failed -- install Git for Windows manually: winget install Git.Git"
    }
}

# -- make ------------------------------------------------------------------

if (Get-Command make -ErrorAction SilentlyContinue) {
    Write-Ok "make available"
} elseif ($Check) {
    Write-Warn "make not found -- needed for build commands"
} else {
    Write-Host "Installing make via winget..."
    $wingetResult = Start-Process -FilePath winget -ArgumentList "install","--id","GnuWin32.Make","--accept-package-agreements","--accept-source-agreements" -Wait -PassThru -NoNewWindow 2>$null
    $gnuBin = Join-Path ${env:ProgramFiles} "..\Program Files (x86)\GnuWin32\bin"
    if (-not (Test-Path (Join-Path $gnuBin "make.exe"))) {
        $gnuBin = "C:\Program Files (x86)\GnuWin32\bin"
    }
    if (Test-Path (Join-Path $gnuBin "make.exe")) {
        $env:Path += ";$gnuBin"
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($userPath -notlike "*GnuWin32*") {
            [Environment]::SetEnvironmentVariable("Path", "$userPath;$gnuBin", "User")
        }
        Write-Ok "make installed and added to PATH -- restart your terminal to use it"
    } elseif (Get-Command make -ErrorAction SilentlyContinue) {
        Write-Ok "make installed"
    } else {
        Write-Warn "make install failed -- install manually: winget install GnuWin32.Make"
    }
}

# -- openssl ---------------------------------------------------------------

if (Get-Command openssl -ErrorAction SilentlyContinue) {
    Write-Ok "openssl available (for MCP TLS certificates)"
} else {
    Write-Warn "openssl not found (optional, needed for MCP HTTPS)"
}

# -- Vendored dependencies ---------------------------------------------

if (Test-Path "requirements-vendor.txt") {
    if ($Check) {
        if (Test-Path "vendor") {
            Write-Ok "vendor/ directory exists"
        } else {
            Write-Warn "vendor/ not populated (run: make vendor)"
        }
    } else {
        Write-Host "Installing vendored dependencies..."
        & $python -m pip install --target vendor -r requirements-vendor.txt
        Write-Ok "Vendored dependencies installed"
    }
}

Write-Host ""

if ($Check) {
    Write-Host "Environment check complete."
} else {
    Write-Host "Setup complete. Available commands:"
    Write-Host "  make build          Build the .oxt extension"
    Write-Host "  make install        Build + install in LibreOffice"
    Write-Host "  make dev-deploy     Symlink for fast dev iteration"
    Write-Host "  make lo-start       Launch LibreOffice with debug logging"
}
