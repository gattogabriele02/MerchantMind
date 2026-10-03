"""World event injection.

Game-world events (a slain dragon, a joined faction, a witnessed crime) enter the
merchants' minds and persistently modify their state. This is the mechanism that
*justifies Skyrim*: events are filtered to the relevant NPCs by proximity
(city / faction / impact radius), evaluated for social salience, personalised per
NPC, appended as episodic memories, and — when highly salient — trigger an
immediate reflection so the change is visible at the very next interaction.

Pure-Python and store-driven, so it is fully testable without Skyrim.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from src.merchantmind import store, reflection
from src.merchantmind.salience import evaluate_salience, is_high_salience, make_llm_judge

# Default emotional impact per event type (used if the event carries none).
DEFAULT_IMPACTS: dict[str, dict[str, float]] = {
    "world_event_global": {"admiration": 0.30, "trust_toward_player": 0.15},
    "faction_joined": {"trust_toward_player": 0.10},
    "crime_witnessed": {"suspicion": 0.25, "trust_toward_player": -0.20},
    "quest_helped": {"admiration": 0.15, "trust_toward_player": 0.10},
}

# impact_radius >= this value is treated as affecting every known NPC.
GLOBAL_RADIUS = 2


@dataclass
class WorldEvent:
    """A serialised world event coming from the Papyrus listeners."""
    event_type: str
    description: str = ""
    city: str = ""
    faction: str = ""
    impact_radius: int = 1
    timestamp: str = ""
    global_event_id: str = ""
    emotional_impact: dict = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict) -> "WorldEvent":
        return cls(
            event_type=payload.get("event_type", "world_event_global"),
            description=payload.get("description", ""),
            city=payload.get("city", payload.get("location", "")),
            faction=payload.get("faction", ""),
            impact_radius=int(payload.get("impact_radius", 1) or 1),
            timestamp=payload.get("timestamp", ""),
            global_event_id=payload.get("global_event_id", ""),
            emotional_impact=payload.get("emotional_impact", {}) or {},
        )


def _npc_matches(npc: dict, event: WorldEvent) -> bool:
    """Whether a stored NPC is affected by the event (proximity / faction filter).

    A radius >= GLOBAL_RADIUS reaches everyone. Otherwise the NPC matches if it is
    in the event's faction OR in the event's city (whichever the event specifies).
    An event with neither faction nor city carries no locality info -> everyone.
    """
    if event.impact_radius >= GLOBAL_RADIUS:
        return True

    identity = npc.get("core_identity", {})
    has_criterion = False

    if event.faction:
        has_criterion = True
        npc_faction = (identity.get("faction", "") or "").strip().lower()
        if npc_faction and npc_faction == event.faction.strip().lower():
            return True

    if event.city:
        has_criterion = True
        npc_city = (identity.get("city", "") or "").strip().lower()
        if npc_city and npc_city == event.city.strip().lower():
            return True

    # No locality/faction info on the event -> affects everyone.
    return not has_criterion


def affected_npcs(event: WorldEvent, base_dir: str, player_name: str) -> list[tuple[str, dict]]:
    """Return ``(npc_id, npc_state)`` for every stored NPC the event reaches."""
    result = []
    for npc_id in store.list_npc_ids(base_dir, player_name):
        npc = store.load_state(base_dir, player_name, npc_id)
        if npc and _npc_matches(npc, event):
            result.append((npc_id, npc))
    return result


def _emotional_impact(event: WorldEvent, npc: dict) -> dict:
    if event.emotional_impact:
        return dict(event.emotional_impact)
    return dict(DEFAULT_IMPACTS.get(event.event_type, {"trust_toward_player": 0.05}))


def _personalise(event: WorldEvent, npc: dict) -> str:
    """Render the event from this NPC's point of view (lightweight template)."""
    name = npc.get("core_identity", {}).get("name", "The merchant")
    base = event.description or f"A {event.event_type.replace('_', ' ')} occurred."
    return f"{name} heard that {base[0].lower() + base[1:] if base else base}"


def _apply_relationship_delta(npc: dict, impact: dict) -> None:
    """Nudge relationship scalars in line with the event's emotional impact."""
    rel = npc.setdefault("relationship_with_player", {})
    mapping = {
        "admiration": ("affinity", 1.0),
        "trust_toward_player": ("affinity", 0.5),
        "suspicion": ("suspicion", 1.0),
    }
    for emotion, delta in impact.items():
        if emotion in mapping:
            field_name, weight = mapping[emotion]
            current = float(rel.get(field_name, 0.0))
            rel[field_name] = max(0.0, min(1.0, current + weight * float(delta)))


def propagate(event: WorldEvent, base_dir: str, player_name: str,
              llm=None, reflect: bool = True, llm_judge=None,
              reflect_async: bool = False) -> list[dict]:
    """Inject the event into every affected NPC. Returns a per-NPC report.

    For each affected NPC: evaluate salience, append a personalised episodic
    memory tagged ``source="papyrus_world_listener"``, nudge the relationship,
    recompute derived fields, persist, and — if the salience is high — run a
    reflection (inline, or in a background thread when ``reflect_async``).

    ``llm_judge`` refines salience for socially ambiguous events; if omitted and
    an ``llm`` is supplied, one is derived from it (dormant unless the event type
    is nuanced — the HTTP route passes ``llm=None``, so production is unchanged).
    """
    from src.merchantmind import pricing  # local import to avoid cycle at import time
    from src.merchantmind.research_logger import research_logger
    judge = llm_judge if llm_judge is not None else (make_llm_judge(llm) if llm else None)
    report = []
    for npc_id, npc in affected_npcs(event, base_dir, player_name):
        price_before = npc.get("merchant_state", {}).get("price_modifier", "")
        impact = _emotional_impact(event, npc)
        memory = {
            "event_id": f"evt_{uuid.uuid4().hex[:10]}",
            "timestamp": event.timestamp,
            "type": event.event_type,
            "description": _personalise(event, npc),
            "emotional_impact": impact,
            "source": "papyrus_world_listener",
            "global_event_id": event.global_event_id,
        }
        importance, decay = evaluate_salience(memory, npc, llm_judge=judge)
        memory["importance"] = round(importance, 4)
        memory["decay_rate"] = round(decay, 4)
        npc.setdefault("episodic_memories", []).append(memory)

        _apply_relationship_delta(npc, impact)
        pricing.recompute_derived(npc)

        needs_reflection = reflect and is_high_salience(importance)
        reflected = False
        if needs_reflection and not reflect_async:
            reflection.run_reflection(npc, llm=llm, trigger="high_salience_event")
            reflected = True

        store.save_state(base_dir, player_name, npc)

        if needs_reflection and reflect_async:
            # Reflect off the request path; it reloads + saves the NPC itself.
            reflection.reflect_in_background(base_dir, player_name, npc_id, llm=llm,
                                             trigger="high_salience_event")
            reflected = True  # scheduled

        # Research logging (no-op unless configured).
        price_after = npc.get("merchant_state", {}).get("price_modifier", "")
        research_logger.log_world_event(
            npc_id, event_type=event.event_type, global_event_id=event.global_event_id,
            importance=round(importance, 4), decay_rate=round(decay, 4),
            price_before=price_before, price_after=price_after, reflected=reflected)
        research_logger.log_episodic(npc_id, memory)
        research_logger.log_price_snapshot(npc_id, npc, "world_event")
        report.append({
            "npc_id": npc_id,
            "importance": round(importance, 4),
            "reflected": reflected,
            "price_modifier": npc.get("merchant_state", {}).get("price_modifier"),
        })
    return report
