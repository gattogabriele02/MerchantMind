"""State definition for the MerchantGraph negotiation."""

from __future__ import annotations

from typing import TypedDict


class MerchantGraphState(TypedDict, total=False):
    """State threaded through the MerchantGraph nodes.

    Only plain JSON-serialisable values live here so the state can be
    checkpointed. Dependencies (LLM, store directory) are injected via closures
    in the graph builder, not stored in the state.
    """

    # Identity / routing
    player_name: str
    npc_id: str
    npc_meta: dict          # name, race, role, city, is_merchant (for first creation)
    language: str
    negotiation_rng_seed: int  # controlled-randomness seed (absent/None = deterministic)

    # Loaded psycho-social state (the "memory")
    npc_psychosocial_state: dict

    # Player input
    player_first_utterance: str
    last_player_utterance: str

    # Intent prediction (section 5.3)
    buyer_intent_distribution: dict

    # Item under negotiation (section 5.4 / 5.8)
    player_action: str      # "buy" | "sell" | "browse"
    item_name: str
    item_base_price: float
    item_index: int         # position in shop_inventory_last_seen (-1 if unresolved)

    # Hidden negotiation strategy (section 5.4)
    internal_target_price: float
    opening_price: float
    current_npc_price: float

    # Live negotiation
    negotiation_status: str  # "opening" | "ongoing" | "deal" | "walkaway"
    npc_line: str            # latest in-character line for TTS
    agreed_price: float | None
    haggle_turns: int
    max_haggle_turns: int
    transcript: list         # list of {"speaker": "player"|"npc", "text": str}
    last_offered_price: float | None   # price the player just named (for colloquial replies)
    last_stance: str                   # "accept" | "counter" | "walkaway" | "offtopic"
    previous_npc_price: float | None   # prezzo del turno prima: dice se c'e' stata davvero una discesa
    offtopic_turn: bool                # il giocatore non ha fatto una mossa di trattativa
    ultimatum_issued: bool             # ultima offerta gia' dichiarata: al prossimo turno si chiude
