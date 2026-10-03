"""MerchantGraph: LangGraph orchestration of the merchant negotiation.

Two compiled ``StateGraph``s drive a human-in-the-loop voice negotiation:

* ``opening graph``  : load -> predict_intent -> detect_item -> appraise ->
  generate_opening_offer. Runs once when the player opens the trade.
* ``turn graph``     : evaluate_counteroffer -> {respond_counter |
  close_deal -> update_state}. Runs once per player counteroffer, with a
  conditional edge implementing the haggle loop / terminal close.

The :class:`MerchantNegotiation` driver holds the running state between turns,
mirroring how Mantella's conversation loop feeds one player utterance at a time.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from langgraph.graph import StateGraph, START, END

from src.merchantmind.graph.state import MerchantGraphState
from src.merchantmind.graph.llm import NegotiationLLM
from src.merchantmind.graph import nodes


def _build_opening_graph(base_dir: str, llm: NegotiationLLM):
    # NOTE: buyer-intent prediction is intentionally NOT on this path. It used to
    # sit between load and detect_item, adding a blocking LLM round-trip before
    # the merchant could say a word. It only fed ``haggle_hard`` into the opening
    # margin (a <=20% nudge that gets haggled away anyway), so it is now run off
    # the critical path by the driver (see MerchantNegotiation._kick_intent_...).
    # appraise_item defaults ``haggle_hard`` to 0.0 when the distribution is absent.
    g = StateGraph(MerchantGraphState)
    g.add_node("load", nodes.make_load_state(base_dir))
    g.add_node("detect_item", nodes.make_detect_intent_and_item(llm))
    g.add_node("appraise", nodes.appraise_item)
    g.add_node("opening_offer", nodes.make_generate_opening_offer(llm))

    g.add_edge(START, "load")
    g.add_edge("load", "detect_item")
    g.add_edge("detect_item", "appraise")
    g.add_edge("appraise", "opening_offer")
    g.add_edge("opening_offer", END)
    return g.compile()


def _route_after_eval(state: dict) -> str:
    """Conditional edge: continue haggling or close the deal."""
    return "ongoing" if state.get("negotiation_status") == "ongoing" else "terminal"


def _build_turn_graph(base_dir: str, llm: NegotiationLLM, llm_judge: Callable | None):
    g = StateGraph(MerchantGraphState)
    g.add_node("evaluate", nodes.make_evaluate_counteroffer(llm))
    g.add_node("respond_counter", nodes.make_respond_counter(llm))
    g.add_node("close_deal", nodes.make_close_deal(llm))
    g.add_node("update_state", nodes.make_update_state(base_dir, llm_judge))

    g.add_edge(START, "evaluate")
    g.add_conditional_edges("evaluate", _route_after_eval, {
        "ongoing": "respond_counter",
        "terminal": "close_deal",
    })
    g.add_edge("respond_counter", END)
    g.add_edge("close_deal", "update_state")
    g.add_edge("update_state", END)
    return g.compile()


class MerchantNegotiation:
    """Stateful driver around the MerchantGraph for one negotiation session."""

    def __init__(self, base_dir: str, llm: NegotiationLLM,
                 llm_judge: Callable | None = None, language: str = "en",
                 predict_intent_async: bool = True, rng_seed: int | None = None) -> None:
        self._opening = _build_opening_graph(base_dir, llm)
        self._turn = _build_turn_graph(base_dir, llm, llm_judge)
        self._llm = llm
        self._language = language
        # Controlled randomness (A5): None = deterministic; an int enables bounded,
        # reproducible jitter (same seed -> same negotiation).
        self._rng_seed = rng_seed
        # When True the buyer-intent prediction runs in a background thread so it
        # never blocks the merchant's spoken line (it is only logged for RQ1).
        # Tests pass False to get the distribution synchronously in the state.
        self._predict_intent_async = predict_intent_async
        self._state: dict[str, Any] | None = None

    def _kick_intent_prediction(self) -> None:
        """Predict + log buyer intent off the critical path.

        Reuses the intent node on an isolated snapshot. In async mode the result
        is only logged (never written back to the live state, to avoid races);
        in sync mode it is merged into the state so callers/tests can read it.
        """
        if self._state is None:
            return
        snapshot = {
            "npc_psychosocial_state": self._state.get("npc_psychosocial_state"),
            "player_first_utterance": self._state.get("player_first_utterance", ""),
            "npc_id": self._state.get("npc_id", ""),
            "haggle_turns": self._state.get("haggle_turns", 0),
        }
        predict = nodes.make_predict_buyer_intent(self._llm)

        def run() -> None:
            try:
                out = predict(snapshot)
                if not self._predict_intent_async and self._state is not None:
                    self._state.update(out)
            except Exception:
                pass  # buyer-intent is observational; never break the negotiation

        if self._predict_intent_async:
            threading.Thread(target=run, daemon=True).start()
        else:
            run()

    @property
    def state(self) -> dict | None:
        return self._state

    @property
    def status(self) -> str:
        return (self._state or {}).get("negotiation_status", "opening")

    def open(self, player_name: str, npc_id: str, first_utterance: str,
             npc_meta: dict | None = None) -> dict:
        """Start a negotiation; returns the merchant's opening turn."""
        init: dict = {
            "player_name": player_name,
            "npc_id": npc_id,
            "npc_meta": npc_meta or {"is_merchant": True},
            "language": self._language,
            "player_first_utterance": first_utterance,
        }
        if self._rng_seed is not None:
            init["negotiation_rng_seed"] = int(self._rng_seed)
        self._state = self._opening.invoke(init)
        self._kick_intent_prediction()
        return self._summary()

    def respond(self, player_utterance: str) -> dict:
        """Feed one player utterance; returns the merchant's next turn."""
        if self._state is None:
            raise RuntimeError("Negotiation not started; call open() first.")
        status = self.status
        if status in ("deal", "walkaway"):
            return self._summary()
        # No item resolved yet (greeting / unclear): re-run the opening graph on
        # the new utterance to (re)detect the item, instead of haggling on nothing.
        if status == "clarify" or not self._state.get("item_name") \
                or float(self._state.get("item_base_price", 0) or 0) <= 0:
            self._state["player_first_utterance"] = player_utterance
            self._state = self._opening.invoke(self._state)
            self._kick_intent_prediction()
            return self._summary()
        self._state["last_player_utterance"] = player_utterance
        self._state = self._turn.invoke(self._state)
        return self._summary()

    def _summary(self) -> dict:
        s = self._state or {}
        return {
            "npc_line": s.get("npc_line", ""),
            "status": s.get("negotiation_status", "opening"),
            "agreed_price": s.get("agreed_price"),
            "item_name": s.get("item_name"),
            "item_index": s.get("item_index", -1),
            "current_npc_price": s.get("current_npc_price"),
            "haggle_turns": s.get("haggle_turns", 0),
        }
