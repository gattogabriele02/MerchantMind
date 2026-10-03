"""Analisi per sottogruppo e spoglio delle risposte aperte.

    python scripts/analisi_sottogruppi.py

Estende test_statistici.py con quello che il piano non prevedeva ma che il capitolo
dei risultati richiede: se le differenze fra condizioni reggono anche dentro i
sottogruppi del campione, e che cosa dicono le 215 risposte a testo libero.

Scrive:
  analisi/sottogruppi.txt   confronti fra sottogruppi, item per item, spoglio lessicale
  analisi/aperte_testo.txt  tutte le risposte aperte, raggruppate per domanda

Le divisioni in sottogruppi sono dicotomie, non i tre livelli originali: con 27
partecipanti i tre livelli dell'esperienza con Skyrim (18/5/4) non reggono nessun
confronto. Il piano di analisi fissato prima della raccolta prevedeva pesi per
esperienza, non test separati: quanto segue e' esplorativo e va letto come tale.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "scripts"))

from test_statistici import ORDINE, holm, num, wilcoxon_appaiato  # noqa: E402

ANALISI = RADICE / "analisi"

righe: list[str] = []


def stampa(testo: str = "") -> None:
    righe.append(testo)


def titolo(testo: str) -> None:
    stampa()
    stampa("=" * 78)
    stampa(testo)
    stampa("=" * 78)


def sezione(testo: str) -> None:
    stampa()
    stampa(f"--- {testo} " + "-" * max(0, 74 - len(testo)))


def formatta_p(p: float) -> str:
    return "< 0,001" if p < 0.001 else f"= {num(p, 3)}"


# ------------------------------------------------------------------ sottogruppi

# Ogni dicotomia: nome, colonna della scheda, valori del primo gruppo, etichette.
DICOTOMIE = [
    ("esperienza con Skyrim", "esperienza_skyrim", {"mai"},
     "mai giocato", "ha giocato"),
    ("conoscenza del commercio di Skyrim", "conosce_commercio", {"no"},
     "non lo conosce", "lo conosce o ne ha sentito"),
    ("altri giochi di ruolo", "altri_gdr", {"no"},
     "nessuno", "qualcuno o molti"),
    ("uso di assistenti vocali", "assistenti_vocali", {"mai", "raramente"},
     "mai o raramente", "ogni tanto o spesso"),
    ("genere", "genere", {"uomo"}, "uomini", "donne"),
]


def mann_whitney(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """U di Mann-Whitney fra due gruppi indipendenti, con r biseriale per ranghi."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan"), float("nan")
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    r = 1.0 - 2.0 * u / (len(a) * len(b))
    return u, p, abs(r)


def contrasti(oss: pd.DataFrame, colonna: str) -> pd.DataFrame:
    """Per ogni partecipante, la differenza di ogni condizione rispetto a N."""
    quadro = oss.pivot(index="partecipante", columns="condizione", values=colonna)
    return pd.DataFrame({c: quadro[c] - quadro["N"] for c in ORDINE if c != "N"})


def descrittiva_gruppi(oss: pd.DataFrame, part: pd.DataFrame, colonna: str,
                       colonna_gruppo: str, primo: set[str],
                       etichette: tuple[str, str], condizioni: list[str]) -> None:
    """Mediane per condizione, dentro ciascun gruppo."""
    gruppo = part.set_index("partecipante")[colonna_gruppo].apply(
        lambda v: etichette[0] if v in primo else etichette[1])
    dati = oss.copy()
    dati["gruppo"] = dati.partecipante.map(gruppo)
    for nome in etichette:
        sotto = dati[dati.gruppo == nome]
        n = sotto.partecipante.nunique()
        valori = "   ".join(
            f"{c}={num(sotto.loc[sotto.condizione == c, colonna].median())}"
            for c in condizioni)
        stampa(f"   {nome:32} n={n:2}   {valori}")


