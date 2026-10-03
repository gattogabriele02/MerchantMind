# Risultati dello studio MerchantMind

> Sintesi ragionata dei risultati dello studio con 27 partecipanti.
> Numeri prodotti da `scripts/analisi.py` e `scripts/test_statistici.py`;
> l'output integrale dei test è in [`risultati_test.txt`](risultati_test.txt).
> Ultimo aggiornamento: 28 agosto 2026, campione completo.

---

## 1. Il campione

**Ventisette partecipanti**, disegno entro i soggetti, quattro condizioni ciascuno
per **108 osservazioni** complessive.

| | |
|---|---|
| Età | media 26,4 anni (min 18, max 51) |
| Genere | 17 uomini, 10 donne |
| Durata della sessione | media 28,7 minuti (min 21, max 35) |
| Esperienza con Skyrim | mai 18 · qualche ora 5 · molte ore 4 |
| Conosce il commercio di Skyrim | no 16 · ne ha sentito parlare 4 · sì 7 |
| Altri giochi di ruolo | no 21 · qualcuno 5 · molti 1 |
| Assistenti vocali | mai 3 · raramente 9 · ogni tanto 9 · spesso 6 |
| Ha già parlato a voce con un NPC | **mai, tutti e 27** |
| Build | 1: 7 · 2: 7 · 3: 7 · 4: 6 |

Due caratteristiche del campione vanno dichiarate perché condizionano la lettura.
Nessun partecipante aveva mai parlato a voce con un personaggio non giocante: la
condizione conversazionale era una novità assoluta per tutti, il che gonfia
plausibilmente le misure di coinvolgimento. E due terzi non avevano mai giocato a
Skyrim, quindi lo scenario di ponderazione «pro esperti» poggia su quattro casi.

### Condizioni

| | Configurazione | Mercante | Riserva |
|---|---|---|---|
| **V** | baratto vanilla, nessuna trattativa | Adrianne Avenicci | — (prezzo fisso 50) |
| **N** | negoziazione, nessuna storia | Arcadia | 46,5 |
| **A** | negoziazione, memoria positiva | Belethor | 42,5 |
| **D** | negoziazione, memoria negativa | Lucan Valerius | 61,7 |

Riferimento di tutti i confronti: **N**. Correzione di **Holm** entro ciascuna
famiglia, α = 0,05. Accanto a ogni *p* è riportata la dimensione dell'effetto.

---

## 2. Affidabilità delle scale

| Dimensione | Item | α di Cronbach |
|---|---|---|
| Memoria percepita | i09–i11 | **0,986** |
| Intelligenza | i04–i06 | **0,981** |
| Credibilità complessiva | i15–i17 | **0,978** |
| Emozione | i07–i08 | **0,977** |

Valori molto alti, calcolati su tutte le osservazioni (partecipante × condizione) e
quindi comprensivi della varianza fra condizioni — la stessa convenzione della scala
originale. Le dimensioni a un solo item (relazione sociale, direzione della relazione,
collera, trattativa percepita) restano item singoli e si riportano come tali.

---

## 3. Scelta dei test

Il piano prevedeva l'ANOVA a misure ripetute e, in caso di violazione delle
assunzioni, l'alternativa non parametrica. Shapiro-Wilk sulle differenze appaiate:

| Misura | Esito |
|---|---|
| prezzo pattuito | normale (N–A: W=0,966, p=0,587; N–D: W=0,961, p=0,491) |
| scarto dalla riserva | normale (stessi valori) |
| round | N–A non normale (p=0,018) |
| credibilità | non normale su tutti i confronti (p=0,008 / 0,003 / 0,043) |
| memoria percepita | N–V non normale (p=0,049) |

Di conseguenza: **ANOVA a misure ripetute** su prezzo e scarto, con Friedman come
verifica di robustezza; **Friedman e Wilcoxon** su round e su tutte le misure
percettive, che sono ordinali per costruzione.

---

## 4. H2 — La memoria muove il comportamento economico

> **Confermata**, con effetti fra i più grandi osservabili in questo tipo di studio.

La condizione V è esclusa dai confronti sul prezzo: il baratto vanilla dipende
dall'Eloquenza del giocatore e non dallo stato relazionale, quindi non è un livello
omogeneo (§6.2). Resta invece in tutte le misure percettive.

