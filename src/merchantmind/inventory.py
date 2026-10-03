"""Merchant inventory ingestion.

Vanilla Mantella does not transmit the merchant inventory to the backend; a small
Papyrus serializer sends it so the negotiation can resolve the *real* shop item
and its base price. This module writes that inventory into the NPC's
``merchant_state.shop_inventory_last_seen`` so ``detect_intent_and_item`` and
``appraise_item`` work against authoritative prices.
"""

from __future__ import annotations

from src.merchantmind import store, pricing


def normalise_items(items: list[dict]) -> list[dict]:
    """Coerce raw inventory entries to ``{item_id, base_price, qty}``."""
    normalised = []
    for it in items or []:
        item_id = str(it.get("item_id") or it.get("name") or "").strip()
        if not item_id:
            continue
        try:
            base_price = float(it.get("base_price", it.get("value", 0)) or 0)
        except (TypeError, ValueError):
            base_price = 0.0
        try:
            qty = int(it.get("qty", it.get("count", 1)) or 1)
        except (TypeError, ValueError):
            qty = 1
        normalised.append({"item_id": item_id, "base_price": base_price, "qty": qty})
    return normalised


def update_inventory(base_dir: str, player_name: str, npc_id: str, items: list[dict],
                     npc_meta: dict | None = None) -> dict:
    """Persist the latest seen inventory for a merchant. Returns the NPC state."""
    meta = npc_meta or {}
    npc = store.load_or_create(
        base_dir, player_name, npc_id,
        name=meta.get("name", ""), is_merchant=True,
        race=meta.get("race", ""), role=meta.get("role", "merchant"),
        city=meta.get("city", ""))
    # Guarantee the merchant section exists even if the NPC was created earlier
    # as a non-merchant.
    merchant = npc.setdefault("merchant_state", {})
    merchant["shop_inventory_last_seen"] = normalise_items(items)
    pricing.recompute_derived(npc)
    store.save_state(base_dir, player_name, npc)
    return npc


def find_item(npc: dict, item_name: str) -> dict | None:
    """Resolve an item by (case-insensitive) id against the stored inventory."""
    if not item_name:
        return None
    target = item_name.strip().lower()
    for it in npc.get("merchant_state", {}).get("shop_inventory_last_seen", []):
        if str(it.get("item_id", "")).strip().lower() == target:
            return it
    return None