def blocco_sottogruppi(oss: pd.DataFrame, part: pd.DataFrame) -> None:
    titolo("SOTTOGRUPPI DEL CAMPIONE")
    stampa()
    stampa("Tutti i confronti fra sottogruppi sono ESPLORATIVI: il piano prevedeva")
    stampa("pesi per esperienza, non test separati, e i gruppi sono piccoli.")

    for nome, colonna, primo, eti_a, eti_b in DICOTOMIE:
        etichette = (eti_a, eti_b)
        appartiene = part.set_index("partecipante")[colonna].apply(lambda v: v in primo)
        n_a, n_b = int(appartiene.sum()), int((~appartiene).sum())
        sezione(f"{nome}: {eti_a} (n={n_a}) contro {eti_b} (n={n_b})")

        stampa("  prezzo pattuito, mediana per condizione")
        descrittiva_gruppi(oss, part, "prezzo_pattuito", colonna, primo, etichette,
                           ORDINE)
        stampa("  memoria percepita, mediana per condizione")
        descrittiva_gruppi(oss, part, "memoria_percepita", colonna, primo, etichette,
                           ORDINE)
        stampa("  credibilita complessiva, mediana per condizione")
        descrittiva_gruppi(oss, part, "credibilita", colonna, primo, etichette, ORDINE)

        # Gli effetti della memoria, misurati come differenza rispetto a N dentro
        # ciascun partecipante: e' la quantita' che i due gruppi possono avere diversa.
        stampa()
        stampa("  effetto della memoria sul prezzo (differenza rispetto a N, per persona)")
        for misura, etichetta in (("prezzo_pattuito", "prezzo"),
                                  ("memoria_percepita", "memoria percepita")):
            diff = contrasti(oss, misura)
            for cond in ("A", "D"):
                serie = diff[cond]
                a = serie[appartiene.reindex(serie.index).fillna(False)].to_numpy()
                b = serie[~appartiene.reindex(serie.index).fillna(False)].to_numpy()
                u, p, r = mann_whitney(a, b)
                a_v, b_v = a[~np.isnan(a)], b[~np.isnan(b)]
                stampa(f"   {etichetta:18} {cond}−N   {eti_a}: mediana "
                       f"{num(np.median(a_v)) if len(a_v) else 'n.d.'}   "
                       f"{eti_b}: mediana {num(np.median(b_v)) if len(b_v) else 'n.d.'}"
                       f"   U={num(u, 1)}, p {formatta_p(p)}, r={num(r, 3)}")

        # Il confronto entro soggetti, rifatto dentro ciascun gruppo.
        stampa()
        stampa("  N contro A e N contro D sul prezzo, dentro ciascun gruppo")
        for nome_gruppo, maschera in ((eti_a, appartiene), (eti_b, ~appartiene)):
            codici = maschera[maschera].index
            quadro = (oss[oss.partecipante.isin(codici)]
                      .pivot(index="partecipante", columns="condizione",
                             values="prezzo_pattuito"))
            grezzi = {}
            for cond in ("A", "D"):
                coppie = quadro[["N", cond]].dropna()
                if len(coppie) < 5:
                    continue
                _, p, r, n_eff = wilcoxon_appaiato(coppie[cond].to_numpy(),
                                                   coppie["N"].to_numpy())
                grezzi[cond] = (p, r, n_eff)
            if not grezzi:
                stampa(f"   {nome_gruppo:32} casi insufficienti")
                continue
            corretti = holm({c: v[0] for c, v in grezzi.items()})
            for cond, (p, r, n_eff) in grezzi.items():
                p_c, sig = corretti[cond]
                stampa(f"   {nome_gruppo:32} N vs {cond}: p {formatta_p(p)} "
                       f"(Holm {formatta_p(p_c)}){'  *' if sig else '   '} "
                       f" r={num(r, 3)}  n={n_eff}")

        # Valutazione della meccanica, un valore per partecipante.
        stampa()
        stampa("  valutazione della meccanica (un valore per persona, scala 1-7)")
        for misura in ("valore_soggettivo", "coinvolgimento", "preferenza_meccanica",
                       "attrito_latenza", "attrito_riconoscimento"):
            serie = part.set_index("partecipante")[misura]
            a = serie[appartiene].to_numpy()
            b = serie[~appartiene].to_numpy()
            u, p, r = mann_whitney(a, b)
            stampa(f"   {misura:24} {eti_a}: {num(np.median(a), 2)}   "
                   f"{eti_b}: {num(np.median(b), 2)}   "
                   f"U={num(u, 1)}, p {formatta_p(p)}, r={num(r, 3)}")


