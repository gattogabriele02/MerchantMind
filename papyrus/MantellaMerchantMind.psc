Scriptname MantellaMerchantMind extends Quest
{
    MerchantMind OPTIONAL game-side senders.

    ⚠️ OPZIONALI — NON servono per l'esperimento:
      - l'inventario dei 3 mercanti è PRE-CARICATO dal seeding (prezzi fissi);
      - gli eventi del mondo (drago) si iniettano dall'esterno con
        scripts/inject_world_event.py.
    Questi helper servono solo se in futuro vuoi l'automazione completa in-game.

    L'azione di scambio REALE (l'unica cosa Papyrus necessaria per l'esperimento)
    è in MantellaAdvancedAction_MerchantMindTrade.psc, NON qui.

    ⚠️ Caveat tecnico: SKSE_HTTP.sendLocalhostHttpRequest fa scattare l'evento
    "SKSE_HTTP_OnHttpReplyReceived" che MantellaConversation gestisce come reply di
    conversazione. Invia questi eventi SOLO fuori da una conversazione attiva, per
    non interferire con lo scambio richiesta/risposta in corso.
}

MantellaConstants property mConsts auto
MantellaRepository property repository auto
Actor property PlayerRef auto

; ---------------------------------------------------------------------------
; 1. INVENTORY SERIALIZER  ->  POST /merchant_inventory  (opzionale)
; ---------------------------------------------------------------------------
Function SerializeMerchantInventory(Actor akMerchant, string asNpcId)
    int handle = SKSE_HTTP.createDictionary()
    SKSE_HTTP.setString(handle, "player_name", PlayerRef.GetDisplayName())
    SKSE_HTTP.setString(handle, "npc_id", asNpcId)

    int n = akMerchant.GetNumItems()
    int[] items = new int[128]
    int count = 0
    int i = 0
    while i < n && count < 128
        Form f = akMerchant.GetNthForm(i)
        if f && f.GetGoldValue() > 0
            int itemDict = SKSE_HTTP.createDictionary()
            SKSE_HTTP.setString(itemDict, "item_id", f.GetName())
            SKSE_HTTP.setInt(itemDict, "base_price", f.GetGoldValue())
            SKSE_HTTP.setInt(itemDict, "qty", akMerchant.GetItemCount(f))
            items[count] = itemDict
            count += 1
        endif
        i += 1
    endWhile

    int[] trimmed = Utility.ResizeIntArray(items, count)
    SKSE_HTTP.setNestedDictionariesArray(handle, "items", trimmed)
    SKSE_HTTP.sendLocalhostHttpRequest(handle, repository.HttpPort, "merchant_inventory")
EndFunction

; ---------------------------------------------------------------------------
; 2. WORLD EVENT SENDER  ->  POST /world_event  (opzionale)
; ---------------------------------------------------------------------------
Function SendWorldEvent(string asEventType, string asDescription, string asCity, int aiImpactRadius)
    int event = SKSE_HTTP.createDictionary()
    SKSE_HTTP.setString(event, "event_type", asEventType)
    SKSE_HTTP.setString(event, "description", asDescription)
    if asCity != ""
        SKSE_HTTP.setString(event, "city", asCity)
    endif
    SKSE_HTTP.setInt(event, "impact_radius", aiImpactRadius)

    int handle = SKSE_HTTP.createDictionary()
    SKSE_HTTP.setString(handle, "player_name", PlayerRef.GetDisplayName())
    SKSE_HTTP.setNestedDictionary(handle, "event", event)
    SKSE_HTTP.sendLocalhostHttpRequest(handle, repository.HttpPort, "world_event")
EndFunction

; Esempi di listener (da agganciare a un magic effect / story manager nel CK):
Event OnDragonKilled(Location akLocation)
    SendWorldEvent("world_event_global", \
        "il giocatore ha ucciso un drago a " + akLocation.GetName() + ".", "", 2)
EndEvent
