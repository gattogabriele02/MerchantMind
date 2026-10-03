Scriptname MantellaAdvancedAction_MerchantTrade extends Quest
{
    MerchantMind custom transaction.

    Executes the exchange at the price agreed by the MerchantGraph, bypassing the
    vanilla barter menu (so the study controls the exact price).

    Dependency-minimal on purpose: it references ONLY vanilla + SKSE + SKSE_HTTP,
    NOT MantellaInterface / MantellaConversation. Those pull in MantellaRepository
    -> MantellaMCM -> SkyUI SDK / UIExtensions sources, which are not needed to run
    the trade and are often not present in an ad-hoc Creation Kit source folder.

    HOW THE MERCHANT IS RESOLVED:
      MantellaConversation dispatches the advanced-action mod event pushing
      _lastNpcToSpeak as the first arg (see MantellaConversation.psc ~L659). The
      trade action is attached to the merchant's closing line, so _lastNpcToSpeak
      == the merchant. Hence "speaker as Actor" is the merchant. (Valid for the
      1:1 merchant negotiation used by the study.)

    ITEM RESOLUTION (by index; language-independent):
      The backend sends "item_index" = the item's position in the merchant's
      seeded inventory. We resolve the Form as TradeItems.GetAt(item_index), so
      no localized display name has to match (Italian vs English). The FormList
      MUST be ordered the same as EXPERIMENT_ITEMS (e.g. [IronSword, RestoreHealth01]
      for [Spada di ferro, Pozione di cura]). If the index is missing/out of range
      we fall back to matching by "item" name via Form.GetName.

    INTEGRATION (Creation Kit — in your own .esp; no master on Mantella needed):
      1. Copy this file into the game's source folder (Data\Source\Scripts) and
         compile it (SKSE source scripts must be on the compile path).
      2. Create a Quest (Start Game Enabled, not Run Once) and attach this script.
      3. Fill ONE property: TradeItems -> a FormList (FLST) of the tradeable items,
         IN THE SAME ORDER as EXPERIMENT_ITEMS.

    Backend side: enabled with env MANTELLA_MERCHANTMIND_TRADE=1
    (see src/merchantmind/transaction.py::build_trade_order).
}

; Full mod-event name = MantellaInterface.EVENT_ADVANCED_ACTIONS_PREFIX + the
; backend action identifier. Hardcoded so we don't reference MantellaInterface.
string property TRADE_EVENT_NAME = \
    "MantellaConversation_Advanced_Action_mantella_npc_merchantmind_trade" auto

int property GOLD_FORMID = 0x0000000F autoReadonly   ; Gold001 (Skyrim.esm)

FormList property TradeItems auto
{Fill in the CK: a FormList of every item the merchants can trade.}

event OnInit()
    RegisterForModEvent(TRADE_EVENT_NAME, "OnMerchantMindTradeReceived")
endEvent

event OnMerchantMindTradeReceived(Form speaker, Form conversationQuest, int argumentsHandle)
    Actor merchant = speaker as Actor
    if !merchant
        return
    endif

    string itemName  = SKSE_HTTP.getString(argumentsHandle, "item")
    int    itemIndex = SKSE_HTTP.getInt(argumentsHandle, "item_index", -1)
    int    price      = SKSE_HTTP.getInt(argumentsHandle, "price")
    int    qty        = SKSE_HTTP.getInt(argumentsHandle, "qty", 1)
    string direction  = SKSE_HTTP.getString(argumentsHandle, "direction", "player_buys")

    ExecuteTrade(merchant, itemName, itemIndex, price, qty, direction)
endEvent

Function ExecuteTrade(Actor merchant, string itemName, int itemIndex, int price, int qty, string direction)
    Actor player = Game.GetPlayer()
    Form gold = Game.GetForm(GOLD_FORMID)
    Form item = ResolveItem(itemIndex, itemName)
    if !item
        Debug.Notification("MerchantMind: unknown item '" + itemName + "'")
        return
    endif

    ; The item is spawned to / removed from the PLAYER directly, so the merchant
    ; does NOT need to physically stock it (simpler for a controlled study). Gold
    ; still moves between player and merchant.
    if direction == "player_sells"
        player.RemoveItem(item, qty, true, merchant)   ; player gives the item
        player.AddItem(gold, price, true)              ; player receives the gold
        Debug.Notification("Sold " + itemName + " for " + price + " gold")
    else ; player_buys
        if player.GetItemCount(gold) < price
            Debug.Notification("Non hai abbastanza oro (servono " + price + ")")
            return
        endif
        player.AddItem(item, qty, true)                ; player receives the item
        player.RemoveItem(gold, price, true, merchant) ; player pays gold to the merchant
        Debug.Notification("Bought " + itemName + " for " + price + " gold")
    endif
EndFunction

; Resolve the item Form from the TradeItems FormList, by index (preferred,
; language-independent) with a fallback to display-name matching. Uses only
; vanilla FormList/Form functions (no SKSE inventory iteration).
Form Function ResolveItem(int itemIndex, string itemName)
    if !TradeItems
        return None
    endif
    int size = TradeItems.GetSize()
    if itemIndex >= 0 && itemIndex < size
        return TradeItems.GetAt(itemIndex)
    endif
    ; Fallback: match by display name.
    int i = 0
    while i < size
        Form f = TradeItems.GetAt(i)
        if f && f.GetName() == itemName
            return f
        endif
        i += 1
    endWhile
    return None
EndFunction
