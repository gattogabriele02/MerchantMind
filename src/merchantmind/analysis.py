"""Post-processing of the research logs for RQ1 (buyer-intent accuracy).

``predict_buyer_intent`` writes a predicted intent distribution at the start of
each negotiation, with an empty ``observed_outcome`` column. This module fills
that column *after the fact* by looking at what the buyer actually did in the
same session (from the transaction / turns logs) and mapping it to the closest
intent label, so predicted-vs-observed pairs can feed an F1 score.

The mapping is a documented heuristic (buyer behaviour is not a clean 1:1 of the
five intent labels — ``bundle_interest`` in particular is not observable from the
single-item logs, so it is never assigned). Pure standard-library, so testable on
synthetic CSVs; it reads real rows only when pointed at a real logs directory.
"""

from __future__ import annotations

import csv
import os

HAGGLE_HARD_MIN_TURNS = 2  # >= this many player turns before a deal => haggled hard


def map_outcome_to_intent(outcome: str, turns: int) -> str:
    """Map an observed negotiation outcome to the closest buyer-intent label.

    - walkaway                       -> ``walkaway_likely``
    - deal after >= 2 player turns   -> ``haggle_hard``
    - deal after <= 1 player turn    -> ``accept_quickly``
    - anything else (browse / none)  -> ``intelligence_gathering``
    (``bundle_interest`` is not observable from single-item logs.)
    """
    outcome = (outcome or "").lower()
    if outcome == "walkaway":
        return "walkaway_likely"
    if outcome == "deal":
        return "haggle_hard" if int(turns or 0) >= HAGGLE_HARD_MIN_TURNS else "accept_quickly"
    return "intelligence_gathering"


def _index_outcomes(logs_dir: str) -> dict[tuple[str, str], dict]:
    """Build ``(session_id, npc_id) -> {outcome, turns}`` from the logs.

    Prefers the transactions log (has turns + outcome); falls back to the final
    status in the turns log for walkaways that never produced a transaction row.
    """
    outcomes: dict[tuple[str, str], dict] = {}

    tx_path = os.path.join(logs_dir, "merchant_transactions_log.csv")
    if os.path.exists(tx_path):
        with open(tx_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row.get("session_id", ""), row.get("npc_id", ""))
                outcomes[key] = {"outcome": row.get("outcome", ""),
                                 "turns": _to_int(row.get("turns"))}

    turns_path = os.path.join(logs_dir, "negotiation_turns_log.csv")
    if os.path.exists(turns_path):
        with open(turns_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row.get("session_id", ""), row.get("npc_id", ""))
                status = (row.get("status", "") or "").lower()
                if status in ("deal", "walkaway"):
                    # Keep the terminal status; don't overwrite a richer tx row.
                    outcomes.setdefault(key, {"outcome": status,
                                              "turns": _to_int(row.get("turn"))})
    return outcomes


def _to_int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def backfill_observed_outcome(logs_dir: str) -> tuple[list[dict], str]:
    """Score every intent prediction against the observed outcome.

    Writes ``buyer_intent_predictions_scored.csv`` (a copy with ``observed_outcome``
    and a ``correct`` column) next to the input, leaving the raw log untouched.
    Returns ``(rows, output_path)``.
    """
    pred_path = os.path.join(logs_dir, "buyer_intent_predictions.csv")
    if not os.path.exists(pred_path):
        raise FileNotFoundError(pred_path)

    outcomes = _index_outcomes(logs_dir)
    rows: list[dict] = []
    with open(pred_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            key = (row.get("session_id", ""), row.get("npc_id", ""))
            info = outcomes.get(key)
            if info:
                observed = map_outcome_to_intent(info["outcome"], info["turns"])
                row["observed_outcome"] = observed
                row["correct"] = "1" if row.get("predicted_top") == observed else "0"
            else:
                row["observed_outcome"] = ""
                row["correct"] = ""
            rows.append(row)

    out_fields = fieldnames + [c for c in ("observed_outcome", "correct") if c not in fieldnames]
    out_path = os.path.join(logs_dir, "buyer_intent_predictions_scored.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows)
    return rows, out_path