### 4.1 Prezzo pattuito

**ANOVA a misure ripetute** (n = 23 completi): F(2, 44) = **587,94**, p < 0,001.
Greenhouse-Geisser ε = 0,860, p corretto < 0,001.
η² parziale = **0,964**, η² generalizzato = **0,932**.

Verifica non parametrica: Friedman χ²(2) = 40,51, p < 0,001, W di Kendall = **0,881**.

| Confronto | p | p (Holm) | r | mediana delle differenze |
|---|---|---|---|---|
| N vs A | < 0,001 | < 0,001 | 0,773 | −3,00 |
| N vs D | < 0,001 | < 0,001 | 0,876 | +14,00 |

Mediane: N = 49,00 · A = 47,00 · D = 62,00.

### 4.2 Scarto dalla riserva

Quanto il giocatore ha pagato **sopra il minimo** che il mercante avrebbe accettato:
misura la conduzione della trattativa più della condizione.

**ANOVA a misure ripetute** (n = 23): F(2, 44) = **18,74**, p < 0,001.
ε = 0,860, p corretto < 0,001. η² parziale = 0,460, η² generalizzato = 0,304.

Friedman χ²(2) = 24,80, p < 0,001, W = 0,539.

| Confronto | p | p (Holm) | r | mediana delle differenze |
|---|---|---|---|---|
| N vs A | 0,028 | 0,028 | 0,479 | +1,00 |
| N vs D | < 0,001 | 0,001 | 0,724 | −1,20 |

Mediane: N = 2,50 · A = 4,50 · D = 0,30.

**Il gradiente è invertito rispetto ai prezzi.** Col mercante più generoso si lascia
sul tavolo di più, con quello ostile quasi nulla.

### 4.3 Numero di round

Friedman χ²(2) = 24,09, p < 0,001, W = 0,446. Mediane: N = 2 · A = 1 · D = 4.

| Confronto | p | p (Holm) | r |
|---|---|---|---|
| N vs A | 0,028 | 0,028 | 0,568 |
| N vs D | 0,002 | 0,003 | 0,688 |

### 4.4 Abbandoni

Affari conclusi: **V 27/27 · N 27/27 · A 27/27 · D 23/27**.

**Q di Cochran**: Q(3) = 12,00, **p = 0,007**. Abbandoni in D: 4/27 = 14,8%,
IC95% [5,9%; 32,5%].

I confronti a coppie non raggiungono la significatività (N vs D: McNemar esatto
p = 0,125; Holm 0,375). **Va letto come limite di potenza, non come assenza di
effetto**: con quattro sole coppie discordanti il McNemar esatto non può scendere
sotto p = 0,125 qualunque sia l'entità della differenza. Il test d'insieme la rileva,
ed è il dato in cui la condizione conta più del comportamento individuale: nessuno
ha mai abbandonato Belethor, Arcadia o Adrianne.

---

## 5. H4 — L'esperienza percepita

> **Confermata in parte, e il modo in cui non lo è costituisce il risultato più
> interessante dello studio.**

Tutte le dimensioni su quattro condizioni, n = 27 completi.

| Dimensione | χ²(3) | p | W | N vs V | N vs A | N vs D |
|---|---|---|---|---|---|---|
| **Memoria percepita** | 70,13 | < 0,001 | 0,866 | ✱ r=0,876 | ✱ r=0,854 | ✱ r=0,855 |
| Relazione sociale | 70,49 | < 0,001 | 0,870 | ✱ r=0,889 | ✱ r=0,906 | ✱ r=0,917 |
| Intelligenza | 68,96 | < 0,001 | 0,851 | ✱ r=0,878 | ✱ r=0,863 | ✱ r=0,835 |
| Direzione della relazione | 68,67 | < 0,001 | 0,848 | ✱ r=0,882 | ✱ r=0,856 | ✱ r=0,875 |
| Trattativa percepita | 67,47 | < 0,001 | 0,833 | ✱ r=0,902 | ✱ r=0,959 | ✱ r=0,645 |
| Collera percepita | 65,67 | < 0,001 | 0,811 | n.s. | n.s. | ✱ r=0,888 |
| Emozione | 59,05 | < 0,001 | 0,729 | ✱ r=0,880 | n.s. (0,075) | n.s. (0,075) |
| **Credibilità complessiva** | 56,35 | < 0,001 | 0,696 | ✱ r=0,876 | **n.s. p=1,000** | **n.s. p=1,000** |
| Comportamento | 44,00 | < 0,001 | 0,543 | ✱ r=0,882 | n.s. | n.s. |

