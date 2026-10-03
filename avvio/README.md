# Strumenti di avvio e di sessione

> **Questi tre file non funzionano da dentro questa cartella.** Vanno copiati nella radice
> del checkout di Mantella, accanto a `main.py` e a `MantellaEnv/`: si orientano rispetto
> alla propria posizione, e da qui non troverebbero né l'interprete né gli script.

| file | che cosa fa |
|---|---|
| `avvia_esperimento.bat` | avvia la sintesi vocale e il backend, con le variabili d'ambiente di MerchantMind |
| `reset_esperimento.bat` | riporta i mercanti allo stato precaricato, per il partecipante successivo |
| `archivia_sessione.ps1` | archivia log, conversazioni e stati di una sessione in `sessioni/<codice>/` |

## L'ordine conta

Fra un partecipante e l'altro: **prima si archivia, poi si resetta.**

Mantella ricarica i riassunti delle conversazioni come contesto, quindi se restano sul disco
il mercante del partecipante successivo si ricorda di quello precedente, e la condizione
sperimentale è compromessa senza che nulla lo segnali. Per questo `archivia_sessione.ps1`
**sposta** le conversazioni invece di copiarle, e `reset_esperimento.bat` si ferma ad
avvisare se ne trova ancora in giro.

```
.\archivia_sessione.ps1 -Codice P02 -Build 2
.\reset_esperimento.bat
.\avvia_esperimento.bat
```

## Da adattare al proprio ambiente

`avvia_esperimento.bat` contiene due percorsi e un nome che valgono per l'installazione su
cui è stato scritto, e vanno cambiati:

- il percorso del server XTTS e del suo ambiente Python;
- l'attesa di 35 secondi per il caricamento del modello vocale, da allungare se la prima
  battuta dà errore;
- il seme della perturbazione (`MANTELLA_MERCHANTMIND_SEED`), che va tolto se si vuole il
  comportamento deterministico.

`reset_esperimento.bat` passa a `seed_experiment.py` il nome del personaggio giocante, che
deve corrispondere **esattamente** a quello in gioco: è la chiave con cui si trova lo stato
dei mercanti su disco.
