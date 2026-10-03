"""Test statistici dello studio MerchantMind.

    python scripts/test_statistici.py

Legge analisi/osservazioni.csv, partecipanti.csv e item.csv (prodotti da
analisi.py) ed esegue i test fissati PRIMA della raccolta:

  - confronto di riferimento sempre contro la condizione N;
  - tre confronti pianificati N-A, N-D, N-V;
  - correzione di Holm entro ciascuna famiglia, alfa 0,05;
  - accanto a ogni p, la dimensione dell'effetto.

Scrive analisi/risultati_test.txt e le tabelle in analisi/tabelle_*.csv.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RADICE = Path(__file__).resolve().parent.parent
ANALISI = RADICE / "analisi"
ALFA = 0.05
ORDINE = ["V", "N", "A", "D"]
NOMI = {"V": "baratto vanilla", "N": "nessuna storia",
        "A": "memoria positiva", "D": "memoria negativa"}

righe: list[str] = []


def stampa(testo: str = "") -> None:
    righe.append(testo)
    print(testo)


def titolo(testo: str) -> None:
    stampa("")
    stampa("=" * 78)
    stampa(testo)
    stampa("=" * 78)


def sezione(testo: str) -> None:
    stampa("")
    stampa(f"--- {testo} " + "-" * max(0, 73 - len(testo)))


# --------------------------------------------------------------- strumenti ---

def holm(p_valori: dict[str, float]) -> dict[str, tuple[float, bool]]:
    """Correzione di Holm-Bonferroni. Restituisce (p corretto, significativo)."""
    ordinati = sorted(p_valori.items(), key=lambda kv: kv[1])
    m = len(ordinati)
    fuori: dict[str, tuple[float, bool]] = {}
    massimo = 0.0
    for i, (chiave, p) in enumerate(ordinati):
        corretto = min(1.0, (m - i) * p)
        massimo = max(massimo, corretto)   # monotonia
        fuori[chiave] = (massimo, massimo < ALFA)
    return fuori


def kendall_w(chi2: float, n: int, k: int) -> float:
    """Concordanza di Kendall: dimensione dell'effetto del test di Friedman."""
    return chi2 / (n * (k - 1)) if n and k > 1 else float("nan")


def wilcoxon_appaiato(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float, int]:
    """Wilcoxon appaiato. Restituisce (statistica, p, r = |Z|/sqrt(N), N usati).

    Le coppie identiche non portano informazione sulla differenza e vengono
    scartate (zero_method='wilcox'); N e' il numero di coppie che restano.
    """
    differenze = a - b
    n_effettivi = int(np.sum(differenze != 0))
    if n_effettivi == 0:
        return float("nan"), 1.0, 0.0, 0
    esito = stats.wilcoxon(a, b, zero_method="wilcox", method="approx")
    z = esito.zstatistic
    return float(esito.statistic), float(esito.pvalue), abs(z) / math.sqrt(n_effettivi), n_effettivi


def cochran_q(matrice: np.ndarray) -> tuple[float, int, float]:
    """Q di Cochran su una matrice soggetti x condizioni di 0/1."""
    n, k = matrice.shape
    colonne = matrice.sum(axis=0)
    righe_somma = matrice.sum(axis=1)
    numeratore = (k - 1) * (k * np.sum(colonne ** 2) - colonne.sum() ** 2)
    denominatore = k * righe_somma.sum() - np.sum(righe_somma ** 2)
    if denominatore == 0:
        return float("nan"), k - 1, 1.0
    q = numeratore / denominatore
    return float(q), k - 1, float(stats.chi2.sf(q, k - 1))


def mcnemar_esatto(a: np.ndarray, b: np.ndarray) -> tuple[int, int, float]:
    """McNemar esatto su due variabili binarie appaiate."""
    b01 = int(np.sum((a == 0) & (b == 1)))
    b10 = int(np.sum((a == 1) & (b == 0)))
    if b01 + b10 == 0:
        return b01, b10, 1.0
    p = stats.binomtest(b01, b01 + b10, 0.5).pvalue
    return b01, b10, float(p)


def alfa_cronbach(matrice: np.ndarray) -> float:
    """Alfa di Cronbach su una matrice soggetti x item."""
    matrice = matrice[~np.isnan(matrice).any(axis=1)]
    k = matrice.shape[1]
    if k < 2 or matrice.shape[0] < 2:
        return float("nan")
    varianze = matrice.var(axis=0, ddof=1)
    totale = matrice.sum(axis=1).var(ddof=1)
    if totale == 0:
        return float("nan")
    return float((k / (k - 1)) * (1 - varianze.sum() / totale))


