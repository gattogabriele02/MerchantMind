# Archivia i dati di UNA sessione sperimentale in una cartella dedicata.
#
#   .\archivia_sessione.ps1 -Codice P02 -Build 2
#
# Cosa fa:
#   1. SPOSTA i CSV da  data/merchantmind/logs/         -> sessioni/<Codice>/logs/
#   2. SPOSTA le conversazioni Mantella del PG          -> sessioni/<Codice>/conversazioni/
#   3. COPIA gli stati finali dei mercanti              -> sessioni/<Codice>/stati_finali/
#   4. CREA i moduli dati da compilare a mano           -> sessioni/<Codice>/dati/
#   5. Scrive info.txt con session_id e righe per file
#   6. Ricrea logs/ e conversations/ vuote per il partecipante successivo
#
# Le conversazioni VANNO spostate, non copiate: Mantella ricarica i riassunti come
# contesto, quindi se restano lì il mercante del partecipante successivo si ricorda
# della sessione precedente.
#
# Non cancella mai nulla: sposta. Se la cartella di destinazione esiste gia', si ferma.

param(
    [Parameter(Mandatory = $true)]
    [string]$Codice,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 4)]
    [int]$Build,

    [string]$Pg = 'Prigioniero'
)

$ErrorActionPreference = 'Stop'

$Mantella     = Join-Path $env:USERPROFILE 'Documents\My Games\Mantella\data'
$MerchantMind = Join-Path $Mantella 'merchantmind'
$Logs         = Join-Path $MerchantMind 'logs'
$Conversazioni= Join-Path $Mantella 'Skyrim\conversations'
$Destinazione = Join-Path $PSScriptRoot "sessioni\$Codice"

# --- il quadrato latino: ordine delle condizioni per ciascuna build --------
$Sequenze = @{
    1 = @('V', 'N', 'A', 'D')
    2 = @('N', 'D', 'V', 'A')
    3 = @('A', 'V', 'D', 'N')
    4 = @('D', 'A', 'N', 'V')
}
$Mercanti = @{
    'V' = 'adrianne_avenicci'
    'N' = 'arcadia'
    'A' = 'belethor'
    'D' = 'lucan_valerius'
}

# Scrive un file di testo in UTF-8 SENZA BOM: Set-Content -Encoding utf8 in
# PowerShell 5.1 lo mette, e pandas se lo ritrova incollato al nome della
# prima colonna.
function Scrivi-Testo {
    param([string]$Percorso, [string[]]$Righe)
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($Percorso, $Righe, $utf8)
}

# --- controlli preliminari -------------------------------------------------
if (-not (Test-Path $MerchantMind)) {
    Write-Host "ERRORE: non trovo $MerchantMind" -ForegroundColor Red
    Write-Host "Hai gia' avviato Mantella con MANTELLA_MERCHANTMIND=1 almeno una volta?"
    exit 1
}
if (Test-Path $Destinazione) {
    Write-Host "ERRORE: la cartella sessioni\$Codice esiste gia'." -ForegroundColor Red
    Write-Host "Usa un codice diverso: non sovrascrivo dati esistenti."
    exit 1
}
if (-not (Test-Path $Logs)) {
    Write-Host "ATTENZIONE: non esiste $Logs - nessun log da archiviare." -ForegroundColor Yellow
    exit 1
}

$CsvPresenti = @(Get-ChildItem $Logs -Filter *.csv -ErrorAction SilentlyContinue)
if ($CsvPresenti.Count -eq 0) {
    Write-Host "ATTENZIONE: la cartella logs e' vuota - niente da archiviare." -ForegroundColor Yellow
    exit 1
}

# --- 1) sposta i log -------------------------------------------------------
New-Item -ItemType Directory -Path $Destinazione -Force | Out-Null
Move-Item -Path $Logs -Destination (Join-Path $Destinazione 'logs')
New-Item -ItemType Directory -Path $Logs -Force | Out-Null

# --- 2) sposta le conversazioni Mantella del personaggio -------------------
$ConvSpostate = @()
if (Test-Path $Conversazioni) {
    $CartelleConv = @(Get-ChildItem $Conversazioni -Directory -ErrorAction SilentlyContinue |
                      Where-Object { $_.Name -like "$Pg*" })
    if ($CartelleConv.Count -gt 0) {
        $DestConv = Join-Path $Destinazione 'conversazioni'
        New-Item -ItemType Directory -Path $DestConv -Force | Out-Null
        foreach ($c in $CartelleConv) {
            Move-Item -Path $c.FullName -Destination $DestConv
            $ConvSpostate += $c.Name
        }
    }
}

