# Gli agganci nel codice di Mantella

MerchantMind è additivo: il modulo in `src/merchantmind/` non viene mai importato da
Mantella se non attraverso i due punti descritti qui, e se la funzione è spenta il
comportamento di Mantella resta quello originale.

Gli agganci sono due file. Il primo è obbligatorio, il secondo serve solo se si vuole
iniettare eventi del mondo durante la partita.

---

## 1. `src/conversation/conversation.py`: la negoziazione

È l'aggancio principale. In testa al file:

```python
from src.merchantmind import integration as merchantmind
```

Nel costruttore della conversazione, tre attributi che tengono la sessione di trattativa:

```python
self.__merchant_session = None
self.__merchant_npc_id: str = ""
self.__merchant_meta: dict = {}
```

**All'avvio della conversazione** si prova ad aprire una sessione. Il metodo esce subito se
la funzione è spenta, se l'interlocutore è il giocatore, o se il personaggio non è
riconosciuto come mercante. Qualunque errore viene catturato e riporta alla pipeline normale
di Mantella: un guasto di MerchantMind non deve rompere la conversazione.

```python
if not merchantmind.enabled(config):
    return
npc = self.__context.npcs_in_conversation.last_added_character
if not npc or npc.is_player_character or not merchantmind.is_merchant_character(npc):
    return
self.__merchant_session = merchantmind.build_negotiation(self.__llm_client, config, language)
self.__merchant_npc_id = merchantmind.npc_id_for(npc)
self.__merchant_meta   = merchantmind.npc_meta_for(npc)
```

**A ogni battuta del giocatore**, se la sessione esiste, il turno viene condotto dal grafo di
negoziazione invece che dalla generazione normale, in un thread che riempie la coda della
sintesi vocale. La prima battuta chiama `session.open(...)`, le successive
`session.respond(...)`.

**Alla chiusura dell'accordo** si costruisce l'ordine di scambio e lo si allega alla risposta
come azione per il gioco:

```python
from src.merchantmind import transaction
order = transaction.build_trade_order(npc.name, item, agreed, item_index=...)
if os.environ.get("MANTELLA_MERCHANTMIND_TRADE", "").lower() in ("1", "true", "yes", "on"):
    return [order]
return []
```

Senza la variabile d'ambiente l'ordine viene solo registrato nei log: l'accordo resta
verbale. È il comportamento giusto finché lo script Papyrus non è installato, perché
un'azione che il gioco non sa smistare non produce nulla di buono.

Il nome passato come `source` dev'essere il **nome visualizzato** del personaggio: è con
quello che lo script lato gioco risolve l'attore.

---

## 2. `src/http/routes/world_event_route.py`: gli eventi del mondo

Serve solo se si vuole che fatti accaduti nel mondo entrino nella memoria dei mercanti
mentre si gioca. La rotta riceve l'evento e lo propaga:

```python
base_dir = os.path.join(self._config.save_folder, "data", "merchantmind")
from src.merchantmind.world_events import WorldEvent, propagate
from src.merchantmind.research_logger import research_logger
from src.merchantmind.inventory import update_inventory
```

Gli import sono locali alla funzione, non in testa al file, così la rotta non dipende dal
modulo quando la funzione è spenta.

Lo stesso percorso lo usa `scripts/inject_world_event.py`, che permette di iniettare un
evento dalla riga di comando mentre la partita è in corso.

---

## 3. Dove finiscono i dati

| | |
|---|---|
| stato dei mercanti | `<cartella salvataggi Mantella>/data/merchantmind/<giocatore>/<mercante>.json` |
| log di ricerca | `<cartella salvataggi Mantella>/data/merchantmind/logs/*.csv` |
| conversazioni | la cartella conversazioni di Mantella, come per qualunque personaggio |

Lo stato è una coppia (giocatore, mercante): cambiare il nome del personaggio giocante
significa ricominciare da mercanti senza memoria.

I log di ricerca sono sei CSV, uno per famiglia di eventi: turni di negoziazione, predizioni
dell'intento, transazioni, memoria episodica, evoluzione del modificatore di prezzo,
istantanee dello stato psico-sociale. Vengono scritti solo quando il logger è configurato, e
sono quelli che `scripts/analisi.py` si aspetta di trovare archiviati per sessione.

---

## 4. Verificare che l'aggancio funzioni

Con `MANTELLA_MERCHANTMIND=1`, all'inizio di una conversazione con un mercante il log di
Mantella deve riportare:

```
MerchantMind enabled for '<nome>' (npc_id=<identificativo>)
```

Se non compare, il personaggio non è stato riconosciuto come mercante: controlla il nome
visualizzato e la biografia. Se compare ma la trattativa non parte, l'errore è nella
costruzione della sessione e viene registrato per esteso nel log.
