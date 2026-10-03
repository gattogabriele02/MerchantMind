"""Custom transaction — the real in-game exchange.

The vanilla barter menu computes prices with its own formula and gives us no
control or visibility over the price — which is the very object of this study.
So once the MerchantGraph produces an ``agreed_price`` we bypass the menu and
execute the swap via a Papyrus function ``ExecuteCustomTrade`` (the NPC removes
the item and hands it over, the player pays the agreed gold).

This module is the *backend* half: it builds the structured command payload the
game executes, and records the completed trade into the merchant's
``transaction_history`` (feeding the buyer-intent prior of future negotiations).
The Papyrus half lives in ``papyrus/MantellaMerchantMind.psc``.
"""

from __future__ import annotations

from src.merchantmind import store

# Action identifier the game-side handler listens for. The game dispatches any
# identifier via a mod event (EVENT_ADVANCED_ACTIONS_PREFIX + identifier), so the
# Papyrus handler script MantellaAdvancedAction_MerchantMindTrade.psc just needs
# to register for this. See papyrus/README.md.
ACTION_EXECUTE_TRADE = "mantella_npc_merchantmind_trade"


def build_trade_order(npc_name: str, item_name: str, agreed_price: float,
                      qty: int = 1, direction: str = "player_buys",
                      item_index: int = -1) -> dict:
    """Build the game action that executes the exchange at the agreed price.

    Shape matches Mantella's action protocol: ``{"identifier", "arguments"}``,
    where ``arguments`` is read game-side via ``SKSE_HTTP.getString/getInt``.
    ``source`` is the NPC **display name**. ``item_index`` is the position in the
    merchant's seeded inventory; the Papyrus handler resolves the item Form from a
    FormList by that index (language-independent), falling back to ``item`` name.
    ``direction`` is ``player_buys`` (NPC -> player, player pays gold) or
    ``player_sells``.
    """
    return {
        "identifier": ACTION_EXECUTE_TRADE,
        "arguments": {
            "source": npc_name,
            "item": item_name,
            "item_index": int(item_index),
            "price": int(round(float(agreed_price))),   # gold is integer in-game
            "qty": int(qty),
            "direction": direction,
        },
    }


def record_completed_trade(base_dir: str, player_name: str, npc_id: str, *,
                           item_name: str, base_price: float, agreed_price: float,
                           npc_target: float | None = None, turns: int = 0,
                           outcome: str = "deal") -> dict:
    """Append a completed/abandoned trade to ``transaction_history`` and refresh
    the summary. Returns the NPC state. (No relationship deltas here — those are
    applied by the negotiation's ``update_psychosocial_state`` node.)
    """
    npc = store.load_or_create(base_dir, player_name, npc_id, is_merchant=True)
    merchant = npc.setdefault("merchant_state", {})
    if outcome == "deal":
        merchant.setdefault("transaction_history", []).append({
            "item": item_name,
            "base_price": base_price,
            "npc_target": npc_target,
            "agreed_price": round(float(agreed_price), 2),
            "turns": turns,
            "outcome": "deal",
        })
    merchant["last_negotiation_outcome"] = outcome
    _refresh_summary(merchant)
    store.save_state(base_dir, player_name, npc)
    return npc


def _refresh_summary(merchant: dict) -> None:
    history = merchant.get("transaction_history", [])
    deals = [t for t in history if t.get("outcome") == "deal"]
    total = len(history)
    summary = merchant.setdefault("transaction_history_summary", {})
    summary["total_transactions"] = total
    summary["total_gold_spent_by_player"] = sum(t.get("agreed_price", 0) or 0 for t in deals)
    if deals:
        summary["average_haggle_turns"] = round(sum(t.get("turns", 0) for t in deals) / len(deals), 2)
    summary["deal_rate"] = round(len(deals) / total, 3) if total else 0.0
    summary["walkaway_rate"] = round(1 - (len(deals) / total), 3) if total else 0.0
