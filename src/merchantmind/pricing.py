"""Derivation of the merchant price modifier, behaviour and relationship stage.

The ``price_modifier`` is never written by hand: it is computed from the
relationship (affinity, respect, suspicion, gratitude) and from high-salience
episodic memories, then cached together with an explicit, auditable breakdown. Transparency of the breakdown is what
makes the ex-post bias audit (section 8.3) possible.

A lower modifier means a better deal for the player. The result is clamped to a
ludically sane band; the floor mirrors the ethical bound that the merchant never
charges below 85% of base price (section 8.2).
"""

from __future__ import annotations

from src.merchantmind.salience import HIGH_SALIENCE_THRESHOLD

# Sensitivity coefficients (kept explicit so they can be tuned / ablated).
TRUST_WEIGHT = 0.10        # affinity -> discount
RESPECT_WEIGHT = 0.07      # respect -> discount
GRATITUDE_WEIGHT = 0.06    # gratitude -> discount
SUSPICION_WEIGHT = 0.30    # suspicion -> surcharge
HIGH_SALIENCE_WEIGHT = 0.05  # per high-salience memory, by emotional valence

PRICE_MODIFIER_FLOOR = 0.85
PRICE_MODIFIER_CEIL = 1.60

# Emotions that, when moved positively, make the NPC more generous vs harsher.
POSITIVE_EMOTIONS = frozenset({"admiration", "trust_toward_player", "gratitude"})
NEGATIVE_EMOTIONS = frozenset({"anger", "fear", "irritation", "suspicion", "stress"})


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _high_salience_adjustment(state: dict) -> float:
    """Net price nudge from high-salience memories, by emotional valence.

    Positive memories (admiration, trust) pull the price down; negative ones
    (suspicion, anger) push it up. Each qualifying memory contributes at most
    ``HIGH_SALIENCE_WEIGHT``.
    """
    total = 0.0
    for memory in state.get("episodic_memories", []):
        if float(memory.get("importance", 0.0)) < HIGH_SALIENCE_THRESHOLD:
            continue
        impact = memory.get("emotional_impact", {}) or {}
        valence = 0.0
        for emotion, delta in impact.items():
            delta = float(delta)
            if emotion in POSITIVE_EMOTIONS:
                valence += delta
            elif emotion in NEGATIVE_EMOTIONS:
                valence -= delta
        if valence > 0:
            total -= HIGH_SALIENCE_WEIGHT
        elif valence < 0:
            total += HIGH_SALIENCE_WEIGHT
    return total


def compute_price_modifier_breakdown(state: dict) -> dict[str, float]:
    """Compute the explicit, auditable breakdown of the price modifier."""
    rel = state.get("relationship_with_player", {})
    breakdown = {
        "base": 1.0,
        "trust_bonus": round(-TRUST_WEIGHT * float(rel.get("affinity", 0.0)), 4),
        "respect_bonus": round(-RESPECT_WEIGHT * float(rel.get("respect", 0.0)), 4),
        "gratitude_bonus": round(-GRATITUDE_WEIGHT * float(rel.get("gratitude", 0.0)), 4),
        "suspicion_penalty": round(SUSPICION_WEIGHT * float(rel.get("suspicion", 0.0)), 4),
        "high_salience_adjustment": round(_high_salience_adjustment(state), 4),
    }
    return breakdown


def compute_price_modifier(state: dict) -> float:
    """Compute the cached price modifier from the breakdown, clamped to band."""
    breakdown = compute_price_modifier_breakdown(state)
    raw = sum(breakdown.values())
    return round(_clamp(raw, PRICE_MODIFIER_FLOOR, PRICE_MODIFIER_CEIL), 4)


def compute_behavior_modifiers(state: dict) -> dict:
    """Derive dialogue tone and haggling dispositions from the relationship."""
    rel = state.get("relationship_with_player", {})
    traits = state.get("core_identity", {}).get("personality_traits", {})
    affinity = float(rel.get("affinity", 0.5))
    respect = float(rel.get("respect", 0.5))
    suspicion = float(rel.get("suspicion", 0.0))

    if suspicion >= 0.5:
        tone = "guarded"
    elif affinity >= 0.7:
        tone = "warm"
    elif affinity <= 0.3:
        tone = "cold"
    else:
        tone = "cordially_guarded" if suspicion >= 0.25 else "neutral"

    greedy = float(traits.get("greedy", 0.5))
    neuroticism = float(traits.get("neuroticism", 0.5))
    agreeableness = float(traits.get("agreeableness", 0.5))
    return {
        "dialogue_tone": tone,
        # Willingness to haggle (concession patience). Grounded in Huang & Hadfi
        # (EMNLP 2024): agreeableness increases concession, so an agreeable merchant
        # haggles over more rounds before walking; greed/respect add pressure.
        "willingness_to_haggle": round(_clamp(
            0.35 + 0.25 * greedy + 0.20 * agreeableness + 0.15 * respect, 0.0, 1.0), 3),
        "greeting_warmth": round(_clamp(affinity - 0.5 * suspicion, 0.0, 1.0), 3),
        # Calmer NPCs tolerate more pressure.
        "tolerance_for_pressure": round(_clamp(0.6 - 0.4 * neuroticism, 0.0, 1.0), 3),
    }


def compute_stage(state: dict) -> str:
    """Map relationship scalars to a coarse relationship stage label."""
    rel = state.get("relationship_with_player", {})
    affinity = float(rel.get("affinity", 0.5))
    respect = float(rel.get("respect", 0.5))
    suspicion = float(rel.get("suspicion", 0.0))

    if suspicion >= 0.6 or affinity <= 0.2:
        return "hostile"
    if suspicion >= 0.35:
        return "wary"
    if affinity >= 0.7 and respect >= 0.6:
        return "trusted_customer"
    if affinity >= 0.55:
        return "acquaintance"
    return "neutral"


def recompute_derived(state: dict) -> dict:
    """Recompute and write back all derived fields. Returns the same state.

    Updates ``merchant_state.price_modifier`` (+ breakdown) when the NPC is a
    merchant, plus ``behavior_modifiers`` and ``relationship_stage`` for any NPC.
    """
    state["behavior_modifiers"] = compute_behavior_modifiers(state)
    state.setdefault("relationship_with_player", {})["relationship_stage"] = compute_stage(state)

    merchant_state = state.get("merchant_state")
    if isinstance(merchant_state, dict):
        merchant_state["price_modifier_breakdown"] = compute_price_modifier_breakdown(state)
        merchant_state["price_modifier"] = compute_price_modifier(state)
    return state
