# MerchantMind — integrazione Papyrus (lato-mod)

Come integrare lo **scambio reale** oro/oggetto nella mod **Mantella-Spell** (clonata in
`c:\Mantella-Spell`). Basato sull'analisi del meccanismo reale di Mantella-Spell
(SKSE_HTTP + azioni via mod-event).

## Come funziona (meccanismo scoperto nel sorgente)
- Il gioco comunica col backend via **`SKSE_HTTP`** (plugin SKSE già presente in
  `Mantella-Spell/SKSE/Plugins/SKSE_HTTP.dll`).
- Il backend, nella risposta, allega **azioni** come `{ "identifier": ..., "arguments": {...} }`.
- `MantellaConversation.psc` smista **qualsiasi** identifier: fa scattare il mod-event
  `EVENT_ADVANCED_ACTIONS_PREFIX + identifier` passando un `argumentsHandle`. **Non c'è
  allow-list lato gioco** → basta uno script che si registri per quell'evento.

## L'unica cosa necessaria per l'esperimento: l'azione di scambio

**File:** [MantellaAdvancedAction_MerchantTrade.psc](MantellaAdvancedAction_MerchantTrade.psc)

Esegue lo scambio al prezzo concordato dal MerchantGraph. Il backend emette l'azione
`mantella_npc_merchantmind_trade` (vedi `src/merchantmind/transaction.py`) quando c'è un
`deal` **e** l'env `MANTELLA_MERCHANTMIND_TRADE=1` è impostato.

> **Versione dependency-minimal.** Lo script referenzia **solo** vanilla + SKSE + `SKSE_HTTP`
> (niente `MantellaInterface`/`MantellaConversation`, che tirerebbero dentro `MantellaMCM` →
> sorgenti SkyUI SDK / UIExtensions, spesso assenti). Risolve il mercante da `speaker`
> (= `_lastNpcToSpeak`, l'NPC che ha pronunciato la battuta di chiusura) e prende player/oro a
> runtime (`Game.GetPlayer()`, `Game.GetForm(0xF)`). → **nessuna proprietà da compilare**.

### Prerequisito di compilazione: i sorgenti sul path
Il compilatore del CK deve trovare, nella cartella source del gioco (`Data\Source\Scripts`):
- i sorgenti **vanilla** (di norma già presenti),
- i sorgenti **SKSE** (`ModEvent.psc`, `Form.psc` con `RegisterForModEvent`, ecc.) — copiali da
  `<MO2>\mods\Skyrim Script Extender (SKSE64)\Scripts\Source\`,
- `SKSE_HTTP.psc` (dai sorgenti di Mantella-Spell).

### Passi di integrazione (Creation Kit)
1. Copia `MantellaAdvancedAction_MerchantTrade.psc` in `...\Skyrim Special Edition\Data\Source\Scripts\`
   (la stessa cartella dove il CK legge i sorgenti — **non** il repo).
2. `Gameplay → Papyrus Script Manager` → seleziona `MantellaAdvancedAction_MerchantTrade` → **Compile**.
3. Nel **tuo** `.esp` (o in `Mantella.esp`): crea una **Quest** (es. `MMTradeHandler`, *Start Game
   Enabled*, *Run Once* off) e **allega** questo script.
4. **Nessuna proprietà** da compilare (player e oro sono risolti a runtime).
5. Salva l'`.esp`. Fatto: l'handler si registra da solo all'avvio partita.

### Attivazione lato backend
```
set MANTELLA_MERCHANTMIND=1
set MANTELLA_MERCHANTMIND_TRADE=1
python main.py
```

### Come combaciano gli oggetti
Il backend manda il **nome** dell'oggetto (dall'inventario pre-caricato, es. *Spada di ferro*).
Lo script cerca nell'inventario del mercante l'oggetto con quel `GetName()` (confronto
case-insensitive) → assicurati che i nomi nel seeding
(`src/merchantmind/experiment.py::EXPERIMENT_ITEMS`) **coincidano con i nomi in-game** nella
lingua che usi (italiano).

## Quest-guida ad avanzamento automatico (esperimento)

**File:** [MMExperimentGuideScript.psc](MMExperimentGuideScript.psc) — da allegare alla quest
`MMExperimentGuide`. Si registra allo **stesso** mod-event dello scambio
(`mantella_npc_merchantmind_trade`): a ogni deal chiuso identifica il mercante (via i 3 alias
`AliasLucan/AliasBelethor/AliasArcadia`) e **completa l'obiettivo giusto mostrando il successivo**, senza
comandi console. Più script possono registrarsi allo stesso evento → il trade handler esegue lo scambio,
questo avanza la quest, in modo indipendente.

- **Prerequisito:** `MANTELLA_MERCHANTMIND_TRADE=1` (l'evento scatta alla chiusura del *deal*). Su walk-away
  non scatta → avanza a mano come fallback.
- **Compilazione:** come la trade action (stessa cartella source + sorgenti SKSE per `RegisterForModEvent`).
- **Setup CK completo:** vedi [../esperimento/environment_ck.md](../esperimento/environment_ck.md) §6c
  (alias, objectives con Target=alias, property da riempire).

## Opzionale (NON serve per l'esperimento)
**File:** [MantellaMerchantMind.psc](MantellaMerchantMind.psc) — helper per inviare l'inventario
reale (`/merchant_inventory`) e gli eventi del mondo (`/world_event`) **automaticamente** dal
gioco. Per l'esperimento **non servono** (inventario pre-caricato dal seeding; evento drago
iniettato con `scripts/inject_world_event.py`). Contengono un caveat sul routing delle reply —
vedi il file.

## Riepilogo endpoint backend
- Azione `mantella_npc_merchantmind_trade` → gestita da `MantellaAdvancedAction_MerchantTrade.psc`.
- `POST /world_event`, `POST /merchant_inventory` → forniti da
  `src/http/routes/world_event_route.py` (attivi se `MANTELLA_MERCHANTMIND=1`).