# --- 3) copia gli stati finali dei mercanti --------------------------------
$Stati = Join-Path $Destinazione 'stati_finali'
New-Item -ItemType Directory -Path $Stati -Force | Out-Null
$CartellaPg = Join-Path $MerchantMind $Pg
if (Test-Path $CartellaPg) {
    Copy-Item -Path $CartellaPg -Destination $Stati -Recurse
} else {
    Write-Host "ATTENZIONE: non trovo gli stati di '$Pg' in $MerchantMind" -ForegroundColor Yellow
}

# --- 4) moduli dati da compilare a mano ------------------------------------
# Formato principale: un foglio Excel con le domande accanto alle caselle.
# Se Python o openpyxl non sono disponibili si ripiega sui CSV (che pero' in
# Excel italiano si aprono tutti in una cella sola: separatore virgola).
$Dati = Join-Path $Destinazione 'dati'
New-Item -ItemType Directory -Path $Dati -Force | Out-Null
$Oggi = Get-Date -Format 'yyyy-MM-dd'

$Python  = Join-Path $PSScriptRoot 'MantellaEnv\Scripts\python.exe'
$Creatore = Join-Path $PSScriptRoot 'scripts\crea_modulo_dati.py'
$XlsxCreato = $false
if ((Test-Path $Python) -and (Test-Path $Creatore)) {
    & $Python $Creatore $Codice $Build 2>&1 | Out-Null
    $XlsxCreato = Test-Path (Join-Path $Dati "dati_$Codice.xlsx")
}
if (-not $XlsxCreato) {
    Write-Host "  (foglio Excel non creato: ripiego sui CSV)" -ForegroundColor Yellow
}

if (-not $XlsxCreato) {

# 4a) scheda di sessione: una riga, metadati + demografia + prezzo vanilla
$IntestazioneSessione = 'partecipante,build,data,eta,genere,lingua_madre,ore_gioco,' +
    'esperienza_skyrim,conosce_commercio,altri_gdr,assistenti_vocali,parlato_npc,' +
    'prezzo_vanilla,durata_minuti,note'
$RigaSessione = "$Codice,$Build,$Oggi,,,,,,,,,,50,,"
Scrivi-Testo -Percorso (Join-Path $Dati 'sessione.csv') -Righe @($IntestazioneSessione, $RigaSessione)

# 4b) questionari per mercante: 4 righe GIA' etichettate secondo la build
$ColonneItem = (1..17 | ForEach-Object { 'i{0:d2}' -f $_ }) -join ','
$RigheQuest = @("partecipante,build,posizione,condizione,mercante,$ColonneItem")
$pos = 1
foreach ($cond in $Sequenze[$Build]) {
    $vuoti = (',' * 17)
    $RigheQuest += "$Codice,$Build,$pos,$cond,$($Mercanti[$cond])$vuoti"
    $pos++
}
Scrivi-Testo -Percorso (Join-Path $Dati 'questionari.csv') -Righe $RigheQuest

# 4c) questionario finale: una riga
$ColonneB = (1..14 | ForEach-Object { 'b{0:d2}' -f $_ }) -join ','
$IntestazioneFinale = 'partecipante,build,a1_differenze,a3_ordine_1,a3_ordine_2,a3_ordine_3,' +
    "a3_ordine_4,a4_ostile,a4_amichevole,a5_ricordava,a6_coinvolgente,a7_attribuzione,$ColonneB"
$RigaFinale = "$Codice,$Build" + (',' * 24)
Scrivi-Testo -Percorso (Join-Path $Dati 'finale.csv') -Righe @($IntestazioneFinale, $RigaFinale)

# 4d) risposte aperte: testo, fuori dai file numerici
$Aperte = @()
$Aperte += "# Risposte aperte - $Codice (build $Build)"
$Aperte += ''
$Aperte += 'Trascrivere alla lettera, senza correggere ne sintetizzare.'
$Aperte += ''
$pos = 1
foreach ($cond in $Sequenze[$Build]) {
    $Aperte += "## $pos. $($Mercanti[$cond]) (condizione $cond) - che impressione ti ha fatto"
    $Aperte += ''
    $Aperte += ''
    $pos++
}
$Aperte += '## Finale 2 - in che cosa erano diversi'
$Aperte += ''
$Aperte += ''
$Aperte += '## Finale 8 - qualcosa che non tornava'
$Aperte += ''
$Aperte += ''
$Aperte += '## Finale B - cosa cambieresti / altro'
$Aperte += ''
$Aperte += ''
$Aperte += '## Note del conduttore'
$Aperte += ''
Scrivi-Testo -Percorso (Join-Path $Dati 'aperte.md') -Righe $Aperte

}  # fine ripiego CSV

# --- 5) info.txt di riepilogo ---------------------------------------------
$LogArchiviati = Join-Path $Destinazione 'logs'
$Righe = @()
$Righe += "Sessione:   $Codice"
$Righe += "Build:      $Build   ->  $($Sequenze[$Build] -join ' ')"
$Righe += "Archiviata: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$Righe += ''
$Righe += "File di log (righe dati, esclusa l'intestazione):"