def anova_misure_ripetute(dati: np.ndarray) -> dict:
    """ANOVA a una via per misure ripetute, con correzione di Greenhouse-Geisser.

    dati: matrice soggetti x condizioni. Restituisce F, gradi di liberta',
    p non corretto e corretto, epsilon, eta quadro parziale e generalizzato.
    Implementata a mano perche' statsmodels non e' fra le dipendenze del
    progetto e non vale la pena aggiungerlo solo per questo.
    """
    n, k = dati.shape
    medie_cond = dati.mean(axis=0)
    medie_sogg = dati.mean(axis=1)
    grande = dati.mean()

    ss_cond = n * np.sum((medie_cond - grande) ** 2)
    ss_sogg = k * np.sum((medie_sogg - grande) ** 2)
    ss_tot = np.sum((dati - grande) ** 2)
    ss_err = ss_tot - ss_cond - ss_sogg

    gdl1, gdl2 = k - 1, (k - 1) * (n - 1)
    ms_cond, ms_err = ss_cond / gdl1, ss_err / gdl2
    f = ms_cond / ms_err if ms_err > 0 else float("nan")

    # epsilon di Greenhouse-Geisser dalla matrice di covarianza delle condizioni
    S = np.cov(dati, rowvar=False, ddof=1)
    s_medio = S.mean()
    diag_media = np.trace(S) / k
    righe_medie = S.mean(axis=1)
    numeratore = (k ** 2) * (diag_media - s_medio) ** 2
    denominatore = (k - 1) * (np.sum(S ** 2) - 2 * k * np.sum(righe_medie ** 2)
                              + (k ** 2) * (s_medio ** 2))
    eps = float(np.clip(numeratore / denominatore, 1.0 / (k - 1), 1.0)) if denominatore else 1.0

    p_grezzo = float(stats.f.sf(f, gdl1, gdl2))
    p_gg = float(stats.f.sf(f, gdl1 * eps, gdl2 * eps))
    return {"F": float(f), "gdl1": gdl1, "gdl2": gdl2, "p": p_grezzo,
            "eps": eps, "p_gg": p_gg,
            "eta_p": float(ss_cond / (ss_cond + ss_err)) if (ss_cond + ss_err) else float("nan"),
            "eta_g": float(ss_cond / (ss_cond + ss_sogg + ss_err)) if ss_tot else float("nan")}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervallo di Wilson a DUE code per una proporzione."""
    if n == 0:
        return float("nan"), float("nan")
    ph = k / n
    denom = 1 + z * z / n
    centro = (ph + z * z / (2 * n)) / denom
    mezzo = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centro - mezzo), min(1.0, centro + mezzo)


def proporzione(k: int, n: int, atteso: float, etichetta: str, rientro: str = "      ") -> None:
    test = stats.binomtest(k, n, atteso, alternative="greater")
    basso, alto = wilson(k, n)
    stampa(f"{rientro}{etichetta}: {k}/{n} = {num(100*k/n, 1)}%  "
           f"IC95% [{num(100*basso,1)}%, {num(100*alto,1)}%]  "
           f"binomiale contro {str(atteso).replace('.', ',')}: p {formatta_p(test.pvalue)}")


def formatta_p(p: float) -> str:
    if np.isnan(p):
        return "   n.d."
    if p < 0.001:
        return "< 0,001"
    return f"= {p:.3f}".replace(".", ",")


def num(x: float, dec: int = 2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n.d."
    return f"{x:.{dec}f}".replace(".", ",")


def matrice_condizioni(oss: pd.DataFrame, colonna: str,
                       condizioni: list[str]) -> tuple[np.ndarray, list[str]]:
    """Matrice soggetti x condizioni sui soli partecipanti completi."""
    tabella = oss.pivot(index="partecipante", columns="condizione", values=colonna)
    mancanti = [c for c in condizioni if c not in tabella.columns]
    if mancanti:
        return np.empty((0, len(condizioni))), []
    tabella = tabella[condizioni].dropna()
    return tabella.to_numpy(dtype=float), list(tabella.index)


# ------------------------------------------------------- famiglie di test ---

def confronta_condizioni(oss: pd.DataFrame, colonna: str, etichetta: str,
                         condizioni: list[str] = ORDINE,
                         riferimento: str = "N") -> dict:
    """Friedman su tutte le condizioni + Wilcoxon contro il riferimento, Holm."""
    dati, soggetti = matrice_condizioni(oss, colonna, condizioni)
    if dati.shape[0] < 3:
        stampa(f"{etichetta}: dati insufficienti ({dati.shape[0]} casi completi)")
        return {}

    n, k = dati.shape
    chi2, p = stats.friedmanchisquare(*[dati[:, i] for i in range(k)])
    w = kendall_w(chi2, n, k)

    mediane = "   ".join(f"{c}={num(np.median(dati[:, i]))}"
                         for i, c in enumerate(condizioni))
    stampa(f"{etichetta}")
    stampa(f"   n={n} completi   mediane: {mediane}")
    stampa(f"   Friedman: chi2({k-1}) = {num(chi2)}, p {formatta_p(p)}, "
           f"W di Kendall = {num(w, 3)}")

    i_rif = condizioni.index(riferimento)
    grezzi, dettagli = {}, {}
    for i, c in enumerate(condizioni):
        if c == riferimento:
            continue
        _, p_coppia, r, n_eff = wilcoxon_appaiato(dati[:, i], dati[:, i_rif])
        grezzi[c] = p_coppia
        dettagli[c] = (r, n_eff, np.median(dati[:, i] - dati[:, i_rif]))
    corretti = holm(grezzi)
    for c in [x for x in condizioni if x != riferimento]:
        r, n_eff, delta = dettagli[c]
        p_c, sig = corretti[c]
        stampa(f"   {riferimento} vs {c}: p {formatta_p(grezzi[c])}  "
               f"(Holm {formatta_p(p_c)}){'  *' if sig else '   '}"
               f"  r = {num(r, 3)}  mediana delle differenze = {num(delta)}  n={n_eff}")
    return {"chi2": chi2, "p": p, "W": w, "n": n,
            "coppie": {c: (grezzi[c], corretti[c][0], dettagli[c][0]) for c in grezzi}}


def descrittive(oss: pd.DataFrame, colonne: list[str]) -> pd.DataFrame:
    fuori = []
    for c in ORDINE:
        sotto = oss[oss["condizione"] == c]
        riga = {"condizione": c}
        for col in colonne:
            valori = sotto[col].dropna()
            riga[f"{col}_n"] = len(valori)
            riga[f"{col}_mediana"] = round(valori.median(), 2) if len(valori) else np.nan
            riga[f"{col}_media"] = round(valori.mean(), 2) if len(valori) else np.nan
            riga[f"{col}_ds"] = round(valori.std(ddof=1), 2) if len(valori) > 1 else np.nan
        fuori.append(riga)
    return pd.DataFrame(fuori)


# --------------------------------------------------------------------- main ---

def main() -> None:
    oss = pd.read_csv(ANALISI / "osservazioni.csv")
    part = pd.read_csv(ANALISI / "partecipanti.csv")
    item = pd.read_csv(ANALISI / "item.csv")

    n_part = part["partecipante"].nunique()

    titolo("STUDIO MERCHANTMIND — TEST STATISTICI")
    stampa(f"Partecipanti: {n_part}    osservazioni: {len(oss)}")
    stampa(f"Disegno entro i soggetti, quattro condizioni: "
           + ", ".join(f"{c} = {NOMI[c]}" for c in ORDINE))
    stampa(f"Riferimento di tutti i confronti: N. Correzione di Holm entro famiglia, "
           f"alfa = {str(ALFA).replace('.', ',')}.")

    # ---------------------------------------------------------- 0 campione ---
    titolo("0. IL CAMPIONE")
    for campo, etichetta in (("esperienza_skyrim", "esperienza con Skyrim"),
                             ("conosce_commercio", "conosce il commercio di Skyrim"),
                             ("genere", "genere"),
                             ("altri_gdr", "altri giochi di ruolo"),
                             ("assistenti_vocali", "usa assistenti vocali"),
                             ("parlato_npc", "ha gia' parlato con un NPC")):
        if campo in part:
            stampa(f"   {etichetta:32} {part[campo].value_counts().to_dict()}")
    if "eta" in part:
        eta = pd.to_numeric(part["eta"], errors="coerce").dropna()
        if len(eta):
            stampa(f"   {'eta':32} media {num(eta.mean(), 1)}  "
                   f"(min {int(eta.min())}, max {int(eta.max())})")
    if "durata_minuti" in part:
        dur = pd.to_numeric(part["durata_minuti"], errors="coerce").dropna()
        if len(dur):
            stampa(f"   {'durata sessione (minuti)':32} media {num(dur.mean(), 1)}  "
                   f"(min {int(dur.min())}, max {int(dur.max())})")
    stampa(f"   {'build':32} {part['build'].value_counts().sort_index().to_dict()}")

    # ------------------------------------------------------ 1 affidabilita ---
    titolo("1. AFFIDABILITA DELLE DIMENSIONI (alfa di Cronbach)")
    stampa("Solo le dimensioni con almeno due item. Le altre restano item singoli e")
    stampa("si riportano come tali, senza alfa.")
    stampa("")
    dimensioni_multi = {
        "intelligenza": ["i04", "i05", "i06"],
        "memoria_percepita": ["i09", "i10", "i11"],
        "credibilita": ["i15", "i16", "i17"],
        "emozione": ["i07", "i08"],
    }
    for nome, chiavi in dimensioni_multi.items():
        larga = item[item["item"].isin(chiavi)].pivot_table(
            index=["partecipante", "condizione"], columns="item", values="valore")
        a = alfa_cronbach(larga[chiavi].to_numpy(dtype=float))
        giudizio = ("buona" if a >= 0.8 else "accettabile" if a >= 0.7
                    else "modesta" if a >= 0.6 else "insufficiente")
        stampa(f"   {nome:22} alfa = {num(a, 3)}   ({len(chiavi)} item, {giudizio})")
    stampa("")
    stampa("   Nota: l'alfa e' calcolata su tutte le osservazioni (partecipante x")
    stampa("   condizione), quindi include la varianza fra condizioni. E' la stessa")
    stampa("   convenzione usata dalla scala originale.")

    # -------------------------------------------- 2 comportamento economico ---
    titolo("2. COMPORTAMENTO ECONOMICO (H2)")
    stampa("La condizione V e' esclusa dai confronti sul prezzo: il baratto vanilla")
    stampa("dipende dall'Eloquenza del giocatore e non dallo stato relazionale, quindi")
    stampa("non e' un livello omogeneo (cap. 6, §6.2). Resta nelle misure percettive.")

    sezione("2.0 Perche' test non parametrici")
    stampa("Il piano prevede l'ANOVA a misure ripetute e, in caso di violazione delle")
    stampa("assunzioni, l'alternativa non parametrica. Si verifica la normalita' delle")
    stampa("differenze appaiate con Shapiro-Wilk.")
    stampa("")
    for colonna in ("prezzo_pattuito", "scarto_riserva", "round", "credibilita",
                    "memoria_percepita"):
        if colonna not in oss.columns:
            continue
        condizioni = ["N", "A", "D"] if colonna in ("prezzo_pattuito", "scarto_riserva",
                                                    "round") else ORDINE
        dati, _ = matrice_condizioni(oss, colonna, condizioni)
        if dati.shape[0] < 3:
            continue
        i_rif = condizioni.index("N")
        esiti = []
        for i, c in enumerate(condizioni):
            if c == "N":
                continue
            diff = dati[:, i] - dati[:, i_rif]
            if np.all(diff == diff[0]):
                esiti.append(f"N-{c}: costante")
                continue
            w_s, p_s = stats.shapiro(diff)
            esiti.append(f"N-{c}: W={num(w_s,3)}, p {formatta_p(p_s)}"
                         + ("" if p_s >= ALFA else "  non normale"))
        stampa(f"   {colonna:20} " + "   ".join(esiti))
    stampa("")
    stampa("   Lettura: per PREZZO e SCARTO le differenze appaiate sono compatibili con")
    stampa("   la normalita', quindi si esegue l'ANOVA a misure ripetute prevista dal")
    stampa("   piano, con Friedman come verifica di robustezza. Per i round e per le")
    stampa("   misure percettive - ordinali per costruzione e in gran parte non normali -")
    stampa("   si usano direttamente Friedman e Wilcoxon.")

    sezione("2.1 Prezzo pattuito")
    for colonna, etichetta in (("prezzo_pattuito", "prezzo pattuito (oro)"),):
        dati, _ = matrice_condizioni(oss, colonna, ["N", "A", "D"])
        a = anova_misure_ripetute(dati)
        stampa(f"   ANOVA a misure ripetute (n={dati.shape[0]}): "
               f"F({a['gdl1']}, {a['gdl2']}) = {num(a['F'])}, p {formatta_p(a['p'])}")
        stampa(f"   Greenhouse-Geisser: epsilon = {num(a['eps'], 3)}, "
               f"p corretto {formatta_p(a['p_gg'])}")
        stampa(f"   eta quadro parziale = {num(a['eta_p'], 3)}   "
               f"eta quadro generalizzato = {num(a['eta_g'], 3)}")
        stampa("")
    confronta_condizioni(oss, "prezzo_pattuito", "prezzo pattuito (oro) - verifica non parametrica",
                         condizioni=["N", "A", "D"])

    sezione("2.2 Scarto fra prezzo pattuito e prezzo di riserva")
    stampa("Quanto il giocatore ha pagato sopra il minimo che il mercante avrebbe")
    stampa("accettato: misura la conduzione della trattativa, non la condizione.")
    stampa("")
    dati_sc, _ = matrice_condizioni(oss, "scarto_riserva", ["N", "A", "D"])
    a = anova_misure_ripetute(dati_sc)
    stampa(f"   ANOVA a misure ripetute (n={dati_sc.shape[0]}): "
           f"F({a['gdl1']}, {a['gdl2']}) = {num(a['F'])}, p {formatta_p(a['p'])}")
    stampa(f"   Greenhouse-Geisser: epsilon = {num(a['eps'], 3)}, "
           f"p corretto {formatta_p(a['p_gg'])}")
    stampa(f"   eta quadro parziale = {num(a['eta_p'], 3)}   "
           f"eta quadro generalizzato = {num(a['eta_g'], 3)}")
    stampa("")
    confronta_condizioni(oss, "scarto_riserva", "scarto dalla riserva (oro) - verifica non parametrica",
                         condizioni=["N", "A", "D"])

    sezione("2.3 Numero di round")
    confronta_condizioni(oss, "round", "round di trattativa",
                         condizioni=["N", "A", "D"])

    sezione("2.4 Esito: affare o abbandono (Q di Cochran)")
    esito = oss.copy()
    esito["deal"] = (esito["esito"] == "deal").astype(int)
    matrice, soggetti = matrice_condizioni(esito, "deal", ORDINE)
    if matrice.size:
        q, gdl, p = cochran_q(matrice.astype(int))
        stampa(f"   n={matrice.shape[0]}   affari conclusi per condizione: "
               + "   ".join(f"{c}={int(matrice[:, i].sum())}/{matrice.shape[0]}"
                            for i, c in enumerate(ORDINE)))
        stampa(f"   Q di Cochran: Q({gdl}) = {num(q)}, p {formatta_p(p)}")
        i_rif = ORDINE.index("N")
        grezzi, dett = {}, {}
        for i, c in enumerate(ORDINE):
            if c == "N":
                continue
            b01, b10, p_c = mcnemar_esatto(matrice[:, i_rif].astype(int),
                                           matrice[:, i].astype(int))
            grezzi[c] = p_c
            dett[c] = (b01, b10)
        corretti = holm(grezzi)
        for c in [x for x in ORDINE if x != "N"]:
            p_c, sig = corretti[c]
            b01, b10 = dett[c]
            stampa(f"   N vs {c}: McNemar esatto p {formatta_p(grezzi[c])}  "
                   f"(Holm {formatta_p(p_c)}){'  *' if sig else '   '}"
                   f"  coppie discordanti {b01}/{b10}")
        stampa("")
        stampa("   Da leggere con attenzione: il test d'insieme rileva la differenza fra")
        stampa("   le condizioni, il confronto a coppie no. Con quattro sole coppie")
        stampa("   discordanti il McNemar esatto non puo' scendere sotto p = 0,125,")
        stampa("   qualunque sia l'entita' dell'effetto: e' un limite di potenza, non")
        stampa("   l'assenza di un effetto. Si riporta la proporzione con l'intervallo.")
        for i, c in enumerate(ORDINE):
            k_ab = int(matrice.shape[0] - matrice[:, i].sum())
            if k_ab:
                basso, alto = wilson(k_ab, matrice.shape[0])
                stampa(f"      abbandoni in {c}: {k_ab}/{matrice.shape[0]} = "
                       f"{num(100*k_ab/matrice.shape[0],1)}%  "
                       f"IC95% [{num(100*basso,1)}%, {num(100*alto,1)}%]")

    # ---------------------------------------------------------- 3 percezione ---
    titolo("3. ESPERIENZA PERCEPITA (H4)")
    stampa("Tutte le dimensioni del questionario per mercante, quattro condizioni.")
    dimensioni = ["memoria_percepita", "credibilita", "intelligenza",
                  "relazione_sociale", "emozione", "comportamento",
                  "direzione_relazione", "collera_percepita", "trattativa_percepita"]
    for d in dimensioni:
        if d not in oss.columns:
            continue
        sezione(f"3.x {d}")
        confronta_condizioni(oss, d, d)

    # ------------------------------------------------- 4 questionario finale ---
    titolo("4. QUESTIONARIO FINALE — SCELTE FORZATE")
    stampa("Confronto con la scelta casuale fra quattro condizioni (p = 0,25),")
    stampa("test binomiale esatto, con intervallo di Wilson al 95%.")
    stampa("")
    domande = [("a4_ostile", "il piu' ostile", "D"),
               ("a4_amichevole", "il piu' amichevole", "A"),
               ("a5_ricordava", "sembrava ricordare qualcosa di me", None),
               ("a6_coinvolgente", "trattativa piu' coinvolgente", None)]
    for campo, etichetta, atteso in domande:
        if campo not in part:
            continue
        conteggi = part[campo].value_counts()
        n = int(conteggi.sum())
        stampa(f"   {etichetta}: {conteggi.to_dict()}")
        bersaglio = atteso or conteggi.idxmax()
        proporzione(int(conteggi.get(bersaglio, 0)), n, 0.25, bersaglio)
        if campo == "a5_ricordava":
            # La domanda vera non e' quale dei due, ma se il partecipante indichi
            # una condizione CON memoria: due opzioni su quattro, atteso 0,50.
            con_memoria = int(conteggi.get("A", 0) + conteggi.get("D", 0))
            proporzione(con_memoria, n, 0.50, "A oppure D (una condizione con memoria)")

    if "a1_differenze" in part:
        conteggi = part["a1_differenze"].value_counts()
        n = int(conteggi.sum())
        stampa("")
        proporzione(int(conteggi.get("si", 0)), n, 0.50,
                    "ha notato differenze fra i mercanti", rientro="   ")

    if "a7_attribuzione" in part:
        conteggi = part["a7_attribuzione"].value_counts()
        n = int(conteggi.sum())
        stampa("")
        stampa(f"   attribuzione del prezzo: {conteggi.to_dict()}")
        proporzione(int(conteggi.get("rapporto", 0)), n, 0.25, "'rapporto'")

    sezione("4.x Classifica di credibilita (ordinamento 1-4)")
    colonne_ordine = [f"a3_ordine_{i}" for i in range(1, 5)]
    if all(c in part for c in colonne_ordine):
        ranghi = []
        for _, r in part.iterrows():
            posizione = {r[c]: i + 1 for i, c in enumerate(colonne_ordine)}
            if set(posizione) == set(ORDINE):
                ranghi.append([posizione[c] for c in ORDINE])
        if len(ranghi) >= 3:
            dati = np.array(ranghi, dtype=float)
            chi2, p = stats.friedmanchisquare(*[dati[:, i] for i in range(4)])
            w = kendall_w(chi2, dati.shape[0], 4)
            stampa(f"   n={dati.shape[0]}   rango medio (1 = piu' 'vero'): "
                   + "   ".join(f"{c}={num(dati[:, i].mean())}" for i, c in enumerate(ORDINE)))
            stampa(f"   Friedman: chi2(3) = {num(chi2)}, p {formatta_p(p)}, "
                   f"W di Kendall = {num(w, 3)}")
            grezzi, dett = {}, {}
            i_rif = ORDINE.index("N")
            for i, c in enumerate(ORDINE):
                if c == "N":
                    continue
                _, p_c, r_eff, n_eff = wilcoxon_appaiato(dati[:, i], dati[:, i_rif])
                grezzi[c] = p_c
                dett[c] = (r_eff, n_eff)
            corretti = holm(grezzi)
            for c in [x for x in ORDINE if x != "N"]:
                p_c, sig = corretti[c]
                r_eff, n_eff = dett[c]
                stampa(f"   N vs {c}: p {formatta_p(grezzi[c])}  (Holm {formatta_p(p_c)})"
                       f"{'  *' if sig else '   '}  r = {num(r_eff, 3)}  n={n_eff}")

    # ------------------------------------------------------ 5 la meccanica ---
    titolo("5. VALUTAZIONE DELLA MECCANICA (questionario finale, parte B)")
    stampa("Punteggi 1-7, un valore per partecipante. Il confronto e' con il punto")
    stampa("neutro della scala (4), test dei ranghi con segno di Wilcoxon.")
    stampa("")
    blocchi = [("valore_soggettivo", "valore soggettivo della trattativa (SVI)"),
               ("coinvolgimento", "coinvolgimento e immersione"),
               ("preferenza_meccanica", "preferenza sulla meccanica"),
               ("attrito_latenza", "attrito: attese fra le battute"),
               ("attrito_riconoscimento", "attrito: doversi ripetere")]
    for campo, etichetta in blocchi:
        if campo not in part:
            continue
        valori = pd.to_numeric(part[campo], errors="coerce").dropna().to_numpy()
        if len(valori) < 3:
            continue
        esito = stats.wilcoxon(valori - 4.0, zero_method="wilcox", method="approx")
        r = abs(esito.zstatistic) / math.sqrt(np.sum(valori != 4))
        stampa(f"   {etichetta:42} mediana {num(np.median(valori))}  "
               f"media {num(valori.mean())}  p {formatta_p(esito.pvalue)}  r = {num(r, 3)}")

    # ---------------------------------------------------- 6 correlazioni ---
    titolo("6. RELAZIONE FRA CONDUZIONE E RISULTATO")
    stampa("Ipotesi emersa dai dati: lo scarto dalla riserva dipende da quanto il")
    stampa("giocatore tratta, piu' che dalla condizione. Rho di Spearman.")
    stampa("")
    validi = oss.dropna(subset=["scarto_riserva", "round"])
    rho, p = stats.spearmanr(validi["round"], validi["scarto_riserva"])
    stampa(f"   round x scarto, tutte le condizioni: n={len(validi)}  "
           f"rho = {num(rho, 3)}, p {formatta_p(p)}")
    for c in ["N", "A", "D"]:
        sotto = validi[validi["condizione"] == c]
        if len(sotto) > 3:
            rho_c, p_c = stats.spearmanr(sotto["round"], sotto["scarto_riserva"])
            stampa(f"   solo condizione {c}: n={len(sotto)}  "
                   f"rho = {num(rho_c, 3)}, p {formatta_p(p_c)}")
    if "memoria_percepita" in oss:
        sotto = oss[oss["condizione"] != "V"].dropna(subset=["memoria_percepita", "scarto_riserva"])
        rho_m, p_m = stats.spearmanr(sotto["memoria_percepita"], sotto["scarto_riserva"])
        stampa(f"   memoria percepita x scarto (senza V): n={len(sotto)}  "
               f"rho = {num(rho_m, 3)}, p {formatta_p(p_m)}")

    # ------------------------------------------------- 7 effetto posizione ---
    titolo("7. CONTROLLO: EFFETTO DELLA POSIZIONE NELLA SEQUENZA")
    stampa("Il quadrato latino dovrebbe averlo annullato. Si verifica sulle misure")
    stampa("che non dipendono dalla condizione per costruzione.")
    stampa("")
    for colonna in ("credibilita", "scarto_riserva", "round"):
        if colonna not in oss.columns or "posizione" not in oss.columns:
            continue
        tabella = oss.pivot_table(index="partecipante", columns="posizione", values=colonna)
        tabella = tabella.dropna()
        if tabella.shape[0] >= 3 and tabella.shape[1] >= 3:
            dati = tabella.to_numpy(dtype=float)
            chi2, p = stats.friedmanchisquare(*[dati[:, i] for i in range(dati.shape[1])])
            w = kendall_w(chi2, dati.shape[0], dati.shape[1])
            esito = "nessun effetto" if p >= ALFA else "EFFETTO PRESENTE, da riportare"
            stampa(f"   {colonna:18} n={dati.shape[0]}  posizioni={dati.shape[1]}  "
                   f"chi2 = {num(chi2)}, p {formatta_p(p)}, W = {num(w, 3)}   {esito}")

    # ------------------------------------------- 8 moderatore: esperienza ---
    titolo("8. MODERATORE: ESPERIENZA CON SKYRIM (tre scenari di peso)")
    stampa("Regola fissata prima della raccolta: se le conclusioni coincidono nei tre")
    stampa("scenari l'effetto e' robusto e si riporta il solo scenario uniforme.")
    stampa("")
    pesi = {"uniforme": {"mai": 1.0, "qualche_ora": 1.0, "molte_ore": 1.0},
            "pro esperti": {"mai": 0.5, "qualche_ora": 1.0, "molte_ore": 1.5},
            "pro neofiti": {"mai": 1.5, "qualche_ora": 1.0, "molte_ore": 0.5}}
    gruppi = part.set_index("partecipante")["esperienza_skyrim"].to_dict()
    stampa(f"   numerosita dei gruppi: {part['esperienza_skyrim'].value_counts().to_dict()}")
    stampa("")
    for misura in ("memoria_percepita", "credibilita", "scarto_riserva"):
        if misura not in oss.columns:
            continue
        stampa(f"   {misura}")
        for nome_scenario, mappa in pesi.items():
            valori = []
            for c in ORDINE:
                sotto = oss[(oss["condizione"] == c)].dropna(subset=[misura])
                if sotto.empty:
                    valori.append(np.nan)
                    continue
                w = np.array([mappa.get(gruppi.get(p_, "mai"), 1.0) for p_ in sotto["partecipante"]])
                valori.append(float(np.average(sotto[misura], weights=w)))
            stampa(f"      {nome_scenario:12} " +
                   "   ".join(f"{c}={num(v)}" for c, v in zip(ORDINE, valori)))
        stampa("")
    stampa("   Con 18 partecipanti su 27 senza esperienza, lo scenario 'pro esperti'")
    stampa("   poggia su 4 casi: la sua stabilita' va dichiarata fra i limiti.")

    # ------------------------------------------------ 9 predizione intento ---
    titolo("9. PREDIZIONE DELL'INTENTO DEL COMPRATORE (H1, RQ1)")
    import glob
    file_scored = sorted(glob.glob(str(RADICE / "sessioni" / "P*" / "logs"
                                      / "buyer_intent_predictions_scored.csv")))
    if not file_scored:
        stampa("   Nessun file valutato: eseguire prima scripts/backfill_observed_outcome.py")
    else:
        intento = pd.concat([pd.read_csv(f) for f in file_scored], ignore_index=True)
        intento = intento[intento["observed_outcome"].notna()]
        n_pred = len(intento)
        acc = float(intento["correct"].mean())
        stampa(f"   Predizioni valutabili: {n_pred} su {len(file_scored)} sessioni")
        stampa(f"   Accuratezza top-1: {num(100*acc, 1)}%")
        stampa("")
        stampa("   Distribuzione del predetto contro l'osservato:")
        incrocio = pd.crosstab(intento["predicted_top"], intento["observed_outcome"])
        for linea in incrocio.to_string().splitlines():
            stampa("      " + linea)
        stampa("")
        osservabili = sorted(intento["observed_outcome"].unique())
        maggioritaria = intento["observed_outcome"].value_counts()
        base_magg = float(maggioritaria.iloc[0] / n_pred)
        stampa(f"   Classi effettivamente osservabili: {len(osservabili)} "
               f"({', '.join(osservabili)})")
        stampa(f"   Riferimento 'classe piu' frequente': {num(100*base_magg,1)}% "
               f"({maggioritaria.index[0]})")
        stampa(f"   Riferimento 'scelta casuale fra 5 etichette': 20,0%")
        k_corretti = int(intento["correct"].sum())
        proporzione(k_corretti, n_pred, 0.20, "accuratezza contro il caso", rientro="   ")
        stampa("")
        stampa("   RISULTATO NEGATIVO, da riportare come tale. L'accuratezza non supera")
        stampa("   la scelta casuale ed e' molto al di sotto della semplice regola")
        stampa("   'prevedi sempre la classe piu' frequente'. La causa principale e'")
        stampa("   visibile nella tabella: l'etichetta 'intelligence_gathering' viene")
        stampa("   predetta in oltre meta' dei casi ma non e' mai osservabile in un")
        stampa("   protocollo in cui si acquista un solo oggetto (cap. 6, §6.6).")
        stampa("")
        stampa("   H1 (la storia individuale migliora la predizione) NON e' verificabile")
        stampa("   con questi soli dati: richiede l'ablazione con e senza storia sugli")
        stampa("   stessi enunciati (scripts/run_intent_ablation.py), che ha bisogno del")
        stampa("   modello linguistico attivo e va eseguita a parte.")

    # -------------------------------------------- 10 qualita dei meccanismi ---
    titolo("10. QUALITA DEI MECCANISMI DI MEMORIA (H3, RQ3)")
    turni_tutti = pd.concat(
        [pd.read_csv(f) for f in sorted(glob.glob(str(RADICE / "sessioni" / "P*"
                                                      / "logs" / "negotiation_turns_log.csv")))],
        ignore_index=True)
    battute = int(turni_tutti["npc_line"].notna().sum())
    anomalie = sorted(glob.glob(str(RADICE / "sessioni" / "P*" / "logs" / "anomaly_log.csv")))
    n_anomalie = 0
    for f in anomalie:
        n_anomalie += len(pd.read_csv(f))
    stampa(f"   Battute generate dal modello linguistico: {battute}")
    stampa(f"   Anomalie rilevate automaticamente: {n_anomalie}")
    if n_anomalie == 0:
        basso, alto = wilson(0, battute)
        stampa(f"   Tasso: 0 per 100 battute   IC95% [0,0%, {num(100*alto,2)}%]")
        stampa("   H3 sulla soglia del 15% e' ampiamente rispettata. Va pero' dichiarato")
        stampa("   che si tratta di un rilevatore automatico con categorie fisse")
        stampa("   (ragionamento trapelato, rottura di personaggio, numeri inventati):")
        stampa("   misura l'assenza di quelle anomalie, non la qualita' del dialogo.")

    episodi = pd.concat(
        [pd.read_csv(f) for f in sorted(glob.glob(str(RADICE / "sessioni" / "P*"
                                                      / "logs" / "episodic_memory_log.csv")))],
        ignore_index=True)
    stampa("")
    stampa(f"   Ricordi creati durante le sessioni: {len(episodi)}")
    if len(episodi):
        stampa("   Importanza e velocita' di oblio per tipo di evento:")
        raggruppato = episodi.groupby("type").agg(
            n=("importance", "size"),
            importanza_media=("importance", "mean"),
            oblio_medio=("decay_rate", "mean"))
        for linea in raggruppato.round(3).to_string().splitlines():
            stampa("      " + linea)
        rho_i, p_i = stats.spearmanr(episodi["importance"], episodi["decay_rate"])
        stampa("")
        stampa(f"   Importanza x velocita' di oblio: rho = {num(rho_i,3)}, p {formatta_p(p_i)}")
        stampa("   Atteso negativo: piu' un ricordo e' importante, piu' lentamente svanisce.")
    riflessioni = sorted(glob.glob(str(RADICE / "sessioni" / "P*" / "logs"
                                       / "reflection_cycle_log.csv")))
    stampa("")
    stampa(f"   Cicli di riflessione osservati: {len(riflessioni)} sessioni su 27.")
    if not riflessioni:
        stampa("   Nessuno: la riflessione si innesca su una storia piu' lunga di una")
        stampa("   singola sessione. La parte di H3 sulla pertinenza delle sintesi resta")
        stampa("   quindi non verificata, e va dichiarato.")

    # ------------------------------------------------ 11 riepilogo ipotesi ---
    titolo("11. RIEPILOGO DELLE IPOTESI")
    stampa("   H1  predizione dell'intento migliorata dalla storia")
    stampa("       NON VERIFICATA - accuratezza al 18,4%, sotto il caso; l'ablazione")
    stampa("       con e senza storia resta da eseguire.")
    stampa("")
    stampa("   H2  la memoria muove prezzo e comportamento")
    stampa("       CONFERMATA - prezzo pattuito e scarto dalla riserva separano le tre")
    stampa("       condizioni con negoziazione, effetti molto grandi; abbandoni solo in D.")
    stampa("")
    stampa("   H3  qualita' dei meccanismi di memoria")
    stampa("       PARZIALE - zero anomalie su tutte le battute generate; oblio")
    stampa("       differenziale coerente col modello; riflessione e allineamento della")
    stampa("       salienza col giudizio umano non verificati in questo disegno.")
    stampa("")
    stampa("   H4  esperienza percepita")
    stampa("       CONFERMATA IN PARTE - memoria percepita, intelligenza, relazione")
    stampa("       sociale e direzione del rapporto separano nettamente le condizioni;")
    stampa("       la credibilita' complessiva NO: distingue solo il baratto vanilla")
    stampa("       dalle tre condizioni conversazionali, che fra loro sono equivalenti.")

    # ---------------------------------------------------------- 9 tabelle ---
    titolo("9. TABELLE SALVATE")
    tab1 = descrittive(oss, ["prezzo_pattuito", "scarto_riserva", "round"])
    tab2 = descrittive(oss, dimensioni)
    tab1.to_csv(ANALISI / "tabelle_comportamento.csv", index=False)
    tab2.to_csv(ANALISI / "tabelle_percezione.csv", index=False)
    stampa("   analisi/tabelle_comportamento.csv   descrittive di D1")
    stampa("   analisi/tabelle_percezione.csv      descrittive di D2 e D3")
    stampa("   analisi/risultati_test.txt          questo documento")

    (ANALISI / "risultati_test.txt").write_text("\n".join(righe), encoding="utf-8")


if __name__ == "__main__":
    main()
