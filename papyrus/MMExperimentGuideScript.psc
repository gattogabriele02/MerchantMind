Scriptname MMExperimentGuideScript extends Quest
{
    Guida sperimentale MerchantMind — avanzamento AUTOMATICO degli obiettivi.

    Ascolta il mod-event dello scambio MerchantMind: a ogni deal chiuso identifica il
    mercante, conta i deal e — raggiunta la soglia DEALS_PER_MERCHANT — completa
    l'obiettivo mostrando il prossimo.

    REGISTRAZIONE ROBUSTA: la RegisterForModEvent sta in StartListening(), chiamata sia
    da OnInit (partita nuova) sia dal FRAGMENT dello stage 10 (affidabile sui save
    esistenti, dove OnInit non ri-scatta). Nel fragment dello stage 10, aggiungere
    (il cast passa per Quest: due script fratelli non si castano direttamente):
        Quest gq = Self
        (gq as MMExperimentGuideScript).StartListening()

    Le notifiche di debug mostrano in gioco l'avanzamento degli obiettivi.

    Prereq: MANTELLA_MERCHANTMIND_TRADE=1. Property da riempire nel CK:
    AliasLucan/AliasBelethor/AliasArcadia (Reference Alias dei 3 mercanti).
}

ReferenceAlias property AliasLucan auto
ReferenceAlias property AliasBelethor auto
ReferenceAlias property AliasArcadia auto

int property DEALS_PER_MERCHANT = 1 auto
{Quanti deal con un mercante prima di passare al prossimo.}

string property TRADE_EVENT_NAME = \
    "MantellaConversation_Advanced_Action_mantella_npc_merchantmind_trade" auto

int lucanDeals
int belethorDeals
int arcadiaDeals

event OnInit()
    StartListening()
endEvent

; Registra l'ascolto del mod-event. Chiamabile da OnInit E dal fragment dello stage 10.
Function StartListening()
    UnregisterForModEvent(TRADE_EVENT_NAME)
    RegisterForModEvent(TRADE_EVENT_NAME, "OnMerchantTrade")
    Debug.Notification("Guida: in ascolto degli scambi")
EndFunction

event OnMerchantTrade(Form speaker, Form conversationQuest, int argumentsHandle)
    Actor merchant = speaker as Actor
    if !merchant
        return
    endif
    Debug.Notification("Guida: scambio ricevuto")

    if merchant == AliasLucan.GetReference()
        lucanDeals += 1
        if lucanDeals >= DEALS_PER_MERCHANT
            Advance(10, 20)
        endif
    elseif merchant == AliasBelethor.GetReference()
        belethorDeals += 1
        if belethorDeals >= DEALS_PER_MERCHANT
            Advance(20, 30)
        endif
    elseif merchant == AliasArcadia.GetReference()
        arcadiaDeals += 1
        if arcadiaDeals >= DEALS_PER_MERCHANT
            SetObjectiveCompleted(30)
            SetStage(40)
        endif
    else
        Debug.Notification("Guida: mercante NON riconosciuto")
    endif
endEvent

Function Advance(int doneObjective, int nextObjective)
    SetObjectiveCompleted(doneObjective)
    SetObjectiveDisplayed(nextObjective)
    SetStage(nextObjective)
    Debug.Notification("Guida: avanzato all'obiettivo " + nextObjective)
EndFunction