def blocco_gradiente(part: pd.DataFrame, oss: pd.DataFrame) -> None:
    """L'esperienza come variabile ordinale a tre livelli, non dicotomizzata."""
    titolo("ESPERIENZA CON SKYRIM COME GRADIENTE (tre livelli)")
    livelli = {"mai": 0, "qualche_ora": 1, "molte_ore": 2}
    esperienza = part.set_index("partecipante").esperienza_skyrim.map(livelli)

    sezione("descrittive per livello")
    for etichetta, codice in livelli.items():
        codici = esperienza[esperienza == codice].index
        sotto = oss[oss.partecipante.isin(codici)]
        prezzi = "   ".join(
            f"{c}={num(sotto.loc[sotto.condizione == c, 'prezzo_pattuito'].median())}"
            for c in ORDINE)
        stampa(f"   {etichetta:14} n={len(codici):2}   prezzo: {prezzi}")
    for etichetta, codice in livelli.items():
        codici = esperienza[esperienza == codice].index
        sotto = oss[oss.partecipante.isin(codici)]
        mem = "   ".join(
            f"{c}={num(sotto.loc[sotto.condizione == c, 'memoria_percepita'].median())}"
            for c in ORDINE)
        stampa(f"   {etichetta:14} n={len(codici):2}   memoria percepita: {mem}")

    sezione("correlazione fra esperienza e valutazione (Spearman)")
    for misura in ("valore_soggettivo", "coinvolgimento", "preferenza_meccanica",
                   "attrito_latenza", "attrito_riconoscimento", "durata_minuti"):
        serie = part.set_index("partecipante")[misura]
        comuni = esperienza.dropna().index.intersection(serie.dropna().index)
        rho, p = stats.spearmanr(esperienza[comuni], serie[comuni])
        stampa(f"   esperienza × {misura:24} rho = {num(rho, 3)}, p {formatta_p(p)}")

    sezione("il prezzo del baratto vanilla, che dipende dall'Eloquenza")
    prezzo_v = part.set_index("partecipante").prezzo_vanilla
    stampa(f"   valori distinti: {sorted(prezzo_v.dropna().unique())}")


def page_l(dati: np.ndarray) -> tuple[float, float, float]:
    """L di Page: test di tendenza per misure ripetute, ordine previsto in anticipo.

    Le colonne di `dati` devono essere gia' nell'ordine crescente ipotizzato. E' il
    test che il piano di analisi prevede per H2, che formula una previsione ordinata
    e non un generico «le condizioni differiscono». Approssimazione normale.
    """
    n, k = dati.shape
    ranghi = np.apply_along_axis(stats.rankdata, 1, dati)
    somme = ranghi.sum(axis=0)
    ell = float(np.sum(np.arange(1, k + 1) * somme))
    atteso = n * k * (k + 1) ** 2 / 4.0
    varianza = n * k ** 2 * (k + 1) * (k ** 2 - 1) / 144.0
    z = (ell - atteso) / np.sqrt(varianza)
    return ell, z, float(stats.norm.sf(z))


def blocco_tendenza(oss: pd.DataFrame) -> None:
    """H2 prevede un ordinamento, non una differenza qualsiasi: qui si verifica."""
    titolo("TEST DI TENDENZA SULL'ORDINAMENTO PREVISTO DA H2")
    stampa()
    stampa("H2 prevede A < N < D sul prezzo pattuito. L'ordinamento e' fissato prima")
    stampa("della raccolta, quindi il test appropriato e' di tendenza e a una coda.")
    for colonna, ordine, etichetta in (
            ("prezzo_pattuito", ["A", "N", "D"], "prezzo pattuito"),
            ("round", ["A", "N", "D"], "round di trattativa")):
        quadro = oss.pivot(index="partecipante", columns="condizione",
                           values=colonna)[ordine].dropna()
        ell, z, p = page_l(quadro.to_numpy(dtype=float))
        stampa(f"   {etichetta:22} ordine {' < '.join(ordine)}   n={len(quadro)}   "
               f"L = {num(ell, 1)}   z = {num(z, 2)}   p (una coda) {formatta_p(p)}")


