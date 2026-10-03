"""Prepara il controllo umano delle anomalie sulle battute generate dal mercante.

    MantellaEnv\\Scripts\\python.exe scripts\\verifica_anomalie.py

Il rilevatore automatico del sistema ha segnalato zero anomalie su 227 battute. H3
poggia interamente su quel numero, e il rilevatore non e' mai stato confrontato con un
giudizio umano: questo script prepara il confronto.

Che cosa e' una battuta del mercante: una riga di `negotiation_turns_log.csv` con
`npc_line` valorizzato, cioe' il testo che il modello linguistico ha prodotto e che il
giocatore ha sentito. NON sono le frasi dette dai partecipanti: quelle stanno nella
colonna `player_utterance` e non sono oggetto di questo controllo.

Le quattro categorie di anomalia (le stesse del rilevatore automatico):
  1. ragionamento trapelato   il modello espone il proprio ragionamento interno
  2. rottura di personaggio   il modello si presenta come assistente artificiale
  3. cifra non ammessa        la battuta contiene un prezzo che le regole non hanno prodotto
  4. battuta vuota            nessun testo

La categoria 3 e' l'unica verificabile in automatico, e lo script la pre-filtra. Una
cifra e' ammessa se e' il prezzo corrente del mercante (anche arrotondato: il modello
dice 67 per 66,51), oppure una cifra che il giocatore ha appena nominato, oppure un
numero che non e' un prezzo. Le prime due categorie e la quarta vanno lette a occhio:
lo script estrae un campione casuale per quello.

Produce `analisi/anomalie_da_controllare.txt`.
"""
from __future__ import annotations

import glob
import os
import random
import re
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parent.parent
USCITA = RADICE / "analisi" / "anomalie_da_controllare.txt"
CAMPIONE = 40          # battute pulite da rileggere per le categorie 1, 2 e 4
SEME = 20260830        # campione riproducibile

NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def numeri(testo: str) -> list[float]:
    fuori = []
    for m in NUMERO.finditer(str(testo)):
        try:
            fuori.append(float(m.group().replace(",", ".")))
        except ValueError:
            pass
    return fuori


def ammesso(n: float, consentiti: list[float]) -> bool:
    """Un numero e' ammesso se coincide con un prezzo consentito, anche arrotondato."""
    for c in consentiti:
        if c is None:
            continue
        if abs(n - c) < 0.01 or abs(n - round(c)) < 0.01:
            return True
    return False


def main() -> None:
    percorsi = sorted(glob.glob(str(RADICE / "sessioni" / "P*" / "logs" /
                                    "negotiation_turns_log.csv")))
    if not percorsi:
        raise SystemExit("nessun registro di trattativa trovato in sessioni/")

    battute, vuote, sospette = [], [], []

    for p in percorsi:
        codice = Path(p).parts[-3]
        d = pd.read_csv(p)
        for npc_id, tratt in d.groupby("npc_id"):
            tratt = tratt.sort_values("turn")
            # Tutti i prezzi nominati nella trattativa: quelli del mercante e quelli
            # offerti dal giocatore. Il mercante puo' legittimamente citarli entrambi.
            prezzi = [v for v in tratt.get("npc_price", []) if pd.notna(v)]
            offerte = [v for v in tratt.get("offered_price", []) if pd.notna(v)]
            for _, r in tratt.iterrows():
                if pd.isna(r.get("npc_line")):
                    continue
                testo = str(r["npc_line"]).strip()
                voce = dict(partecipante=codice, npc=npc_id, turno=int(r["turn"]),
                            prezzo=r.get("npc_price"), testo=testo)
                if not testo:
                    vuote.append(voce)
                    continue
                battute.append(voce)
                consentiti = list(prezzi) + list(offerte)
                non_spiegati = [n for n in numeri(testo)
                                if not ammesso(n, consentiti)]
                if non_spiegati:
                    voce["numeri"] = non_spiegati
                    sospette.append(voce)

    random.seed(SEME)
    pulite = [b for b in battute if b not in sospette]
    campione = random.sample(pulite, min(CAMPIONE, len(pulite)))

    righe = [
        "CONTROLLO UMANO DELLE ANOMALIE",
        "",
        f"battute generate dal mercante: {len(battute)}",
        f"battute vuote: {len(vuote)}",
        f"battute con almeno una cifra non riconducibile ai prezzi della trattativa: "
        f"{len(sospette)}",
        "",
        "Una cifra e' considerata ammessa se coincide con un prezzo del mercante in",
        "quella trattativa (anche arrotondato) o con una cifra offerta dal giocatore.",
        "",
        "=" * 78,
        "PARTE 1 - da controllare una per una: cifre non spiegate",
        "=" * 78,
        "",
    ]
    if not sospette:
        righe.append("   Nessuna. Sulla categoria 'cifra non ammessa' il rilevatore")
        righe.append("   automatico e il controllo indipendente coincidono.")
    for v in sospette:
        righe.append(f"[{v['partecipante']} {v['npc']} turno {v['turno']}] "
                     f"prezzo ammesso: {v['prezzo']}   cifre non spiegate: "
                     f"{v.get('numeri')}")
        righe.append(f"   {v['testo']}")
        righe.append("")

    righe += [
        "=" * 78,
        f"PARTE 2 - campione casuale di {len(campione)} battute, da rileggere",
        "=" * 78,
        "",
        "Per ciascuna, chiedersi soltanto:",
        "  a) espone il ragionamento interno del modello?",
        "  b) si presenta come assistente artificiale, o esce dal personaggio?",
        "  c) e' vuota o priva di senso?",
        "Segnare quante volte la risposta e' si'. Se e' zero, il rilevatore automatico",
        "e il giudizio umano concordano, ed e' il dato da riportare.",
        "",
    ]
    for i, v in enumerate(campione, start=1):
        righe.append(f"{i:2d}. [{v['partecipante']} {v['npc']} t{v['turno']}] {v['testo']}")
        righe.append("")

    USCITA.parent.mkdir(parents=True, exist_ok=True)
    USCITA.write_text("\n".join(righe), encoding="utf-8")
    print(f"battute del mercante: {len(battute)}   vuote: {len(vuote)}   "
          f"con cifre non spiegate: {len(sospette)}")
    print(f"scritto {USCITA.relative_to(RADICE).as_posix()} "
          f"({len(campione)} battute da rileggere)")


if __name__ == "__main__":
    main()
