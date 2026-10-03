"""Research CSV logger for the user-study metrics.

Writes one CSV per metric family into a configurable directory, appending a row
at each significant state change. It is the "measurable" backbone of the study:
every row is a datum ready for the RQ analyses (section 7.7).

Design, mirroring the existing ``latency_tracker`` pattern:
- a module-level singleton ``research_logger`` that is a **no-op until configured**,
  so importing/calling it from the pure-Python modules (nodes, world_events,
  reflection) has zero side effects unless the feature is actually running;
- ``configure(base_dir)`` turns it on and points it at an output folder;
- ``start_session(player, condition)`` stamps a session id used on every row.

Only the *automatic* logs live here (10 CSVs). The two manual files from the
thesis — ``user_study_questionnaires.csv`` and ``user_study_demographics.csv`` —
are filled by the experimenter, not by the system.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from threading import Lock

# Column order for each CSV. Missing fields at write time become "".
LOG_HEADERS: dict[str, list[str]] = {
    "price_modifier_evolution.csv": [
        "timestamp", "session_id", "player", "npc_id", "trigger", "relationship_stage",
        "affinity", "respect", "suspicion", "gratitude", "price_modifier",
        "base", "trust_bonus", "respect_bonus", "gratitude_bonus",
        "suspicion_penalty", "high_salience_adjustment",
    ],
    "buyer_intent_predictions.csv": [
        "timestamp", "session_id", "player", "npc_id", "turn", "first_utterance",
        "haggle_hard", "accept_quickly", "bundle_interest", "walkaway_likely",
        "intelligence_gathering", "predicted_top", "observed_outcome",
    ],
    "negotiation_turns_log.csv": [
        "timestamp", "session_id", "player", "npc_id", "turn", "role",
        "player_utterance", "offered_price", "stance", "npc_price", "target_price",
        "status", "npc_line",
    ],
    "merchant_transactions_log.csv": [
        "timestamp", "session_id", "player", "npc_id", "item", "base_price",
        "npc_target", "agreed_price", "turns", "outcome",
    ],
    "world_event_propagation_log.csv": [
        "timestamp", "session_id", "player", "event_type", "global_event_id",
        "npc_id", "importance", "decay_rate", "price_modifier_before",
        "price_modifier_after", "reflected",
    ],
    "episodic_memory_log.csv": [
        "timestamp", "session_id", "player", "npc_id", "event_id", "type",
        "description", "importance", "decay_rate", "source", "emotional_impact",
    ],
    "reflection_cycle_log.csv": [
        "timestamp", "session_id", "player", "npc_id", "reflection_id", "trigger",
        "reflection", "confidence", "n_derived", "derived_from",
    ],
    "psychosocial_state_snapshots.csv": [
        "timestamp", "session_id", "player", "npc_id", "trigger", "relationship_stage",
        "affinity", "respect", "suspicion", "gratitude", "price_modifier",
        "n_episodic", "n_reflective", "dominant_emotion",
    ],
    "relationship_stage_transitions.csv": [
        "timestamp", "session_id", "player", "npc_id", "from_stage", "to_stage", "trigger",
    ],
    "anomaly_log.csv": [
        "timestamp", "session_id", "player", "npc_id", "category", "description",
        "turn", "raw_text",
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ResearchLogger:
    """No-op-until-configured CSV logger for the user-study metrics."""

    def __init__(self) -> None:
        self._base_dir: str = ""
        self._session_id: str = ""
        self._player: str = ""
        self._condition: str = ""
        self._lock = Lock()

    # --- lifecycle --------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(self._base_dir)

    def configure(self, base_dir: str) -> None:
        """Turn the logger on and create the output directory."""
        self._base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def start_session(self, player: str = "", condition: str = "") -> str:
        """Stamp a new session id (used on every subsequent row)."""
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._player = player
        self._condition = condition
        return self._session_id

    def set_player(self, player: str) -> None:
        """Set the player name stamped on subsequent rows (single-player)."""
        if player:
            self._player = player

    def disable(self) -> None:
        """Turn logging off (used in tests to isolate)."""
        self._base_dir = ""
        self._session_id = ""
        self._player = ""

    # --- low-level write --------------------------------------------------

    def _write(self, name: str, fields: dict) -> None:
        if not self._base_dir:
            return
        header = LOG_HEADERS[name]
        row = {
            "timestamp": _now(),
            "session_id": self._session_id,
            "player": fields.get("player", self._player),
        }
        row.update(fields)
        ordered = [row.get(col, "") for col in header]
        path = os.path.join(self._base_dir, name)
        # Best-effort: a logging failure must never break the negotiation pipeline.
        try:
            with self._lock:
                new_file = not os.path.exists(path)
                with open(path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if new_file:
                        writer.writerow(header)
                    writer.writerow(ordered)
        except OSError:
            pass

    # --- helpers to read the psycho-social state --------------------------

    @staticmethod
    def _rel(state: dict) -> dict:
        return state.get("relationship_with_player", {})

    @staticmethod
    def _price(state: dict) -> float | str:
        return state.get("merchant_state", {}).get("price_modifier", "")

    # --- typed log methods ------------------------------------------------

    def log_price_snapshot(self, npc_id: str, state: dict, trigger: str) -> None:
        rel = self._rel(state)
        breakdown = state.get("merchant_state", {}).get("price_modifier_breakdown", {})
        self._write("price_modifier_evolution.csv", {
            "npc_id": npc_id, "trigger": trigger,
            "relationship_stage": rel.get("relationship_stage", ""),
            "affinity": rel.get("affinity", ""), "respect": rel.get("respect", ""),
            "suspicion": rel.get("suspicion", ""), "gratitude": rel.get("gratitude", ""),
            "price_modifier": self._price(state),
            "base": breakdown.get("base", ""), "trust_bonus": breakdown.get("trust_bonus", ""),
            "respect_bonus": breakdown.get("respect_bonus", ""),
            "gratitude_bonus": breakdown.get("gratitude_bonus", ""),
            "suspicion_penalty": breakdown.get("suspicion_penalty", ""),
            "high_salience_adjustment": breakdown.get("high_salience_adjustment", ""),
        })

    def log_state_snapshot(self, npc_id: str, state: dict, trigger: str) -> None:
        rel = self._rel(state)
        self._write("psychosocial_state_snapshots.csv", {
            "npc_id": npc_id, "trigger": trigger,
            "relationship_stage": rel.get("relationship_stage", ""),
            "affinity": rel.get("affinity", ""), "respect": rel.get("respect", ""),
            "suspicion": rel.get("suspicion", ""), "gratitude": rel.get("gratitude", ""),
            "price_modifier": self._price(state),
            "n_episodic": len(state.get("episodic_memories", [])),
            "n_reflective": len(state.get("reflective_memory", [])),
            "dominant_emotion": state.get("emotional_state", {}).get("dominant_emotion", ""),
        })

    def log_stage_if_changed(self, npc_id: str, from_stage: str, to_stage: str,
                             trigger: str) -> None:
        if from_stage != to_stage:
            self._write("relationship_stage_transitions.csv", {
                "npc_id": npc_id, "from_stage": from_stage, "to_stage": to_stage,
                "trigger": trigger,
            })

    def log_intent(self, npc_id: str, turn: int, first_utterance: str,
                   distribution: dict) -> None:
        top = max(distribution, key=distribution.get) if distribution else ""
        self._write("buyer_intent_predictions.csv", {
            "npc_id": npc_id, "turn": turn, "first_utterance": first_utterance,
            "haggle_hard": distribution.get("haggle_hard", ""),
            "accept_quickly": distribution.get("accept_quickly", ""),
            "bundle_interest": distribution.get("bundle_interest", ""),
            "walkaway_likely": distribution.get("walkaway_likely", ""),
            "intelligence_gathering": distribution.get("intelligence_gathering", ""),
            "predicted_top": top, "observed_outcome": "",
        })

    def log_turn(self, npc_id: str, turn: int, role: str, *, player_utterance: str = "",
                 offered_price="", stance: str = "", npc_price="", target_price="",
                 status: str = "", npc_line: str = "") -> None:
        self._write("negotiation_turns_log.csv", {
            "npc_id": npc_id, "turn": turn, "role": role,
            "player_utterance": player_utterance, "offered_price": offered_price,
            "stance": stance, "npc_price": npc_price, "target_price": target_price,
            "status": status, "npc_line": npc_line,
        })

    def log_transaction(self, npc_id: str, *, item: str, base_price, npc_target,
                        agreed_price, turns: int, outcome: str) -> None:
        self._write("merchant_transactions_log.csv", {
            "npc_id": npc_id, "item": item, "base_price": base_price,
            "npc_target": npc_target, "agreed_price": agreed_price, "turns": turns,
            "outcome": outcome,
        })

    def log_world_event(self, npc_id: str, *, event_type: str, global_event_id: str,
                        importance, decay_rate, price_before, price_after,
                        reflected: bool) -> None:
        self._write("world_event_propagation_log.csv", {
            "npc_id": npc_id, "event_type": event_type, "global_event_id": global_event_id,
            "importance": importance, "decay_rate": decay_rate,
            "price_modifier_before": price_before, "price_modifier_after": price_after,
            "reflected": reflected,
        })

    def log_episodic(self, npc_id: str, memory: dict) -> None:
        self._write("episodic_memory_log.csv", {
            "npc_id": npc_id, "event_id": memory.get("event_id", ""),
            "type": memory.get("type", ""), "description": memory.get("description", ""),
            "importance": memory.get("importance", ""), "decay_rate": memory.get("decay_rate", ""),
            "source": memory.get("source", ""),
            "emotional_impact": json.dumps(memory.get("emotional_impact", {}), ensure_ascii=False),
        })

    def log_reflection(self, npc_id: str, reflection: dict) -> None:
        derived = reflection.get("derived_from", [])
        self._write("reflection_cycle_log.csv", {
            "npc_id": npc_id, "reflection_id": reflection.get("reflection_id", ""),
            "trigger": reflection.get("trigger", ""), "reflection": reflection.get("reflection", ""),
            "confidence": reflection.get("confidence", ""), "n_derived": len(derived),
            "derived_from": json.dumps(derived, ensure_ascii=False),
        })

    def log_anomaly(self, npc_id: str, *, category: str, description: str,
                    turn="", raw_text: str = "") -> None:
        self._write("anomaly_log.csv", {
            "npc_id": npc_id, "category": category, "description": description,
            "turn": turn, "raw_text": raw_text,
        })


# Module-level singleton (no-op until configure() is called).
research_logger = ResearchLogger()
