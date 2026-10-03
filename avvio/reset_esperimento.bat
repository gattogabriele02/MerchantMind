@echo off
REM Reset degli stati dei 3 mercanti al baseline pre-caricato.
REM Eseguire PRIMA di ogni partecipante (NON a meta' sessione).
cd /d "%~dp0"

REM --- controllo: le conversazioni del partecipante precedente sono state archiviate? ---
REM Mantella ricarica i riassunti come contesto: se restano lì, il mercante si ricorda
REM della sessione precedente. A toglierle e' archivia_sessione.ps1, non questo script.
powershell -NoProfile -Command ^
  "$c = Join-Path $env:USERPROFILE 'Documents\My Games\Mantella\data\Skyrim\conversations';" ^
  "$r = @(Get-ChildItem $c -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'Prigioniero*' });" ^
  "if ($r.Count -gt 0) { Write-Host ''; Write-Host '  ATTENZIONE: ci sono ancora conversazioni non archiviate:' -ForegroundColor Yellow;" ^
  "  $r | ForEach-Object { Write-Host ('    ' + $_.Name) };" ^
  "  Write-Host '  Lancia prima:  .\archivia_sessione.ps1 -Codice <P0N> -Build <1-4>' -ForegroundColor Yellow;" ^
  "  Write-Host '  Altrimenti il prossimo partecipante trova mercanti che ricordano il precedente.' -ForegroundColor Yellow; Write-Host '' }"

echo Reset stati mercanti per il personaggio "Prigioniero"...
MantellaEnv\Scripts\python.exe scripts\seed_experiment.py --player "Prigioniero"
echo.
echo Fatto. Atteso: admiration ^< neutral ^< distrust (prezzi crescenti).
pause
