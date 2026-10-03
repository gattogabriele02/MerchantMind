"""Porta i fogli dati su un altro computer e li riporta indietro.

    python scripts/moduli_trasferimento.py esporta
    python scripts/moduli_trasferimento.py importa <cartella>

Sposta SOLO i file dati_P##.xlsx: poche decine di KB in tutto. Il resto della
cartella sessioni/ (log, conversazioni, stati) resta dov'e', sia perche' pesa
sia perche' contiene il parlato trascritto dei partecipanti, che il consenso
impegna a conservare in forma anonima e in locale.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from openpyxl import load_workbook

RADICE = Path(__file__).resolve().parent.parent
SESSIONI = RADICE / "sessioni"
VALIGIA = RADICE / "moduli_da_compilare"

CODICE = re.compile(r"dati_(P\d{2})\.xlsx$", re.IGNORECASE)


def campi_compilati(percorso: Path) -> tuple[int, int]:
    """Quante caselle sono piene, su quante attese."""
    wb = load_workbook(percorso, data_only=True)
    pieni = totali = 0
    for nome, righe in (("1 Sessione", range(5, 17)),
                        ("3 Finale", list(range(5, 15)) + list(range(17, 31)))):
        ws = wb[nome]
        for r in righe:
            if ws.cell(row=r, column=4).value in (None, "note"):
                continue
            totali += 1
            if ws.cell(row=r, column=2).value not in (None, ""):
                pieni += 1
    ws = wb["2 Questionari"]
    for r in range(5, 22):
        if not str(ws.cell(row=r, column=1).value or "").startswith("i"):
            continue
        for c in range(3, 7):
            totali += 1
            if ws.cell(row=r, column=c).value not in (None, ""):
                pieni += 1
    return pieni, totali


def esporta():
    VALIGIA.mkdir(exist_ok=True)
    n = 0
    print(f"{'file':<18} {'compilato':>12}")
    for cartella in sorted(SESSIONI.glob("P*")):
        for f in cartella.glob("dati/dati_*.xlsx"):
            shutil.copy2(f, VALIGIA / f.name)
            pieni, totali = campi_compilati(f)
            stato = "COMPLETO" if pieni == totali else f"{pieni}/{totali}"
            print(f"{f.name:<18} {stato:>12}")
            n += 1
    print(f"\n{n} fogli copiati in  {VALIGIA.name}\\")
    print("Porta quella cartella sul portatile, compila, e riportala indietro.")


def importa(sorgente: Path):
    if not sorgente.is_dir():
        sys.exit(f"non e' una cartella: {sorgente}")
    aggiornati = saltati = 0
    print(f"{'file':<18} {'prima':>10} {'dopo':>10}   esito")
    for f in sorted(sorgente.glob("dati_*.xlsx")):
        trovato = CODICE.search(f.name)
        if not trovato:
            print(f"{f.name:<18} nome non riconosciuto, salto")
            continue
        codice = trovato.group(1).upper()
        destinazione = SESSIONI / codice / "dati" / f"dati_{codice}.xlsx"
        if not destinazione.parent.exists():
            print(f"{f.name:<18} nessuna sessione {codice}, salto")
            continue

        nuovi, totali = campi_compilati(f)
        vecchi = campi_compilati(destinazione)[0] if destinazione.exists() else 0

        # Non si sovrascrive mai un foglio piu' completo di quello in arrivo:
        # e' l'unico modo di perdere dati inseriti a mano.
        if destinazione.exists() and nuovi < vecchi:
            print(f"{f.name:<18} {vecchi:>10} {nuovi:>10}   SALTATO (qui e' piu' completo)")
            saltati += 1
            continue
        shutil.copy2(f, destinazione)
        print(f"{f.name:<18} {vecchi:>10} {nuovi:>10}   aggiornato" +
              ("  COMPLETO" if nuovi == totali else ""))
        aggiornati += 1
    print(f"\n{aggiornati} aggiornati, {saltati} saltati.")
    print(r"Adesso:  MantellaEnvScriptspython.exe scriptsnalisi.py")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("esporta", "importa"):
        sys.exit(__doc__)
    if sys.argv[1] == "esporta":
        esporta()
    else:
        if len(sys.argv) < 3:
            sys.exit("uso: python scripts/moduli_trasferimento.py importa <cartella>")
        importa(Path(sys.argv[2]))
