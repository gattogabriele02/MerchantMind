# MerchantMind

Memoria sociale persistente e negoziazione vocale per i mercanti di *The Elder Scrolls V:
Skyrim*.

Nel gioco originale il prezzo di un oggetto è una funzione chiusa del suo valore base e
dell'abilità di Eloquenza del giocatore: il mercante non entra nel calcolo, non ricorda
niente di chi ha davanti, e l'unica mossa disponibile è accettare o non comprare.
MerchantMind sostituisce quella meccanica con una **trattativa parlata** condotta da un
personaggio che **ricorda la storia condivisa** con il giocatore e ne tiene conto nel
prezzo, nel tono e nella pazienza.

Il sistema è stato realizzato e valutato con uno studio su 27 partecipanti. I risultati
aggregati sono in [`risultati/`](risultati/), con la sintesi ragionata in
[`risultati/risultati.md`](risultati/risultati.md).

---

## 1. Come funziona

Ogni coppia giocatore-personaggio ha un **documento psico-sociale persistente** su disco
(un JSON per mercante). Contiene quattro valori di relazione (affinità, rispetto,
gratitudine, sospetto), un archivio di ricordi episodici e lo stato commerciale.

Quando succede qualcosa nel mondo di gioco, l'episodio entra nell'archivio con una
**importanza** fra 0 e 1, da cui discende la velocità con cui verrà dimenticato: più pesa,
più lentamente svanisce, e se viene richiamato il decadimento riparte. Un ciclo di
riflessione asincrono sintetizza periodicamente i ricordi salienti in una frase che il
personaggio usa come memoria di sé.

Da relazione e ricordi si ricava un **modificatore di prezzo**:

```
μ = 1 - 0,10 · affinità - 0,07 · rispetto - 0,06 · gratitudine + 0,30 · sospetto
      ± 0,05 per ogni ricordo saliente (importanza ≥ 0,80)
confinato nella banda 0,85 - 1,60

prezzo di riserva = μ × valore di listino
```

Il prezzo di riserva è il minimo che il mercante accetta, e non viene mai pronunciato.
L'apertura parte dal più alto fra riserva e listino, più un margine di trattativa.

La conversazione è governata da **due pipeline**. Quella di apertura si percorre una volta
sola: carica lo stato, riconosce l'oggetto, fissa riserva e apertura, pronuncia la prima
cifra. Quella di turno si ripete a ogni battuta: legge la controproposta, ne estrae la cifra
e l'atteggiamento, calcola la concessione per regola, genera la battuta parlata, e torna in
cima. Esce solo quando la trattativa si chiude, con un accordo o con una rottura, e solo
allora lo stato persistente viene riscritto.

**Il punto architetturale che conta:** il prezzo lo decidono formule deterministiche e
ispezionabili, non il modello linguistico. Al modello è imposto come vincolo. Nelle 227
battute generate durante lo studio non è mai stata inventata una cifra.

Quando l'accordo è raggiunto, il backend emette un'azione che uno script Papyrus esegue
dentro il gioco: l'oro passa al mercante e l'oggetto al giocatore, scavalcando il menu di
baratto originale.

## 2. Che cosa serve