# NB: si usa Import-Csv, non uno split manuale sulle virgole: le battute degli NPC
# contengono virgole e a capo dentro campi quotati, che spezzerebbero il conteggio.
$SessionIds = @()
$NumTransazioni = 0
foreach ($f in (Get-ChildItem $LogArchiviati -Filter *.csv | Sort-Object Name)) {
    try {
        $righeCsv = @(Import-Csv -Path $f.FullName)
    } catch {
        $Righe += ("  {0,-42} {1,5}" -f $f.Name, 'ERR')
        continue
    }
    $Righe += ("  {0,-42} {1,5}" -f $f.Name, $righeCsv.Count)
    if ($f.Name -eq 'merchant_transactions_log.csv') { $NumTransazioni = $righeCsv.Count }
    if ($righeCsv.Count -gt 0 -and ($righeCsv[0].PSObject.Properties.Name -contains 'session_id')) {
        $SessionIds += ($righeCsv | ForEach-Object { $_.session_id })
    }
}

$SessionIds = $SessionIds | Where-Object { $_ } | Sort-Object -Unique
$Righe += ''
$Righe += "session_id presenti: $($SessionIds.Count)"
foreach ($id in $SessionIds) { $Righe += "  $id" }
if ($SessionIds.Count -gt 1) {
    $Righe += ''
    $Righe += "ATTENZIONE: piu' di un session_id. Mantella e' stato riavviato durante"
    $Righe += "la sessione, oppure questa cartella contiene piu' di un partecipante."
}

# Con Mantella lasciato acceso fra un partecipante e l'altro il session_id resta
# lo stesso, quindi il controllo qui sopra non rileva piu' un'archiviazione
# dimenticata. Il numero di transazioni si': 3 affari MerchantMind a testa
# (la condizione V passa dal baratto vanilla e non lascia traccia).
$Righe += ''
$Righe += "transazioni registrate: $NumTransazioni (attese 3)"
if ($NumTransazioni -gt 3) {
    $Righe += ''
    $Righe += "ATTENZIONE: piu' di 3 transazioni. Molto probabilmente questa cartella"
    $Righe += "contiene anche il partecipante precedente: archiviazione dimenticata."
} elseif ($NumTransazioni -lt 3) {
    $Righe += ''
    $Righe += "ATTENZIONE: meno di 3 transazioni. Una trattativa non e' stata"
    $Righe += "registrata: abbandono, oppure lo scambio non e' scattato."
}
$Righe += ''
if ($ConvSpostate.Count -gt 0) {
    $Righe += "Conversazioni Mantella archiviate: $($ConvSpostate -join ', ')"
} else {
    $Righe += "ATTENZIONE: nessuna conversazione Mantella trovata per '$Pg'."
}
$Righe += "Stati finali copiati da: $Pg"
$Righe += ''
if ($XlsxCreato) {
    $Righe += "Da compilare a mano: dati/dati_$Codice.xlsx (4 fogli)"
} else {
    $Righe += 'Da compilare a mano in dati/: sessione.csv, questionari.csv, finale.csv, aperte.md'
}

Scrivi-Testo -Percorso (Join-Path $Destinazione 'info.txt') -Righe $Righe

# --- riepilogo a video -----------------------------------------------------
Write-Host ''
Write-Host "=== Sessione $Codice archiviata (build $Build) ===" -ForegroundColor Green
Write-Host "  in: sessioni\$Codice\"
Write-Host ''
$Righe | Select-Object -Skip 4 | ForEach-Object { Write-Host "  $_" }
Write-Host ''
if ($SessionIds.Count -gt 1) {
    Write-Host '  ^^^ controlla il punto segnalato sopra' -ForegroundColor Yellow
    Write-Host ''
}
if ($ConvSpostate.Count -eq 0) {
    Write-Host "  ^^^ senza conversazioni archiviate, controlla il nome del PG (-Pg)" -ForegroundColor Yellow
    Write-Host ''
}
if ($XlsxCreato) {
    Write-Host "  Adesso apri:  sessioni\$Codice\dati\dati_$Codice.xlsx" -ForegroundColor Cyan
    Write-Host '  (4 fogli: sessione, questionari, finale, aperte - caselle gialle)' -ForegroundColor Cyan
} else {
    Write-Host '  Adesso: compila i moduli in dati\ mentre hai la sessione fresca.' -ForegroundColor Cyan
}
Write-Host '  Poi, per il prossimo partecipante:' -ForegroundColor Cyan
Write-Host '    reset_esperimento.bat   (rimette i mercanti al baseline)'
Write-Host '    avvia_esperimento.bat   (XTTS + Mantella)'
Write-Host ''
