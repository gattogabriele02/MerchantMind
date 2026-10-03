"""Seeding of the three experiment merchants.

The user study manipulates the merchant's memory as a *pre-loaded* variable:
each participant meets three merchants with a different injected social history —
**admiration**, **distrust**, **neutral** — and negotiates the same two items with
each. This module writes those pre-loaded psycho-social states (history +
inventory) to disk so the study is controlled and comparable across merchants.

Pre-seeding the **inventory** with fixed base prices also makes prices comparable
across merchants (no per-run LLM estimation) — so the objective RQ2 metric works
without the Papyrus inventory serializer.

Pure-Python and store-driven → fully testable.
"""

from __future__ import annotations

from src.merchantmind import schema, store, pricing

# The two standard items every participant haggles for, with the shop prices.
# Italian ids to match Italian-speaking participants (the item resolver matches
# the spoken name against these ids).
EXPERIMENT_ITEMS = [
    {"item_id": "Spada di ferro", "base_price": 50, "qty": 3},
    {"item_id": "Pozione di cura", "base_price": 40, "qty": 5},
]

# One spec per merchant. Relationship values drive `price_modifier` via pricing;
# episodic memories + relationship_summary let the merchant "remember" the story.
EXPERIMENT_MERCHANTS = [
    {
        "npc_id": "belethor", "name": "Belethor", "city": "Whiterun",
        "condition": "admiration",
        "traits": {"agreeableness": 0.6, "greedy": 0.55, "honorable": 0.5},
        "relationship": {"affinity": 0.9, "respect": 0.85, "gratitude": 0.85,
                         "suspicion": 0.0},
        "emotional": {"admiration": 0.6, "trust_toward_player": 0.8},
        "summary": ("Il giocatore ha ucciso il drago alla Torre di Guardia Ovest e "
                    "ha salvato Whiterun. Gli sono grato e mi fido di lui."),
        "reflection": ("Quel viaggiatore ci ha salvati dal drago. Gli devo un "
                       "trattamento di favore."),
        "episodic": [
            {"type": "world_event_global",
             "description": "Il giocatore ha ucciso il drago e ha salvato Whiterun.",
             "emotional_impact": {"admiration": 0.30, "trust_toward_player": 0.15},
             "importance": 0.92, "decay_rate": 0.005, "source": "papyrus_world_listener"},
            {"type": "first_purchase",
             "description": "Il giocatore ha comprato qualche pozione senza tirare sul prezzo.",
             "emotional_impact": {"trust_toward_player": 0.05},
             "importance": 0.30, "decay_rate": 0.07, "source": "merchant_interaction"},
        ],
    },
    {
        "npc_id": "lucan_valerius", "name": "Lucan Valerius", "city": "Riverwood",
        "condition": "distrust",
        "traits": {"agreeableness": 0.4, "greedy": 0.6, "honorable": 0.7},
        "relationship": {"affinity": 0.2, "respect": 0.3, "gratitude": 0.0,
                         "suspicion": 0.75},
        "emotional": {"trust_toward_player": 0.2, "suspicion": 0.6, "irritation": 0.3},
        "summary": ("Il giocatore ha provato a vendermi merce rubata ed è stato visto "
                    "commettere un crimine. Non mi fido di lui."),
        "reflection": ("Devo stare attento con questo qui: ha provato a rifilarmi "
                       "refurtiva. Prezzi pieni, niente sconti."),
        "episodic": [
            {"type": "stolen_goods_sold",
             "description": "Il giocatore ha provato a vendermi oggetti riconosciuti come rubati.",
             "emotional_impact": {"suspicion": 0.25, "trust_toward_player": -0.20},
             "importance": 0.85, "decay_rate": 0.008, "source": "merchant_interaction"},
            {"type": "crime_witnessed",
             "description": "Il giocatore è stato visto commettere un furto a Riverwood.",
             "emotional_impact": {"suspicion": 0.20, "trust_toward_player": -0.10},
             "importance": 0.78, "decay_rate": 0.01, "source": "papyrus_world_listener"},
        ],
    },
    {
        "npc_id": "arcadia", "name": "Arcadia", "city": "Whiterun",
        "condition": "neutral",
        "traits": {"agreeableness": 0.5, "greedy": 0.5, "honorable": 0.5},
        "relationship": {"affinity": 0.5, "respect": 0.5, "gratitude": 0.0,
                         "suspicion": 0.05},
        "emotional": {"trust_toward_player": 0.5},
        "summary": "Cliente occasionale. Nessuna storia particolare tra noi.",
        "reflection": "",
        "episodic": [
            {"type": "first_purchase",
             "description": "Il giocatore ha comprato una pozione di cura.",
             "emotional_impact": {"trust_toward_player": 0.03},
             "importance": 0.25, "decay_rate": 0.075, "source": "merchant_interaction"},
        ],
    },
]


def build_merchant_state(spec: dict) -> dict:
    """Build a fully pre-loaded psycho-social state from a merchant spec."""
    state = schema.new_psychosocial_state(
        spec["npc_id"], spec["name"], is_merchant=True, role="merchant",
        city=spec.get("city", ""))

    state["core_identity"]["personality_traits"].update(spec.get("traits", {}))
    state["emotional_state"].update(spec.get("emotional", {}))

    rel = state["relationship_with_player"]
    rel.update(spec.get("relationship", {}))
    rel["relationship_summary"] = spec.get("summary", "")
    rel["interactions_count"] = len(spec.get("episodic", []))

    for i, ev in enumerate(spec.get("episodic", [])):
        ev = dict(ev)
        ev.setdefault("event_id", f"seed_{spec['npc_id']}_{i}")
        state["episodic_memories"].append(ev)

    if spec.get("reflection"):
        state["reflective_memory"].append({
            "reflection_id": f"seed_ref_{spec['npc_id']}",
            "generated_at": state["last_updated"],
            "trigger": "preloaded_history",
            "reflection": spec["reflection"],
            "confidence": 0.8,
            "derived_from": [m["event_id"] for m in state["episodic_memories"]],
        })

    state["merchant_state"]["shop_inventory_last_seen"] = [dict(it) for it in EXPERIMENT_ITEMS]

    # Derive price_modifier / behaviour / stage from the injected relationship.
    pricing.recompute_derived(state)
    return state


def seed_experiment(base_dir: str, player_name: str,
                    merchants: list[dict] | None = None) -> dict[str, dict]:
    """Write the three pre-loaded merchant states for ``player_name``.

    Returns a mapping ``npc_id -> state``. Overwrites any existing state for those
    merchants (so a session can be reset by re-seeding).
    """
    specs = merchants if merchants is not None else EXPERIMENT_MERCHANTS
    result: dict[str, dict] = {}
    for spec in specs:
        state = build_merchant_state(spec)
        store.save_state(base_dir, player_name, state)
        result[spec["npc_id"]] = state
    return result
