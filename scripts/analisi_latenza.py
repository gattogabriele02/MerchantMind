"""Latenza dei componenti durante le 27 sessioni sperimentali.

    python scripts/analisi_latenza.py

Il tracciatore di latenza di Mantella scrive un unico file cumulativo in
Documents/My Games/Mantella/latency_log.csv, che copre anche lo sviluppo: non e'
archiviato per sessione come i log di MerchantMind. Qui le righe vengono attribuite
ai partecipanti per FINESTRA TEMPORALE, perche' l'identificatore di sessione di
Mantella cambia a ogni conversazione (uno per mercante) e non coincide con quello
di MerchantMind (il primo della sessione).

La finestra di ciascun partecipante va dall'istante del suo session_id all'inizio
del partecipante successivo; per l'ultimo si usa la durata dichiarata nella scheda.
Le righe fuori da ogni finestra sono scartate: sono prove di sviluppo.

Scrive analisi/latenza.txt e analisi/latenza_sessioni.csv, portando dentro il
repository le sole righe che riguardano l'esperimento.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "scripts"))

from test_statistici import num  # noqa: E402

ANALISI = RADICE / "analisi"
SESSIONI = RADICE / "sessioni"
SORGENTE = Path.home() / "Documents" / "My Games" / "Mantella" / "latency_log.csv"

COLONNE = ["timestamp", "session_id", "npc", "turno", "fase", "secondi"]

# Nome leggibile e ruolo di ciascuna fase misurata.
FASI = {
    "stt_transcription": ("trascrizione del parlato (STT)", "per battuta del giocatore"),
    "llm_ttft": ("modello linguistico, prima parola", "per battuta del mercante"),
    "llm_full": ("modello linguistico, risposta intera", "per battuta del mercante"),
    "tts_http_request": ("sintesi vocale (TTS)", "per frase pronunciata"),
    "mm_llm_opening": ("MerchantMind: battuta di apertura", "una per trattativa"),
    "mm_llm_counter": ("MerchantMind: controfferta", "per round"),
    "mm_llm_close": ("MerchantMind: chiusura", "una per trattativa"),
    "mm_llm_intent": ("MerchantMind: predizione dell'intento", "per battuta"),
    "mm_llm_detect": ("MerchantMind: riconoscimento dell'offerta", "per battuta"),
    "mm_llm_parse": ("MerchantMind: lettura del prezzo", "per battuta"),
    "mm_llm_clarify": ("MerchantMind: richiesta di chiarimento", "quando serve"),
}

righe: list[str] = []


def stampa(testo: str = "") -> None:
    righe.append(testo)


def finestre() -> pd.DataFrame:
    """Inizio e fine di ogni sessione, in ora locale, dai log di MerchantMind."""
    voci = []
    for cartella in sorted(SESSIONI.glob("P*")):
        log = cartella / "logs" / "negotiation_turns_log.csv"
        if not log.is_file():
            continue
        codice_sessione = str(pd.read_csv(log).session_id.iloc[0])
        voci.append({"partecipante": cartella.name,
                     "inizio": pd.to_datetime(codice_sessione, format="%Y%m%d_%H%M%S")})
    quadro = pd.DataFrame(voci).sort_values("inizio").reset_index(drop=True)
    # La finestra si chiude all'inizio della sessione successiva; per l'ultima, e per
    # ogni sessione seguita da una pausa lunga, si usa un'ora e mezza.
    limite = pd.Timedelta(minutes=90)
    successivo = quadro.inizio.shift(-1)
    quadro["fine"] = successivo.where(
        (successivo - quadro.inizio) < limite, quadro.inizio + limite)
    quadro.loc[quadro.index[-1], "fine"] = quadro.inizio.iloc[-1] + limite
    return quadro


def main() -> None:
    if not SORGENTE.is_file():
        sys.exit(f"non trovo {SORGENTE}")

    lat = pd.read_csv(SORGENTE, header=None, names=COLONNE)
    lat["istante"] = pd.to_datetime(lat.timestamp)
    quadro = finestre()

    lat["partecipante"] = pd.NA
    for voce in quadro.itertuples():
        dentro = (lat.istante >= voce.inizio) & (lat.istante < voce.fine)
        lat.loc[dentro, "partecipante"] = voce.partecipante
    dentro = lat[lat.partecipante.notna()].copy()

    stampa("LATENZA DEI COMPONENTI DURANTE LE SESSIONI SPERIMENTALI")
    stampa()
    stampa(f"   righe nel file cumulativo: {len(lat)}")
    stampa(f"   righe attribuite alle sessioni: {len(dentro)}")
    stampa(f"   sessioni coperte: {dentro.partecipante.nunique()} su {len(quadro)}")
    stampa(f"   periodo: {dentro.istante.min():%d/%m/%Y %H:%M} — "
           f"{dentro.istante.max():%d/%m/%Y %H:%M}")
    stampa()
    stampa("Le righe fuori finestra appartengono allo sviluppo e sono scartate.")
    stampa("Ogni fase e' misurata separatamente: la somma NON e' un tempo di risposta")
    stampa("misurato punto a punto, perche' le fasi si accavallano (la sintesi parte")
    stampa("sulla prima frase mentre il modello sta ancora generando le successive).")

    stampa()
    stampa(f"   {'fase':44} {'n':>5} {'mediana':>9} {'q1':>7} {'q3':>7} {'max':>7}")
    for fase, (nome, unita) in FASI.items():
        sotto = dentro[dentro.fase == fase].secondi
        if sotto.empty:
            continue
        stampa(f"   {nome + ' — ' + unita:44} {len(sotto):5} "
               f"{num(sotto.median(), 2):>9} {num(sotto.quantile(0.25), 2):>7} "
               f"{num(sotto.quantile(0.75), 2):>7} {num(sotto.max(), 2):>7}")

    # Le tre fasi che il giocatore attende una dopo l'altra prima di sentire la voce.
    stampa()
    stampa("   catena percepita dal giocatore (mediane): "
           "trascrizione + prima parola del modello + prima frase sintetizzata")
    catena = {f: dentro.loc[dentro.fase == f, "secondi"].median()
              for f in ("stt_transcription", "llm_ttft", "tts_http_request")}
    if all(pd.notna(v) for v in catena.values()):
        totale = sum(catena.values())
        pezzi = "  +  ".join(f"{num(v, 2)} s" for v in catena.values())
        stampa(f"      {pezzi}  =  {num(totale, 2)} s")

    stampa()
    stampa("   quanto pesa ciascuna fase sul totale delle attese misurate")
    totale = dentro.secondi.sum()
    for fase, gruppo in dentro.groupby("fase").secondi:
        nome = FASI.get(fase, (fase, ""))[0]
        stampa(f"      {nome:44} {num(100 * gruppo.sum() / totale, 1):>6}%")

    stampa()
    stampa("   attesa complessiva misurata per sessione (somma di tutte le fasi)")
    per_sessione = dentro.groupby("partecipante").secondi.sum()
    stampa(f"      mediana {num(per_sessione.median(), 1)} s   "
           f"min {num(per_sessione.min(), 1)} s   max {num(per_sessione.max(), 1)} s")

    dentro[["partecipante", "timestamp", "npc", "turno", "fase", "secondi"]].to_csv(
        ANALISI / "latenza_sessioni.csv", index=False)
    (ANALISI / "latenza.txt").write_text("\n".join(righe), encoding="utf-8")
    print("   analisi/latenza.txt")
    print("   analisi/latenza_sessioni.csv")


if __name__ == "__main__":
    main()
