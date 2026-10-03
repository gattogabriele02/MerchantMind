@echo off
REM Auto-elevazione ad amministratore: il PTT usa GetAsyncKeyState, che NON legge i
REM tasti se Skyrim gira elevato (MO2/SKSE) e Mantella no. Rilanciamo come admin.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Richiedo privilegi di amministratore per il PTT...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

REM --- 1) XTTS in una finestra a parte (senza --deepspeed) ---
echo Avvio XTTS in una finestra separata (localhost:8020)...
start "XTTS" /D "C:\XTTS" "C:\XTTS\xttsEnv\Scripts\python.exe" -m xtts_api_server

REM --- 2) attesa caricamento modello XTTS (aumenta se al primo TTS da' errore) ---
echo Attendo il caricamento del modello XTTS (35s)...
timeout /t 35 /nobreak >nul

REM --- 3) Mantella con MerchantMind ---
set MANTELLA_MERCHANTMIND=1
set MANTELLA_MERCHANTMIND_TRADE=1
set MANTELLA_MERCHANTMIND_SEED=42
echo ============================================================
echo  MerchantMind ON  (admin, trade=1, seed=%MANTELLA_MERCHANTMIND_SEED%)
echo ============================================================
MantellaEnv\Scripts\python.exe main.py
pause