def blocco_trattativa() -> None:
    """Durata e numero di battute di ogni trattativa, dai turni registrati.

    Il piano di analisi prevede la durata fra le misure di D1, ma analisi.py non la
    ricava: si ottiene qui dagli istanti del primo e dell'ultimo turno.
    """
    titolo("DINAMICA DELLA TRATTATIVA: DURATA E BATTUTE")
    npc_condizione = {"arcadia": "N", "belethor": "A", "lucan_valerius": "D"}
    voci = []
    for percorso in sorted(RADICE.glob("sessioni/P*/logs/negotiation_turns_log.csv")):
        codice = percorso.parents[1].name
        turni = pd.read_csv(percorso)
        turni["istante"] = pd.to_datetime(turni.timestamp)
        for npc, gruppo in turni.groupby("npc_id"):
            voci.append({
                "partecipante": codice,
                "condizione": npc_condizione[npc],
                "durata": (gruppo.istante.max() - gruppo.istante.min()).total_seconds(),
                "battute": len(gruppo),
                "battute_npc": int((gruppo.role != "player").sum()),
            })
    quadro = pd.DataFrame(voci)

    sezione("durata della trattativa, in secondi")
    for cond in ("N", "A", "D"):
        sotto = quadro[quadro.condizione == cond].durata
        stampa(f"   {cond}   n={len(sotto)}   mediana {num(sotto.median(), 1)}   "
               f"media {num(sotto.mean(), 1)}   min {num(sotto.min(), 0)}   "
               f"max {num(sotto.max(), 0)}")
    tavola = quadro.pivot(index="partecipante", columns="condizione", values="durata")
    chi2, p = stats.friedmanchisquare(*[tavola[c] for c in ("N", "A", "D")])
    n, k = tavola.shape[0], 3
    stampa(f"   Friedman: chi2(2) = {num(chi2)}, p {formatta_p(p)}, "
           f"W di Kendall = {num(chi2 / (n * (k - 1)), 3)}")
    grezzi, effetti = {}, {}
    for cond in ("A", "D"):
        _, p_coppia, r, n_eff = wilcoxon_appaiato(tavola[cond].to_numpy(),
                                                  tavola["N"].to_numpy())
        grezzi[cond], effetti[cond] = p_coppia, (r, n_eff)
    corretti = holm(grezzi)
    for cond in ("A", "D"):
        r, n_eff = effetti[cond]
        p_c, sig = corretti[cond]
        stampa(f"   N vs {cond}: p {formatta_p(grezzi[cond])} (Holm {formatta_p(p_c)})"
               f"{'  *' if sig else '   '}  r = {num(r, 3)}  n={n_eff}")

    sezione("battute scambiate")
    stampa(f"   turni registrati in totale: {int(quadro.battute.sum())}   "
           f"di cui del mercante: {int(quadro.battute_npc.sum())}")
    for cond in ("N", "A", "D"):
        sotto = quadro[quadro.condizione == cond]
        stampa(f"   {cond}   battute totali {int(sotto.battute.sum()):3}   "
               f"mediana per trattativa {num(sotto.battute.median(), 0)}")


def blocco_item(oss: pd.DataFrame, part: pd.DataFrame, item: pd.DataFrame) -> None:
    """Mediana di ogni singolo item, per condizione: il dettaglio dei questionari."""
    titolo("ITEM PER ITEM")

    sezione("questionario per mercante, 17 item, mediana per condizione")
    tabella = item.pivot_table(index="item", columns="condizione", values="valore",
                               aggfunc="median")[ORDINE]
    for nome, riga in tabella.iterrows():
        valori = "   ".join(f"{c}={num(riga[c], 2)}" for c in ORDINE)
        stampa(f"   {nome}   {valori}")

    sezione("questionario finale parte B, 14 item, mediana e media")
    for j in range(1, 15):
        colonna = f"b{j:02d}"
        if colonna not in part.columns:
            continue
        stampa(f"   {colonna}   mediana={num(part[colonna].median(), 2)}   "
               f"media={num(part[colonna].mean(), 2)}   "
               f"min={num(part[colonna].min(), 0)}  max={num(part[colonna].max(), 0)}")

    sezione("scelte forzate del questionario finale")
    for colonna in ("a1_differenze", "a4_ostile", "a4_amichevole", "a5_ricordava",
                    "a6_coinvolgente", "a7_attribuzione"):
        if colonna in part.columns:
            conteggi = part[colonna].value_counts().to_dict()
            stampa(f"   {colonna:20} {conteggi}")


# ------------------------------------------------------------- risposte aperte

TEMI = {
    "memoria": r"ricord|memoria|si ricord|sapeva chi|mi conosc|conosceva|rammenta|"
               r"passato|storia|rancor|riconosc",
    "prezzo": r"prezz|scont|caro|costos|economic|oro|contratt|tratt|affare|"
              r"mercanteggi|abbass|alzat",
    "tono": r"gentil|scortes|ostil|freddo|fredda|simpatic|antipatic|arrabbiat|"
            r"cordial|brusc|sgarbat|scontros|amichevol|villan|nervos|irritat",
    "tecnico": r"capiva|capito male|ripeter|microfono|lento|lenta|attesa|attend|"
               r"bug|inglese|caric|risposta lenta|ritardo",
}


def normalizza(testo: str) -> str:
    testo = unicodedata.normalize("NFKD", str(testo).lower())
    return "".join(c for c in testo if not unicodedata.combining(c))