✱ = significativo dopo Holm. Le mediane per condizione sono in
[`tabelle_percezione.csv`](tabelle_percezione.csv).

### Mediane delle dimensioni chiave

| | V | N | A | D |
|---|---|---|---|---|
| Memoria percepita | 1,00 | 4,67 | 6,67 | 6,67 |
| Intelligenza | 1,00 | 5,33 | 6,67 | 6,67 |
| Credibilità | 2,00 | 6,33 | 6,00 | 6,00 |
| Direzione della relazione | 2,00 | 5,00 | 6,00 | **1,00** |
| Collera percepita | 1,00 | 1,00 | 1,00 | **6,00** |
| Trattativa percepita | 1,00 | 6,00 | 7,00 | 7,00 |

### Il risultato controintuitivo

**La memoria non rende il mercante più credibile.** La credibilità complessiva
distingue nettamente il baratto vanilla dalle tre condizioni conversazionali
(r = 0,876), ma **non distingue fra loro** le tre condizioni con dialogo: N vs A
p = 0,940, N vs D p = 0,896, con effetti praticamente nulli (r = 0,017 e 0,033).

Quello che la memoria produce è **riconoscimento** — memoria percepita, intelligenza
attribuita, relazione sociale, direzione del rapporto — non credibilità. Un mercante
che ricorda viene giudicato più *memore* e più *intelligente*, ma non più *vero*.
Ciò che rende credibile un personaggio, in questi dati, è il fatto stesso di poterci
parlare.

Vale la pena notare che la **direzione** della relazione è perfettamente colta: la
mediana passa da 6,00 con Belethor a **1,00** con Lucan, e la collera percepita da
1,00 a 6,00. Nessun partecipante ha confuso il verso del rapporto.

---

## 6. Il questionario finale

### Scelte forzate (binomiale esatto, IC di Wilson a due code)

| Domanda | Risposta | Proporzione | IC95% | p |
|---|---|---|---|---|
| Ha notato differenze? | sì | **27/27** (100%) | [87,5%; 100%] | < 0,001 (vs 0,50) |
| Il più ostile | **D** | 27/27 (100%) | [87,5%; 100%] | < 0,001 |
| Il più amichevole | **A** | 27/27 (100%) | [87,5%; 100%] | < 0,001 |
| Sembrava ricordare qualcosa di me | A o D | **27/27** (100%) | [87,5%; 100%] | < 0,001 (vs 0,50) |
| » di cui A | A | 15/27 (55,6%) | [37,3%; 72,4%] | < 0,001 |
| Trattativa più coinvolgente | D | 12/27 (44,4%) | [27,6%; 62,7%] | 0,022 |
| Il prezzo dipendeva da… | **rapporto** | 27/27 (100%) | [87,5%; 100%] | < 0,001 |

Tre risultati all'unanimità: tutti hanno notato differenze, tutti hanno identificato
correttamente il verso della relazione, e **tutti hanno attribuito il prezzo al
rapporto col mercante** anziché alla propria abilità o al caso. Alla domanda su chi
sembrasse ricordare qualcosa di loro, **nessuno** ha indicato il mercante neutro o
quello vanilla.

La domanda sulla trattativa più coinvolgente si divide fra D e A (12 e 12, con 3 a N):
il coinvolgimento non segue la benevolenza, e il mercante ostile è tanto memorabile
quanto quello amichevole.

### Classifica di credibilità (ordinamento 1–4)

Friedman χ²(3) = 54,33, p < 0,001, W = 0,671.
Rango medio (1 = più «vero»): **A 1,70 · D 1,81 · N 2,48 · V 4,00**.

| Confronto | p | p (Holm) | r |
|---|---|---|---|
| N vs V | < 0,001 | < 0,001 | 0,899 |
| N vs A | 0,005 | 0,010 | 0,540 |
| N vs D | 0,017 | 0,017 | 0,460 |

