"""Asynchronous reflection cycle.

Turns a *list of facts* (episodic memories) into an *attitude*: a prospective
reflection synthesises recent high-salience memories into a new
``reflective_memory`` entry, a retrospective reflection rewrites the
``relationship_summary``, and the derived fields (price_modifier, behaviour,
stage) are recomputed.

It runs outside the voice critical path. The synthesis is LLM-driven when an LLM
is supplied (the injectable :class:`NegotiationLLM`), with a deterministic
rule-based fallback so the cycle — and its triggers — are fully unit testable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from src.merchantmind import pricing
from src.merchantmind.salience import HIGH_SALIENCE_THRESHOLD

# Trigger thresholds (section 5.6).
NEW_MEMORIES_TRIGGER = 5
TIME_TRIGGER = timedelta(hours=2)
PROSPECTIVE_TOP_K = 5


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _reflection_bookkeeping(npc: dict) -> dict:
    return npc.setdefault("reflection_state", {
        "last_reflection_at": None,
        "episodic_count_at_last": 0,
    })


def _ensure_event_ids(memories: list) -> None:
    for mem in memories:
        if not mem.get("event_id"):
            mem["event_id"] = f"evt_{uuid.uuid4().hex[:10]}"


def should_reflect(npc: dict, now: datetime | None = None) -> tuple[bool, str]:
    """Whether a reflection is due, and which trigger fired.

    Triggers: >=5 new memories since last reflection, >2h elapsed, or a single
    high-salience (>0.80) memory appeared since the last reflection.
    """
    book = _reflection_bookkeeping(npc)
    memories = npc.get("episodic_memories", [])
    new_count = len(memories) - int(book.get("episodic_count_at_last", 0))

    if new_count >= NEW_MEMORIES_TRIGGER:
        return True, "5_new_episodic_memories"

    # A high-salience event among the new memories forces an immediate reflection.
    for mem in memories[int(book.get("episodic_count_at_last", 0)):]:
        if float(mem.get("importance", 0.0)) >= HIGH_SALIENCE_THRESHOLD:
            return True, "high_salience_event"

    last_at = _parse_iso(book.get("last_reflection_at") or "")
    if last_at is None:
        # Never reflected: reflect once there is at least one memory.
        if memories:
            return True, "first_reflection"
    elif _now(now) - last_at > TIME_TRIGGER and new_count > 0:
        return True, "time_elapsed"
    return False, ""


def _top_k_by_salience(memories: list, k: int) -> list:
    return sorted(memories, key=lambda m: float(m.get("importance", 0.0)), reverse=True)[:k]


def _rule_based_insight(npc: dict, recent: list) -> tuple[str, float]:
    """Deterministic fallback insight when no LLM is supplied."""
    name = npc.get("core_identity", {}).get("name", "The merchant")
    rel = npc.get("relationship_with_player", {})
    stage = rel.get("relationship_stage", "neutral")
    notable = recent[0]["description"] if recent else "no notable events"
    text = (f"{name} sees the player as a {stage.replace('_', ' ')}. "
            f"Most salient recently: {notable}")
    confidence = round(min(0.9, 0.5 + 0.1 * len(recent)), 2)
    return text, confidence


def _llm_insight(llm, npc: dict, recent: list) -> tuple[str, float]:
    identity = npc.get("core_identity", {})
    rel = npc.get("relationship_with_player", {})
    events = "; ".join(m.get("description", "") for m in recent) or "none"
    text = llm.text(
        system=(f"You are reflecting privately as {identity.get('name', 'a merchant')}, a "
                f"{identity.get('role', 'merchant')}. In ONE sentence, synthesise how you now "
                "feel about this customer. No narration."),
        user=(f"Current relationship: {rel.get('relationship_summary', 'a customer')}. "
              f"Recent notable events: {events}."),
        label="mm_llm_reflect",
    ).strip()
    if not text:
        return _rule_based_insight(npc, recent)
    return text, 0.75


def run_reflection(npc: dict, llm=None, now: datetime | None = None,
                   trigger: str = "manual") -> dict:
    """Run one reflection cycle in place and return the NPC state.

    1. Prospective: synthesise top-k recent memories into a ``reflective_memory``.
    2. Retrospective: rewrite ``relationship_summary``.
    3. Recompute derived fields and update bookkeeping.
    """
    memories = npc.get("episodic_memories", [])
    _ensure_event_ids(memories)
    recent = _top_k_by_salience(memories, PROSPECTIVE_TOP_K)

    if llm is not None:
        insight_text, confidence = _llm_insight(llm, npc, recent)
    else:
        insight_text, confidence = _rule_based_insight(npc, recent)

    entry = {
        "reflection_id": f"ref_{uuid.uuid4().hex[:10]}",
        "generated_at": _now(now).replace(microsecond=0).isoformat(),
        "trigger": trigger,
        "reflection": insight_text,
        "confidence": confidence,
        "derived_from": [m["event_id"] for m in recent],
    }
    npc.setdefault("reflective_memory", []).append(entry)

    # Retrospective: the relationship summary becomes the freshest reflection,
    # anchored on the current stage.
    rel = npc.setdefault("relationship_with_player", {})
    rel["relationship_summary"] = insight_text

    pricing.recompute_derived(npc)

    book = _reflection_bookkeeping(npc)
    book["last_reflection_at"] = _now(now).replace(microsecond=0).isoformat()
    book["episodic_count_at_last"] = len(memories)

    # Research logging (no-op unless configured).
    from src.merchantmind.research_logger import research_logger
    research_logger.log_reflection(npc.get("npc_id", ""), entry)
    return npc


def maybe_reflect(npc: dict, llm=None, now: datetime | None = None) -> tuple[bool, dict]:
    """Reflect only if a trigger fires. Returns ``(reflected, npc)``."""
    due, trigger = should_reflect(npc, now)
    if due:
        run_reflection(npc, llm=llm, now=now, trigger=trigger)
    return due, npc


def _reflect_and_save(base_dir: str, player_name: str, npc_id: str,
                      llm=None, trigger: str = "high_salience_event") -> bool:
    """Load an NPC, run one reflection, persist it. Returns whether it ran.

    Synchronous worker behind :func:`reflect_in_background` — kept separate so it
    is unit testable without threads. Reloads the NPC so it never races with the
    caller's own save of the same file.
    """
    from src.merchantmind import store
    npc = store.load_state(base_dir, player_name, npc_id)
    if npc is None:
        return False
    run_reflection(npc, llm=llm, trigger=trigger)
    store.save_state(base_dir, player_name, npc)
    return True


def reflect_in_background(base_dir: str, player_name: str, npc_id: str,
                          llm=None, trigger: str = "high_salience_event") -> None:
    """Run a reflection off the critical path, in a daemon thread (fail-safe)."""
    import threading

    def worker() -> None:
        try:
            _reflect_and_save(base_dir, player_name, npc_id, llm=llm, trigger=trigger)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()