def blocco_aperte(aperte: pd.DataFrame, part: pd.DataFrame) -> None:
    titolo("RISPOSTE APERTE")
    stampa()
    stampa("Spoglio LESSICALE AUTOMATICO, non la codifica a due codificatori")
    stampa("prevista dal piano: conta la presenza di famiglie di parole, e va")
    stampa("riportato come tale. Serve a dire quante persone nominano un tema")
    stampa("SENZA che nessun item glielo abbia suggerito.")

    aperte = aperte[aperte.domanda != "Note del conduttore"].copy()
    aperte["testo"] = aperte.risposta.map(normalizza)
    stampa()
    stampa(f"   risposte totali: {len(aperte)}   partecipanti: {aperte.partecipante.nunique()}")

    # Le impressioni sui mercanti portano in coda la sigla della condizione.
    impressioni = aperte[aperte.domanda.str.contains("impressione")].copy()
    impressioni["condizione"] = impressioni.domanda.str.extract(r"\(([VNAD])\)")

    sezione("impressione sul mercante: temi nominati spontaneamente, per condizione")
    stampa(f"   {'tema':10} " + "   ".join(f"{c:>10}" for c in ORDINE))
    for tema, schema in TEMI.items():
        conteggi = []
        for cond in ORDINE:
            sotto = impressioni[impressioni.condizione == cond]
            k = int(sotto.testo.str.contains(schema, regex=True).sum())
            conteggi.append(f"{k:2}/{len(sotto):2} ({100 * k / len(sotto):4.1f}%)")
        stampa(f"   {tema:10} " + "   ".join(f"{c:>10}" for c in conteggi))

    sezione("domande aperte finali: temi nominati")
    for domanda in sorted(aperte.domanda.unique()):
        if "impressione" in domanda:
            continue
        sotto = aperte[aperte.domanda == domanda]
        parti = []
        for tema, schema in TEMI.items():
            k = int(sotto.testo.str.contains(schema, regex=True).sum())
            parti.append(f"{tema} {k}/{len(sotto)}")
        stampa(f"   {domanda}")
        stampa(f"      " + "   ".join(parti))

    sezione("lunghezza delle risposte")
    lunghezze = aperte.risposta.astype(str).str.split().str.len()
    stampa(f"   parole per risposta: mediana {int(lunghezze.median())}, "
           f"min {int(lunghezze.min())}, max {int(lunghezze.max())}")


def scrivi_testi(aperte: pd.DataFrame) -> None:
    """Tutte le risposte aperte in chiaro, raggruppate: servono per le citazioni."""
    fuori: list[str] = ["RISPOSTE APERTE, TESTO INTEGRALE",
                        "(fonte delle citazioni testuali)", ""]
    impressioni = aperte[aperte.domanda.str.contains("impressione")].copy()
    impressioni["condizione"] = impressioni.domanda.str.extract(r"\(([VNAD])\)")
    for cond in ORDINE:
        sotto = impressioni[impressioni.condizione == cond].sort_values("partecipante")
        fuori += ["", "=" * 78,
                  f"IMPRESSIONE SUL MERCANTE — condizione {cond}  ({len(sotto)} risposte)",
                  "=" * 78]
        fuori += [f"  [{r.partecipante}] {r.risposta}" for r in sotto.itertuples()]
    for domanda in sorted(aperte.domanda.unique()):
        if "impressione" in domanda:
            continue
        sotto = aperte[aperte.domanda == domanda].sort_values("partecipante")
        fuori += ["", "=" * 78, f"{domanda}  ({len(sotto)} risposte)", "=" * 78]
        fuori += [f"  [{r.partecipante}] {r.risposta}" for r in sotto.itertuples()]
    (ANALISI / "aperte_testo.txt").write_text("\n".join(fuori), encoding="utf-8")


def main() -> None:
    oss = pd.read_csv(ANALISI / "osservazioni.csv")
    part = pd.read_csv(ANALISI / "partecipanti.csv")
    item = pd.read_csv(ANALISI / "item.csv")
    aperte = pd.read_csv(ANALISI / "aperte.csv")

    stampa("ANALISI PER SOTTOGRUPPO E RISPOSTE APERTE — studio MerchantMind")
    stampa(f"27 sessioni, {len(oss)} osservazioni, {len(part)} questionari completi")

    blocco_sottogruppi(oss, part)
    blocco_gradiente(part, oss)
    blocco_tendenza(oss)
    blocco_trattativa()
    blocco_item(oss, part, item)
    blocco_aperte(aperte, part)
    scrivi_testi(aperte[aperte.domanda != "Note del conduttore"])

    (ANALISI / "sottogruppi.txt").write_text("\n".join(righe), encoding="utf-8")
    print("   analisi/sottogruppi.txt")
    print("   analisi/aperte_testo.txt")


if __name__ == "__main__":
    main()