**Nota importante.** Nel confronto diretto fra i quattro mercanti le condizioni con
memoria risultano più «vere» di quella neutra, mentre sulla scala item per item la
credibilità non le distingueva. La differenza fra i due strumenti è istruttiva: la
valutazione assoluta non separa, il confronto diretto sì. È materiale per la
discussione sulla validità di costrutto.

---

## 7. La meccanica nel suo insieme

Punteggi 1–7, un valore per partecipante, confrontati col punto neutro della scala (4)
con il test dei ranghi con segno.

| Blocco | Mediana | Media | p | r |
|---|---|---|---|---|
| Valore soggettivo della trattativa (SVI) | 5,75 | 5,79 | < 0,001 | 0,877 |
| Coinvolgimento e immersione | 6,25 | 6,39 | < 0,001 | 0,880 |
| Preferenza sulla meccanica | 6,25 | 6,26 | < 0,001 | 0,883 |
| Attrito: attese fra le battute | 2,00 | 2,52 | < 0,001 | 0,856 |
| Attrito: doversi ripetere | 1,00 | 1,52 | < 0,001 | 0,933 |

Tutti i blocchi positivi sono significativamente sopra il punto neutro, e i due
attriti significativamente sotto: la latenza e gli errori di riconoscimento non sono
stati vissuti come un ostacolo. Va ricordato che **nessuno dei partecipanti aveva mai
parlato a voce con un NPC**, quindi l'effetto novità è parte di questi numeri.

---

## 8. H1 — Predizione dell'intento

> **Risultato negativo**, da riportare come tale.

141 predizioni valutabili su 27 sessioni. **Accuratezza top-1: 18,4%.**

Riferimenti: scelta casuale fra 5 etichette = 20,0%; regola «prevedi sempre la classe
più frequente» = 64,5%. Il modello sta **sotto entrambi**.

Matrice di confusione (predetto in riga, osservato in colonna):

| | accept_quickly | haggle_hard | walkaway_likely |
|---|---|---|---|
| accept_quickly | 18 | 27 | 3 |
| bundle_interest | 1 | 0 | 0 |
| haggle_hard | 1 | 6 | 0 |
| **intelligence_gathering** | **20** | **52** | **1** |
| walkaway_likely | 4 | 6 | 2 |

La causa è leggibile nella tabella: `intelligence_gathering` viene predetta 73 volte
su 141 — oltre la metà — e **non è mai osservabile** in un protocollo in cui si
acquista un solo oggetto (§6.6). Il predittore spende la maggior parte della sua massa
su una classe che il disegno non può produrre.

**H1 in senso stretto non è verificata**: il confronto fra predizione con e senza
storia individuale richiede l'ablazione sugli stessi enunciati
(`scripts/run_intent_ablation.py`), che ha bisogno del modello linguistico attivo e
va eseguita a parte.

---

## 9. H3 — Qualità dei meccanismi di memoria

> **Parzialmente verificata.**

**Anomalie del modello linguistico: zero su 227 battute generate** (IC95% superiore
1,66%). La soglia del 15% prevista da H3 è ampiamente rispettata. Va però dichiarato
che si tratta di un rilevatore automatico con categorie fisse — ragionamento trapelato,
rottura di personaggio, numeri inventati — e che misura l'assenza di *quelle* anomalie,
non la qualità del dialogo in generale.

**Memoria episodica: 81 ricordi creati.**

| Tipo di evento | n | Importanza media | Oblio medio |
|---|---|---|---|
| `first_purchase` | 47 | 0,323 | 0,068 |
| `negotiation_hard` | 30 | 0,440 | 0,056 |
| `negotiation_walkaway` | 4 | 0,565 | 0,044 |

L'oblio differenziale si comporta come previsto: correlazione fra importanza e
velocità di oblio **rho = −1,000, p < 0,001**, cioè perfettamente monotòna — più un
ricordo è importante, più lentamente svanisce. L'abbandono di una trattativa produce
il ricordo più pesante, il primo acquisto il più leggero.

**Cicli di riflessione: zero in tutte e 27 le sessioni.** La riflessione si innesca su
una storia più lunga di una seduta singola, quindi la parte di H3 sulla pertinenza
delle sintesi resta non verificata in questo disegno.

