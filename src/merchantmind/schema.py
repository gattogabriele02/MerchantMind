"""Schema and default factories for the per-NPC psycho-social state.

This module defines the structure of the unified per-NPC JSON described in the
thesis design. The state is kept as plain
``dict`` objects so it serialises cleanly to JSON and stays decoupled from the
rest of the Mantella code base. ``merchant_state`` is optional: it is only
instantiated for NPCs whose role is ``merchant``.

The module is intentionally dependency-free (standard library only) so the
psycho-social "engine" can be unit tested without Skyrim, an LLM or any network.
"""

from __future__ import annotations

from datetime import datetime, timezone

SCHEMA_VERSION = "2.0-unified"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_personality_traits() -> dict[str, float]:
    """Neutral Big-Five (+ two trade-relevant traits) personality vector."""
    return {
        "agreeableness": 0.5,
        "extraversion": 0.5,
        "conscientiousness": 0.5,
        "neuroticism": 0.5,
        "openness": 0.5,
        "greedy": 0.5,
        "honorable": 0.5,
    }


def new_emotional_state() -> dict:
    return {
        "anger": 0.0,
        "fear": 0.0,
        "trust_toward_player": 0.5,
        "stress": 0.0,
        "admiration": 0.0,
        "irritation": 0.0,
        "last_updated": _now_iso(),
        "dominant_emotion": "trust",
    }


def new_relationship() -> dict:
    return {
        "affinity": 0.5,
        "respect": 0.5,
        "fear": 0.0,
        "suspicion": 0.0,
        "gratitude": 0.0,
        "relationship_stage": "neutral",
        "relationship_summary": "",
        "first_met": _now_iso(),
        "interactions_count": 0,
    }


def new_merchant_state() -> dict:
    return {
        "shop_inventory_last_seen": [],
        "price_modifier": 1.0,
        "price_modifier_breakdown": {},
        "transaction_history_summary": {
            "total_transactions": 0,
            "total_gold_spent_by_player": 0,
            "average_haggle_turns": 0.0,
            "deal_rate": 0.0,
            "walkaway_rate": 0.0,
        },
        "transaction_history": [],
        "predicted_buyer_archetype": "unknown",
        "last_negotiation_outcome": None,
    }


def new_psychosocial_state(npc_id: str, name: str = "", *, is_merchant: bool = False,
                           race: str = "", role: str = "", city: str = "") -> dict:
    """Create a fresh psycho-social state for an NPC.

    Args:
        npc_id: Stable identifier for the NPC (e.g. ``"belethor_whiterun"``).
        name: Display name of the NPC.
        is_merchant: When True a ``merchant_state`` section is instantiated.
        race / role / city: Optional identity fields.
    """
    state: dict = {
        "npc_id": npc_id,
        "schema_version": SCHEMA_VERSION,
        "last_updated": _now_iso(),
        "core_identity": {
            "name": name or npc_id,
            "race": race,
            "role": role or ("merchant" if is_merchant else ""),
            "city": city,
            "faction": "",
            "shop": "",
            "personality_traits": new_personality_traits(),
            "moral_values": {"lawfulness": 0.5, "loyalty_to_jarl": 0.5},
        },
        "emotional_state": new_emotional_state(),
        "relationship_with_player": new_relationship(),
        "episodic_memories": [],
        "reflective_memory": [],
        "goals": [],
        "behavior_modifiers": {
            "dialogue_tone": "neutral",
            "willingness_to_haggle": 0.5,
            "greeting_warmth": 0.5,
            "tolerance_for_pressure": 0.5,
        },
    }
    if is_merchant:
        state["merchant_state"] = new_merchant_state()
    return state


def is_merchant(state: dict) -> bool:
    """Return True if the state carries an instantiated ``merchant_state``."""
    return isinstance(state.get("merchant_state"), dict)


def touch(state: dict) -> None:
    """Update the top-level ``last_updated`` timestamp in place."""
    state["last_updated"] = _now_iso()
