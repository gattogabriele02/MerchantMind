"""Ablation harness for buyer-intent prediction (RQ1).

Research question: does giving the merchant the customer's *history* change how it
predicts the customer's negotiation intent? This runs ``predict_buyer_intent`` on
the same utterances under two conditions — **with** a populated transaction
history / archetype vs **without** (a blank first-time customer) — and records the
two predicted distributions side by side.

The LLM is injected (a real client for a real run, a fake in tests), and the node
logic is reused verbatim so the ablation measures exactly the production model.
"""

from __future__ import annotations

from src.merchantmind.graph import nodes

# The prior the "with history" condition feeds the predictor: a customer who has
# haggled hard across several past visits.
WITH_HISTORY = {
    "label": "with_history",
    "summary": {"total_transactions": 8, "average_haggle_turns": 4.5,
                "deal_rate": 0.5, "walkaway_rate": 0.5},
    "archetype": "hard_haggler",
}
WITHOUT_HISTORY = {
    "label": "without_history",
    "summary": {"total_transactions": 0, "average_haggle_turns": 0.0,
                "deal_rate": 0.0, "walkaway_rate": 0.0},
    "archetype": "unknown",
}

DEFAULT_UTTERANCES = [
    "Quanto vuoi per la spada di ferro?",
    "È troppo caro, facciamo la metà.",
    "Mostrami cosa hai.",
    "Se non scendi me ne vado.",
]


def _intent_state(summary: dict, archetype: str, utterance: str) -> dict:
    """Minimal graph state carrying just what ``predict_buyer_intent`` reads."""
    return {
        "npc_psychosocial_state": {
            "merchant_state": {
                "transaction_history_summary": summary,
                "predicted_buyer_archetype": archetype,
            }
        },
        "player_first_utterance": utterance,
        "npc_id": "ablation",
        "haggle_turns": 0,
    }


def run_intent_ablation(llm, utterances: list[str] | None = None,
                        conditions: list[dict] | None = None) -> list[dict]:
    """Run the predictor over every (condition x utterance). Returns flat rows.

    Each row: ``{condition, utterance, <5 intent probs>, predicted_top}``.
    """
    utterances = utterances or DEFAULT_UTTERANCES
    conditions = conditions or [WITH_HISTORY, WITHOUT_HISTORY]
    predict = nodes.make_predict_buyer_intent(llm)

    rows: list[dict] = []
    for cond in conditions:
        for utt in utterances:
            state = _intent_state(cond["summary"], cond["archetype"], utt)
            dist = predict(state)["buyer_intent_distribution"]
            top = max(dist, key=dist.get) if dist else ""
            rows.append({"condition": cond["label"], "utterance": utt,
                         "predicted_top": top, **dist})
    return rows
