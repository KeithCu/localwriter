# Dev-mode deploy: create a symlink (junction) in LO share\extensions\ pointing
# to the project root, so changes take effect on LO restart without unopkg.
#
# Adapted from mcp-libre/scripts/dev-deploy.sh.
#
# Requires: Run as Administrator (for symlinks)
#
# Usage:
#   .\scripts\dev-deploy.ps1           # Create symlink if missing
#   .\scripts\dev-deploy.ps1 -Remove   # Remove the symlink

param(
    [switch]$Remove,
    [switch]$Help
)

if ($Help) {
    Write-Host "Usage: .\scripts\dev-deploy.ps1 [-Remove]"
    Write-Host "  -Remove : remove the symlink"
    Write-Host ""
    Write-Host "Requires: Run as Administrator"
    exit 0
}

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ExtName = "localwriter"

# ── Find LO extensions dir ──────────────────────────────────────────────────

$loExtDir = $null
$candidates = @(
    "${env:ProgramFiles}\LibreOffice\share\extensions",
    "${env:ProgramFiles(x86)}\LibreOffice\share\extensions",
    "C:\Program Files\LibreOffice\share\extensions",
    "C:\Program Files (x86)\LibreOffice\share\extensions"
)

foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
        $loExtDir = $candidate
        break
    }
}

if (-not $loExtDir) {
    Write-Host "[X] LibreOffice share\extensions not found"
    exit 1
}

$symlinkPath = Join-Path $loExtDir $ExtName

# ── Remove mode ──────────────────────────────────────────────────────────────

if ($Remove) {
    if (Test-Path $symlinkPath) {
        # Junction/symlink: use cmd /c rmdir to remove without deleting target
        cmd /c rmdir "$symlinkPath" 2>$null
        if (-not (Test-Path $symlinkPath)) {
            Write-Host "[OK] Symlink removed: $symlinkPath"
        } else {
            Remove-Item -Path $symlinkPath -Force -Recurse
            Write-Host "[OK] Symlink removed: $symlinkPath"
        }
    } else {
        Write-Host "[OK] No symlink to remove"
    }
    exit 0
}

# ── Clean __pycache__ ────────────────────────────────────────────────────────

Get-ChildItem -Path $ProjectRoot -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# ── Create symlink if missing ────────────────────────────────────────────────

if (Test-Path $symlinkPath) {
    $target = (Get-Item $symlinkPath).Target
    if (-not $target) { $target = $symlinkPath }
    Write-Host "[OK] Symlink already exists: $symlinkPath -> $target"
} else {
    Write-Host "[*] Creating symlink: $symlinkPath -> $ProjectRoot"
    # Use directory junction (works without Developer Mode)
    cmd /c mklink /J "$symlinkPath" "$ProjectRoot"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to create symlink. Run as Administrator."
        exit 1
    }
    Write-Host "[OK] Symlink created"
}

# ── Re-register bundled extensions ───────────────────────────────────────────

$unopkg = $null
$unopkgCandidates = @(
    "${env:ProgramFiles}\LibreOffice\program\unopkg.exe",
    "${env:ProgramFiles(x86)}\LibreOffice\program\unopkg.exe",
    "C:\Program Files\LibreOffice\program\unopkg.exe",
    "C:\Program Files (x86)\LibreOffice\program\unopkg.exe"
)

foreach ($candidate in $unopkgCandidates) {
    if (Test-Path $candidate) {
        $unopkg = $candidate
        break
    }
}

if ($unopkg) {
    Get-Process -Name "soffice", "soffice.bin" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    & $unopkg reinstall --bundled 2>$null
    $lockFile = Join-Path $env:APPDATA "LibreOffice\4\user\.lock"
    if (Test-Path $lockFile) {
        Remove-Item -Path $lockFile -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[OK] Bundled extensions re-registered"
} else {
    Write-Host "[!] unopkg not found, skip bundled reinstall"
}

Write-Host ""
Write-Host "=== Dev Deploy Done ==="
Write-Host "  Project: $ProjectRoot"
Write-Host "  Symlink: $symlinkPath"
Write-Host "  Restart LibreOffice to load changes."
Write-Host ""