L'allineamento fra salienza calcolata e giudizio umano richiede una codifica
indipendente di un campione di episodi e non è stato svolto.

---

## 10. Controlli metodologici

**Effetto della posizione nella sequenza.** Il quadrato latino ha funzionato: nessun
effetto rilevabile né sulla credibilità (χ² = 1,22, p = 0,749, W = 0,015) né sul numero
di round (χ² = 0,71, p = 0,870, W = 0,009).

**Ponderazione per esperienza con Skyrim.** Le conclusioni coincidono nei tre scenari
(uniforme, pro esperti, pro neofiti): le medie si spostano al massimo di qualche
centesimo. Secondo la regola fissata prima della raccolta, **l'effetto è robusto e si
riporta il solo scenario uniforme**. Resta da dichiarare che il gruppo «molte ore»
conta 4 partecipanti su 27.

---

## 11. Un risultato emerso dai dati

Non era previsto dal piano e va presentato come esplorativo.

| Correlazione | rho | p |
|---|---|---|
| round × scarto dalla riserva (tutte le condizioni) | **−0,547** | < 0,001 |
| » solo N | −0,519 | 0,006 |
| » solo A | −0,170 | 0,398 |
| » solo D | −0,443 | 0,034 |
| memoria percepita × scarto | −0,065 | 0,575 |

**Chi tratta di più paga meno, e la percezione della relazione non c'entra.** Lo scarto
dalla riserva dipende da quanti round il giocatore sostiene, non da quanto avverte di
avere un rapporto col mercante.

Questo si lega a un fatto strutturale del modello osservato nei log: il prezzo di
apertura è **identico** per Belethor e Arcadia (53,90) e più alto solo per Lucan (66,51),
perché la formula di apertura parte da `max(riserva, valore di listino)` e la riserva di
Belethor (42,5) sta sotto il listino (50). Ne segue un'asimmetria:

> **La memoria negativa è visibile fin dalla prima battuta; quella positiva solo se il
> giocatore tratta.** Il vantaggio della relazione favorevole esiste sempre nel modello
> — la riserva più bassa — ma diventa denaro soltanto per chi negozia. Chi si fida e
> accetta subito paga come se il mercante fosse neutro.

È la spiegazione delle inversioni A/N osservate in diverse sessioni individuali, e un
punto di progettazione da discutere: un mercante benevolo che non mostra la propria
benevolenza nel prezzo di apertura restituisce il proprio favore solo ai giocatori
già esperti di trattativa.

---

## 12. Riepilogo delle ipotesi

| | Ipotesi | Esito |
|---|---|---|
| **H1** | la storia individuale migliora la predizione dell'intento | **non verificata** — accuratezza 18,4%, sotto il caso; ablazione da eseguire |
| **H2** | la memoria muove prezzo e comportamento | **confermata** — η² parziale 0,964 sul prezzo, W 0,88; abbandoni solo in D |
| **H3** | qualità dei meccanismi di memoria | **parziale** — zero anomalie su 227 battute, oblio differenziale coerente; riflessione e allineamento della salienza non verificati |
| **H4** | esperienza percepita | **confermata in parte** — memoria, intelligenza, relazione e direzione del rapporto separano nettamente; la credibilità complessiva no |

---

## 13. Che cosa resta da fare

1. **Ablazione dell'intento** con e senza storia individuale, per chiudere H1.
2. **Codifica delle risposte aperte** (214 raccolte) secondo lo schema fissato prima
   della raccolta: memoria / prezzo / tono / problema tecnico, due codificatori
   indipendenti, accordo dichiarato.
3. **Codifica indipendente della salienza** su un campione di episodi, per la parte di
   H3 rimasta aperta.

## File prodotti

| File | Contenuto |
|---|---|
| `osservazioni.csv` | una riga per partecipante × condizione: la tabella principale |
| `partecipanti.csv` | una riga per partecipante: demografia e questionario finale |
| `item.csv` | formato lungo, un item per riga |
| `aperte.csv` | le 214 risposte a testo libero |
| `tabelle_comportamento.csv` | descrittive di D1 |
| `tabelle_percezione.csv` | descrittive di D2 e D3 |
| `risultati_test.txt` | output integrale dei test |
| `riepilogo.txt` | riassunto descrittivo prodotto da `analisi.py` |
