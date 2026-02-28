# Kill all running LibreOffice processes.
#
# Usage:
#   .\scripts\kill-libreoffice.ps1

$Processes = @("soffice", "soffice.bin", "oosplash")
$killed = 0

foreach ($name in $Processes) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        Write-Host "[OK] Killing $name (PID $($p.Id))"
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        $killed++
    }
}

if ($killed -eq 0) {
    Write-Host "[OK] No LibreOffice process running."
} else {
    Write-Host "[OK] Killed $killed process(es)."
}
