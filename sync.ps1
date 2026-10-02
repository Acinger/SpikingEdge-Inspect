# SE Inspect / VORSA - Uebertragung auf den Pi
#
# Aufruf:   .\sync.ps1
#           .\sync.ps1 -Pi <user>@<PI-IP>    (andere Adresse)
#
# Ueberträgt vorsa/, tools/, start.sh, vorsa.service, install.sh und die
# Dokumente. __pycache__ bleibt aussen vor. Jeder Schritt meldet sich, damit
# ein Abbruch sofort sichtbar ist (2026-10-02: das Skript endete stumm, weil
# PowerShell eine ssh-Warnung auf stderr als Fehler wertete).

param(
    [string]$Pi   = "<user>@<PI-IP>",
    [string]$Ziel = "~/vorsa-m3",
    [string]$Quelle = $PSScriptRoot
)

# NICHT "Stop": native Programme (ssh/scp) schreiben Hinweise auf stderr,
# und PowerShell wuerde das Skript daraufhin ohne Meldung beenden.
$ErrorActionPreference = "Continue"

Write-Host "Quelle: $Quelle"
Write-Host "Ziel:   ${Pi}:${Ziel}"
Write-Host ""

$build = "?"
$serverFile = Join-Path $Quelle "vorsa\web\server.py"
if (Test-Path $serverFile) {
    $m = Select-String -Path $serverFile -Pattern '^BUILD = "(.+)"'
    if ($m) { $build = $m.Matches[0].Groups[1].Value }
}
Write-Host "Lokale Version (Server/Footer): $build"

Write-Host "[1/4] __pycache__ lokal entfernen"
Get-ChildItem -Path (Join-Path $Quelle "vorsa"), (Join-Path $Quelle "tools") -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host "[2/4] Verbindung zum Pi pruefen"
$probe = & ssh -o ConnectTimeout=8 $Pi "mkdir -p $Ziel && echo PI_OK" 2>&1
Write-Host ($probe -join "`n")
if ($LASTEXITCODE -ne 0 -or -not ($probe -match "PI_OK")) {
    Write-Host "ssh zum Pi fehlgeschlagen (Code $LASTEXITCODE). Pi an? Adresse richtig? Schluessel hinterlegt?" -ForegroundColor Red
    exit 1
}

$pfade = @(
    (Join-Path $Quelle "vorsa"),
    (Join-Path $Quelle "tools"),
    (Join-Path $Quelle "SPEC.md"),
    (Join-Path $Quelle "README.md"),
    (Join-Path $Quelle "CHANGELOG.md"),
    (Join-Path $Quelle "start.sh"),
    (Join-Path $Quelle "vorsa.service"),
    (Join-Path $Quelle "install.sh")
) | Where-Object { Test-Path $_ }

Write-Host "[3/4] Dateien kopieren ($($pfade.Count) Pfade)"
& scp -r $pfade "${Pi}:${Ziel}/" 2>&1 | ForEach-Object { Write-Host "      $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "scp fehlgeschlagen (Code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

Write-Host "[4/4] Auf dem Pi aufraeumen und Version lesen"
# start.local.sh traegt die Einstellungen DIESER Anlage (Linie mit Relais und
# Arduino-Arm) und wird nie ueberschrieben - start.sh selbst ist generisch.
$remote = "cd $Ziel && find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; chmod +x start.sh install.sh 2>/dev/null; [ -f start.local.sh ] || printf 'export VORSA_PROFIL=linie\nexport VORSA_BAND=relais\nexport VORSA_ARM=uno\n' > start.local.sh; echo 'Pi:'; grep -m1 '^BUILD = ' vorsa/web/server.py; echo 'start.local.sh:'; cat start.local.sh"
& ssh $Pi $remote 2>&1 | ForEach-Object { Write-Host "      $_" }

Write-Host ""
Write-Host "Uebertragen. Jetzt auf dem Pi:  sudo systemctl restart vorsa   -> Browser Strg+Shift+R, Footer muss $build zeigen." -ForegroundColor Green