MerchantMind **non è una mod a sé**: è uno strato che si innesta su
[Mantella](https://www.nexusmods.com/skyrimspecialedition/mods/98631), la mod che dà voce ai
personaggi di Skyrim. Prima di tutto il resto serve quindi un'installazione di Mantella che
funziona.

Mantella è fatta di **due metà che parlano fra loro via HTTP in locale**, e la distinzione
conta per capire dove si innesta MerchantMind:

- **la parte dentro al gioco**, cioè la mod vera e propria (`Mantella Spell`) con i suoi
  plugin SKSE, che si installa con un gestore di mod;
- **il backend Python**, un programma che gira in una finestra a parte e che fa il lavoro:
  trascrizione, modello linguistico, sintesi vocale.

MerchantMind vive **nel backend**, e lo modifica. Questo ha una conseguenza pratica da sapere
prima di cominciare: la versione di Mantella che si scarica da Nexus porta il backend già
impacchettato, quindi non si può modificare. **Per MerchantMind serve la versione dei
sorgenti**, presa dal repository, che si lancia con `python main.py`. La parte dentro al
gioco invece resta quella normale, installata da Nexus come per chiunque.

Oltre a Mantella e alle sue dipendenze servono:

| | |
|---|---|
| Creation Kit | per ricompilare gli script Papyrus e, volendo, ricostruire l'ambiente di prova |
| un endpoint LLM compatibile OpenAI | locale (Ollama, KoboldCpp) o remoto (OpenRouter, Groq, OpenAI) |
| un motore di sintesi vocale | [XTTS](https://www.nexusmods.com/skyrimspecialedition/mods/113445), [xVASynth](https://github.com/DanRuta/xVA-Synth) o [Piper](https://github.com/rhasspy/piper): quelli che Mantella già supporta |
| Python 3.11 | la versione richiesta da Mantella |

## 3. Installazione

### Passo 0: far funzionare Mantella da sola

Non saltarlo. Finché non riesci a parlare a voce con un personaggio qualsiasi, MerchantMind
non ha modo di funzionare, e cercare l'errore dopo aver aggiunto uno strato in più è molto
più difficile.

Segui la **guida ufficiale di installazione per Skyrim**:
<https://art-from-the-machine.github.io/Mantella/pages/installation.html>

In sintesi, quello che ti chiede: installare con un gestore di mod le dipendenze (SKSE,
Address Library, FonixData per il movimento labiale, UIExtensions, SkyUI, il redistribuibile
Visual C++) e poi Mantella; procurarti una chiave per un servizio LLM e metterla in
`GPT_SECRET_KEY.txt`; configurare i percorsi nel `config.ini`. Skyrim deve stare **fuori da
`Program Files`**, altrimenti i permessi di Windows bloccano la scrittura dei file.

Sai di esserci arrivato quando, avviando il gioco, la finestra di Mantella scrive
`Waiting for player to select an NPC...`, hai l'incantesimo nell'inventario, lo lanci su un
personaggio e quello ti risponde a voce.

Se qualcosa non va, la pagina delle domande frequenti copre quasi tutti i casi:
<https://art-from-the-machine.github.io/Mantella/pages/issues_qna> , e c'è il
[Discord del progetto](https://discord.gg/Q4BJAdtGUE).

### Passo 1: passare al backend dei sorgenti

Ora si sostituisce il backend impacchettato con quello modificabile. La parte dentro al gioco
non si tocca.

```
git clone https://github.com/art-from-the-machine/Mantella
cd Mantella
py -3.11 -m venv MantellaEnv
.\MantellaEnv\Scripts\Activate
pip install -r requirements.txt
```

Poi copia in questo checkout il `GPT_SECRET_KEY.txt` e il `config.ini` che già funzionavano,
chiudi il backend impacchettato e avvia questo:

```
MantellaEnv\Scripts\python.exe main.py
```

Deve comportarsi esattamente come prima. Se sì, la base è pronta.

### Passo 2: installare MerchantMind

1. **Copia il modulo** dentro il checkout, conservando il percorso:

   ```
   src/merchantmind/   ->   <Mantella>/src/merchantmind/
   ```

2. **Applica i due agganci** nel codice di Mantella: due file e poche righe, descritti in
   [`INTEGRAZIONE.md`](INTEGRAZIONE.md). Sono le uniche modifiche a Mantella.

3. **Installa lo script Papyrus** dello scambio, seguendo
   [`papyrus/README.md`](papyrus/README.md). Senza, la trattativa funziona lo stesso ma
   l'accordo resta verbale: oro e oggetto non passano di mano.

4. **Copia gli strumenti** di [`avvio/`](avvio/) nella radice del checkout: si aspettano di
   trovare lì `main.py` e `MantellaEnv/`.

### Passo 3: verificare

Avvia con `MANTELLA_MERCHANTMIND=1` e parla con un mercante. Nel log del backend deve
comparire:

```
MerchantMind enabled for '<nome>' (npc_id=<identificativo>)
```

Se non compare, il personaggio non è stato riconosciuto come mercante: vedi il paragrafo
sulla configurazione. Se compare ma la trattativa non parte, l'errore è registrato per esteso
nel log.

## 4. Configurazione

MerchantMind è **spento** se non lo si accende esplicitamente. Si governa con quattro
variabili d'ambiente:

| variabile | effetto |
|---|---|
| `MANTELLA_MERCHANTMIND` | `1` accende la negoziazione. Senza, Mantella si comporta come sempre |
| `MANTELLA_MERCHANTMIND_TRADE` | `1` emette l'azione di scambio verso il gioco. Richiede lo script Papyrus installato |
| `MANTELLA_MERCHANTMIND_SEED` | un intero rende riproducibile la perturbazione su margine e passo di concessione; `random` la rende variabile; assente la disattiva |
| `MANTELLA_MERCHANTMIND_FAST_MODEL` | modello più piccolo per le chiamate strutturate. `off` usa un modello solo |

Il resto si configura nel `config.ini` di Mantella: endpoint, modello, parametri di
generazione e sintesi vocale.

Un personaggio viene riconosciuto come mercante dal **nome visualizzato** o da parole chiave
nella sua biografia. Lo stato è agganciato al nome, non al riferimento in gioco: lo stesso
personaggio in una cella diversa, o duplicato nel Creation Kit, condivide la stessa memoria.

## 5. Avviare tutto, con Mod Organizer 2

Skyrim con le mod si avvia **da MO2**, mai da Steam: MO2 costruisce al volo una cartella
`Data` virtuale con dentro le mod attive, e il gioco lanciato da fuori non le vede. Mantella
e le sue dipendenze stanno lì dentro.

Tre cose invece MO2 **non** le virtualizza, e stanno dove uno se le aspetta:

- il backend Python, che è un programma a parte e vive nel suo checkout;
- i dati che scrive, in `Documents\My Games\Mantella\data`, compresi gli stati dei mercanti
  e i log di MerchantMind;
- i salvataggi di Skyrim.

### L'ordine di avvio

1. **La sintesi vocale.** Se usi XTTS è un server a parte su `localhost:8020`, e impiega una
   trentina di secondi a caricare il modello. Se parte dopo il resto, la prima battuta
   fallisce.
2. **Il backend**, cioè `MantellaEnv\Scripts\python.exe main.py`, con le variabili
   d'ambiente di MerchantMind impostate.
3. **Skyrim da MO2**, scegliendo SKSE nel menu a tendina dei programmi, non il lanciatore
   del gioco.

`avvio\avvia_esperimento.bat` fa i primi due in sequenza, con l'attesa in mezzo.

### La trappola dei permessi

Se MO2, e quindi Skyrim, gira **come amministratore** e il backend no, il tasto per parlare
non funziona e **non compare nessun errore**: il rilevamento del tasto non riesce a leggere
gli eventi di un processo che gira a un livello di integrità più alto del suo.

O li avvii **entrambi** come amministratore, o **nessuno dei due**.
`avvia_esperimento.bat` si rilancia da solo come amministratore proprio per questo motivo. È
la prima cosa da controllare se la voce non viene registrata e tutto il resto sembra a posto.

### Il Creation Kit e la cartella vera

Per compilare gli script Papyrus, il Creation Kit legge i sorgenti dalla cartella **reale**
del gioco, non da quella virtuale di MO2. I sorgenti SKSE vanno quindi copiati a mano da
`<MO2>\mods\Skyrim Script Extender (SKSE64)\Scripts\Source\` dentro
`...\Skyrim Special Edition\Data\Source\Scripts\`. I dettagli sono in
[`papyrus/README.md`](papyrus/README.md).

## 6. Eseguire una sessione

```
avvio\avvia_esperimento.bat      avvia sintesi vocale e backend con le variabili giuste
avvio\reset_esperimento.bat      riporta i mercanti allo stato precaricato
avvio\archivia_sessione.ps1      archivia log, conversazioni e stati di una sessione
```

L'ordine conta. Prima di ogni partecipante si **archivia** la sessione precedente e poi si
**resetta**: Mantella ricarica i riassunti delle conversazioni come contesto, quindi se
restano sul disco il mercante si ricorda del partecipante precedente. Lo script di reset
avvisa se trova conversazioni non archiviate.

Il precaricamento dei mercanti si fa anche a mano:

```
MantellaEnv\Scripts\python.exe scripts\seed_experiment.py --player "NomeDelPersonaggio"
```

Il nome deve corrispondere **esattamente** a quello del personaggio in gioco, perché è la
chiave con cui si trova lo stato su disco.

## 7. Riprodurre l'analisi

Gli script si lanciano dalla radice del checkout, dove stanno `sessioni/` (i dati grezzi) e
`analisi/` (gli aggregati). Nell'ordine:

| script | che cosa fa |
|---|---|
| `scripts/analisi.py` | unisce tutte le sessioni e produce le tabelle di comportamento e percezione |
| `scripts/test_statistici.py` | esegue i test e scrive l'output integrale |
| `scripts/analisi_latenza.py` | scompone i tempi per componente |
| `scripts/analisi_sottogruppi.py` | ripete l'analisi dentro i sottogruppi e spoglia le risposte aperte |
| `scripts/verifica_anomalie.py` | prepara il controllo umano sulle battute generate |
| `scripts/run_intent_ablation.py` | confronta il predittore dell'intento con e senza storia relazionale |
| `scripts/backfill_observed_outcome.py` | ricostruisce l'esito osservato nel registro delle predizioni |

`scripts/crea_modulo_dati.py` e `scripts/moduli_trasferimento.py` servono alla raccolta: il
primo genera il foglio in cui trascrivere i questionari cartacei, il secondo li sposta fra
computer.

## 8. Che cosa ha prodotto lo studio

27 partecipanti, disegno entro i soggetti a quattro condizioni con ordine controbilanciato
da un quadrato latino, 108 osservazioni. Le condizioni: baratto originale (V), negoziazione
senza storia (N), con memoria positiva (A), con memoria negativa (D).

**La memoria arriva al prezzo.** Mediane di 47,0 monete con il mercante dalla memoria
positiva, 49,4 con quello senza storia, 62,0 con quello dalla memoria negativa, nell'ordine
previsto prima di raccogliere i dati. Di tutta la dispersione dei prezzi, il 96% si spiega
con quale mercante si aveva davanti.

**L'effetto è asimmetrico.** La memoria negativa vale 14 monete di sovrapprezzo, quella
positiva solo 3 di sconto, perché la riserva del mercante benevolo sta sotto il valore di
listino e l'apertura non la mostra: lo sconto lo ottiene solo chi tratta.

**Il canale regge il dialogo.** Zero cifre inventate su 227 battute generate.

**La memoria si vede, ma non rende più credibili.** Memoria percepita, intelligenza e
relazione sociale separano nettamente le condizioni; la credibilità complessiva no: i tre
mercanti che parlano sono giudicati credibili allo stesso modo, che ricordino o no. Tutto il
salto sta fra il menu e il poter parlare.

**La predizione dell'intento non ha funzionato:** 18,4% di accuratezza, sotto il livello del
caso. Lo spazio delle etichette non era allineato al protocollo, e il confronto che avrebbe
dovuto isolarne il contributo, con e senza storia relazionale, non è stato condotto.

**Il costo sta nella voce, non nel ragionamento.** La catena che il giocatore attende è di
circa 2,2 secondi; la sola sintesi vocale ne è il 56,6%, i nodi di MerchantMind poco più del
16%.

## 9. Da dove ripartire

- **Lo studio longitudinale.** La memoria qui è precaricata, non accumulata: si misura
  l'effetto di *avere* una storia, non quello di *costruirla*. È il seguito naturale, e
  richiede più sedute con lo stesso partecipante.
- **Il predittore dell'intento.** Va ridisegnato lo spazio delle etichette, e soprattutto va
  eseguita l'ablazione con e senza storia: `scripts/run_intent_ablation.py` è già pronto.
- **La propagazione degli eventi del mondo** è realizzata e funzionante
  (`src/merchantmind/world_events.py`, `scripts/inject_world_event.py`) ma non è mai stata
  sottoposta a verifica sperimentale, perché nel disegno adottato le storie erano
  precaricate.
- **L'equilibrio economico.** Una forbice del 30% sul prezzo, su una partita lunga, mette in
  tensione l'economia del gioco. Le leve sono restringere la banda del modificatore,
  aggiungere un richiamo verso i prezzi degli altri mercanti, o limitare la meccanica agli
  acquisti che contano.
- **Fuori dal gioco.** La struttura non è specifica di Skyrim: stato relazionale che
  persiste, margine che non si dichiara, decisione quantitativa fuori dal modello,
  tutto ispezionabile. Resta un'ipotesi che questo studio non verifica.

## 10. I dati dei partecipanti

> **Questo repository è privato, e deve restarlo.** In `risultati/` ci sono dati riferiti ai
> singoli partecipanti: `partecipanti.csv` contiene la demografia, `aperte.csv` le risposte a
> testo libero. Sono pseudonimizzati con i codici P01-P27, ma il consenso informato promette
> conservazione anonimizzata: renderlo pubblico, o inoltrarlo fuori dalle persone invitate,
> va oltre quello che i partecipanti hanno accettato.

Se un domani serve una versione aperta, vanno tolti quei due file e vanno ricontrollati
`item.csv`, `osservazioni.csv` e `latenza_sessioni.csv`: contengono solo misure, ma sono
anch'essi riga per riga riferiti al singolo partecipante.

I **dati grezzi** di sessione, cioè log di conversazione, trascrizioni e stati finali, non
sono qui e non sono versionati: il `.gitignore` esclude `sessioni/` apposta. Chi riprende il
progetto e deve rieseguire l'analisi dall'origine li deve chiedere a chi li custodisce.

## 11. Licenza e provenienza

Il codice è distribuito sotto **AGPL-3.0**, la stessa licenza di
[Mantella](https://github.com/art-from-the-machine/Mantella), su cui questo lavoro si innesta
e di cui costituisce un'opera derivata. Il testo integrale è in [`LICENSE`](LICENSE).

In pratica significa che chi riprende il progetto e lo distribuisce, anche solo rendendolo
accessibile attraverso una rete, deve a sua volta renderne disponibili i sorgenti sotto la
stessa licenza.

I dati in `risultati/` non sono coperti dalla licenza del software: per quelli valgono le
condizioni del consenso informato descritte sopra.

## 12. Che cosa c'è qui dentro

```
.
├── README.md              questo file
├── INTEGRAZIONE.md        i due agganci nel codice di Mantella
├── LICENSE                AGPL-3.0, ereditata da Mantella
├── src/merchantmind/      il modulo: stato, salienza, prezzo, pipeline, scambio
├── papyrus/               gli script lato gioco, con le istruzioni di compilazione
├── scripts/               esperimento e analisi
├── avvio/                 avvio, reset e archiviazione di una sessione
└── risultati/             tabelle, test ed esiti dello studio
```

## 13. Link utili

| | |
|---|---|
| installazione di Mantella per Skyrim | <https://art-from-the-machine.github.io/Mantella/pages/installation.html> |
| problemi e domande frequenti | <https://art-from-the-machine.github.io/Mantella/pages/issues_qna> |
| Mantella su Nexus, versione stabile | <https://www.nexusmods.com/skyrimspecialedition/mods/98631> |
| sorgenti del backend | <https://github.com/art-from-the-machine/Mantella> |
| la mod lato gioco | <https://github.com/art-from-the-machine/Mantella-Spell> |
| Discord del progetto | <https://discord.gg/Q4BJAdtGUE> |

Mantella è un progetto di terzi in sviluppo attivo: i due agganci descritti in
[`INTEGRAZIONE.md`](INTEGRAZIONE.md) sono riferiti alla versione usata per lo studio, e su una
versione più recente i nomi dei metodi possono essere cambiati. Gli agganci restano gli
stessi due punti, l'avvio della conversazione e la generazione del turno: se non trovi le
righe esatte, cerca quelle.
