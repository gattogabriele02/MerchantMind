"""Social salience evaluation and differential decay.

Implements the hybrid rule-based / LLM-judge salience model from the design doc, inspired by ACT-R style activation: every event
receives an ``importance`` (how much it counts) and a ``decay_rate`` (how fast it
is forgotten). High-importance events decay slowly, so emotionally significant
moments (a slain dragon, a betrayal) stay salient across sessions while everyday
noise fades.

The rule-based path is free and deterministic. An optional ``llm_judge`` callable
can be supplied to refine scores for socially ambiguous event types only, keeping
LLM cost bounded.
"""

from __future__ import annotations

from typing import Callable

# Base importance weight per event type.
TYPE_BASE_WEIGHTS: dict[str, float] = {
    # Merchant interaction events
    "first_purchase": 0.30,
    "negotiation_hard": 0.40,
    "negotiation_walkaway": 0.55,
    "stolen_goods_sold": 0.80,
    "trade_above_avg": 0.35,
    "gift_to_npc": 0.65,
    # Injected world events
    "world_event_global": 0.85,
    "faction_joined": 0.70,
    "crime_witnessed": 0.75,
    "quest_helped": 0.60,
    # LLM anomalies (tracked but low salience)
    "llm_anomaly_detected": 0.10,
}

DEFAULT_BASE_WEIGHT = 0.30

# Event types where an LLM judge (if provided) refines the rule-based score.
NUANCED_TYPES = frozenset({"stolen_goods_sold", "betrayal", "rescue"})

# Salience above which a state change is considered immediately reflection-worthy.
HIGH_SALIENCE_THRESHOLD = 0.80

LlmJudge = Callable[[dict, dict], float]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def evaluate_salience(event: dict, npc_state: dict,
                      llm_judge: LlmJudge | None = None) -> tuple[float, float]:
    """Return ``(importance, decay_rate)`` for an event given the NPC's state.

    Args:
        event: Episodic event dict. Uses ``type`` and ``emotional_impact``.
        npc_state: The NPC psycho-social state (for personality modulation).
        llm_judge: Optional callable ``(event, npc_state) -> score in [0, 1]``
            used only for nuanced event types to refine the rule-based score.
    """
    event_type = event.get("type", "")
    base = TYPE_BASE_WEIGHTS.get(event_type, DEFAULT_BASE_WEIGHT)

    traits = npc_state.get("core_identity", {}).get("personality_traits", {})

    # Personality modulation: an honourable NPC remembers betrayals more.
    if event_type == "stolen_goods_sold":
        base *= (1.0 + traits.get("honorable", 0.0))

    # Emotional impact modulation: bigger emotional swings are more memorable.
    impact = event.get("emotional_impact", {}) or {}
    impact_magnitude = sum(abs(float(v)) for v in impact.values())
    importance = _clamp(base + 0.3 * impact_magnitude)

    # Optional LLM-judge refinement for socially ambiguous events.
    if llm_judge is not None and event_type in NUANCED_TYPES:
        llm_score = _clamp(float(llm_judge(event, npc_state)))
        importance = 0.5 * importance + 0.5 * llm_score

    # Differential decay: high importance -> slow forgetting.
    decay_rate = max(0.005, 0.10 * (1.0 - importance))
    return importance, decay_rate


def make_llm_judge(llm) -> LlmJudge:
    """Build an ``(event, npc_state) -> score in [0,1]`` judge backed by an LLM.

    Used only for :data:`NUANCED_TYPES` (see :func:`evaluate_salience`), so socially
    ambiguous events (a stolen-goods sale, a betrayal) get a model-refined salience
    while everyday events stay on the free rule-based path. Fail-safe: any error
    returns 0.0 so the rule-based score prevails.
    """
    def judge(event: dict, npc_state: dict) -> float:
        name = npc_state.get("core_identity", {}).get("name", "the merchant")
        try:
            raw = llm.json(
                system=("You rate how socially significant an event is for a shopkeeper's "
                        "long-term memory of a customer. Output strictly "
                        '{"salience": <number 0..1>}.'),
                user=(f"Shopkeeper: {name}. Event ({event.get('type', '')}): "
                      f"{event.get('description', '')}. How salient is it (0=forgettable, "
                      "1=unforgettable)?"),
                label="mm_llm_salience")
            return _clamp(float(raw.get("salience", 0.0)))
        except Exception:
            return 0.0
    return judge


def is_high_salience(importance: float,
                     threshold: float = HIGH_SALIENCE_THRESHOLD) -> bool:
    """Whether an importance score warrants an immediate reflection."""
    return importance >= threshold


def decayed_importance(memory: dict, elapsed_days: float) -> float:
    """Importance of a memory after ``elapsed_days`` of differential decay.

    Uses geometric decay ``importance * (1 - decay_rate) ** days`` with a small
    floor so genuinely formative memories never vanish entirely.
    """
    importance = float(memory.get("importance", 0.0))
    decay_rate = float(memory.get("decay_rate", 0.05))
    if elapsed_days <= 0:
        return importance
    faded = importance * ((1.0 - decay_rate) ** elapsed_days)
    return max(0.0, faded)
