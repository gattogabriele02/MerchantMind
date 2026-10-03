"""MerchantGraph nodes.

Each node is a plain callable ``(state) -> partial_state`` so it composes in a
LangGraph ``StateGraph``. Dependencies (the LLM and the store directory) are
bound via closures in :mod:`merchant_graph`, keeping the state JSON-serialisable.

Design split: the *numbers* (target price,
concessions, accept/walk decision) are deterministic and auditable; the *LLM*
only understands the player's utterance and voices the merchant's reply.
"""

from __future__ import annotations

import random
import uuid

from src.merchantmind import store, salience, pricing, anomaly
from src.merchantmind.graph.llm import NegotiationLLM
from src.merchantmind.research_logger import research_logger


def _history_from_transcript(transcript: list | None) -> list:
    """Map the negotiation transcript to chat messages (npc=assistant, player=user).

    Gives the dialogue LLM conversational memory of the turns so far without
    re-prompting everything (A1). Empty on the first line -> no behaviour change.
    """
    messages = []
    for entry in transcript or []:
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        role = "assistant" if entry.get("speaker") == "npc" else "user"
        messages.append({"role": role, "content": text})
    return messages


def _rng_from_state(state: dict, salt: int) -> random.Random | None:
    """Reproducible RNG for controlled randomness (A5), or None if disabled.

    Enabled only when ``negotiation_rng_seed`` is set on the state. The seed is
    combined with a per-use ``salt`` and the current turn so each decision gets an
    independent-but-reproducible draw (same seed -> same negotiation).
    """
    seed = state.get("negotiation_rng_seed")
    if seed is None:
        return None
    turn = int(state.get("haggle_turns", 0))
    return random.Random(int(seed) * 1000003 + salt * 31 + turn)


def _concession_beta(npc: dict) -> float:
    """Shape of the concession curve from agreeableness (Faratin et al.).

    beta < 1 Boulware (tough, concedes near the deadline), 1 linear, > 1 Conceder
    (soft, concedes early). Grounded in Huang & Hadfi: agreeable -> concedes more.
    """
    agr = float(npc.get("core_identity", {}).get("personality_traits", {}).get("agreeableness", 0.5))
    return max(CONCESSION_BETA_MIN, min(CONCESSION_BETA_MAX, 2.0 * agr))


def _tit_for_tat_bonus(prev_offered, curr_offered, opening: float, target: float) -> float:
    """Bounded extra concession rewarding the buyer's own concession (behavior-dependent).

    Returns a fraction in [0, TIT_FOR_TAT_WEIGHT], proportional to how much the
    buyer raised their offer between turns (normalised by the concession span).
    """
    if prev_offered is None or curr_offered is None or opening <= target:
        return 0.0
    gain = (float(curr_offered) - float(prev_offered)) / (opening - target)
    return max(0.0, min(TIT_FOR_TAT_WEIGHT, TIT_FOR_TAT_WEIGHT * gain))


def _log_line_anomalies(state: dict, line: str, allowed_numbers: list | None) -> None:
    """Detect + log any contract violation in a spoken line (no-op if clean)."""
    for a in anomaly.detect_line_anomalies(line, allowed_numbers=allowed_numbers):
        research_logger.log_anomaly(
            state.get("npc_id", ""), category=a["category"], description=a["description"],
            turn=int(state.get("haggle_turns", 0)), raw_text=a["raw_text"])

# --- intent / pricing constants (tunable, ablatable) ----------------------

INTENT_LABELS = (
    "haggle_hard",
    "accept_quickly",
    "bundle_interest",
    "walkaway_likely",
    "intelligence_gathering",
)

# How much above the hidden target the opening offer sits, scaled by how hard
# the buyer is expected to haggle.
OPENING_MARGIN_BASE = 0.08
OPENING_MARGIN_HAGGLE = 0.20

# Floor a player offer must clear (relative to target) to avoid a walkaway.
WALKAWAY_FLOOR_RATIO = 0.6

# Oltre ``max_haggle_turns`` la curva di concessione e' esaurita: il prezzo e'
# gia' fermo sulla riserva e continuare non produce piu' nulla. Il mercante fa
# un'ultima offerta esplicita ("prendere o lasciare") e, se il giocatore non la
# copre, chiude senza accordo. Senza questo la trattativa puo' proseguire
# all'infinito ripetendo la stessa battuta.

# Controlled randomness (A5): bounded, seeded jitter so the merchant feels less
# robotic without breaking auditability. Applied ONLY when a seed is set.
OPENING_MARGIN_JITTER = 0.03   # +/- on the opening margin
CONCESSION_JITTER = 0.15       # +/- 15% on each concession step

# Non-linear concession curve (Faratin et al. time-dependent tactics): beta < 1
# = Boulware (tough, concedes late), beta = 1 linear, beta > 1 = Conceder (soft,
# concedes early). Shaped by agreeableness (Huang & Hadfi). Plus a bounded
# tit-for-tat term rewarding the buyer's own concession (behavior-dependent).
CONCESSION_BETA_MIN = 0.4
CONCESSION_BETA_MAX = 2.0
TIT_FOR_TAT_WEIGHT = 0.15


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# --- nodes ----------------------------------------------------------------

def make_load_state(base_dir: str):
    def load_npc_psychosocial_state(state: dict) -> dict:
        meta = state.get("npc_meta", {}) or {}
        npc = store.load_or_create(
            base_dir, state["player_name"], state["npc_id"],
            name=meta.get("name", ""), is_merchant=meta.get("is_merchant", True),
            race=meta.get("race", ""), role=meta.get("role", "merchant"),
            city=meta.get("city", ""))
        # Make sure derived fields (price_modifier, stage, behaviour) are current.
        pricing.recompute_derived(npc)
        return {"npc_psychosocial_state": npc, "negotiation_status": "opening",
                "haggle_turns": 0, "transcript": []}
    return load_npc_psychosocial_state


def make_predict_buyer_intent(llm: NegotiationLLM):
    def predict_buyer_intent(state: dict) -> dict:
        npc = state["npc_psychosocial_state"]
        merchant = npc.get("merchant_state", {})
        summary = merchant.get("transaction_history_summary", {})
        archetype = merchant.get("predicted_buyer_archetype", "unknown")
        utterance = state.get("player_first_utterance", "")

        system = (
            "You predict a customer's negotiation intent for a shopkeeper. "
            "Output a probability distribution (values 0..1) over exactly these "
            f"keys: {', '.join(INTENT_LABELS)}."
        )
        user = (
            f"Customer history with this shop:\n"
            f"- interactions: {summary.get('total_transactions', 0)}\n"
            f"- average haggle turns: {summary.get('average_haggle_turns', 0)}\n"
            f"- deal rate: {summary.get('deal_rate', 0)}\n"
            f"- previously labelled: {archetype}\n\n"
            f'Customer just said: "{utterance}"'
        )
        raw = llm.json(system, user, label="mm_llm_intent")
        dist = {k: float(raw.get(k, 0.0)) for k in INTENT_LABELS}
        total = sum(dist.values())
        if total > 0:
            dist = {k: round(v / total, 4) for k, v in dist.items()}
        else:  # uninformative fallback
            dist = {k: round(1 / len(INTENT_LABELS), 4) for k in INTENT_LABELS}
        research_logger.log_intent(state.get("npc_id", ""), int(state.get("haggle_turns", 0)),
                                   utterance, dist)
        return {"buyer_intent_distribution": dist}
    return predict_buyer_intent


def make_detect_intent_and_item(llm: NegotiationLLM):
    def detect_intent_and_item(state: dict) -> dict:
        utterance = state.get("player_first_utterance", "")
        inventory = state["npc_psychosocial_state"].get("merchant_state", {}).get(
            "shop_inventory_last_seen", [])
        item_list = ", ".join(
            f"{it.get('item_id')} ({it.get('base_price')})" for it in inventory) or "unknown"

        system = (
            "Extract the trade intent from a customer line in a fantasy shop. "
            'Return JSON: {"action": "buy"|"sell"|"browse", "item_name": str, '
            '"base_price": number}. Use the shop inventory to resolve the item '
            "and its base price; if no item is named use action 'browse'."
        )
        user = f'Shop inventory: {item_list}\nCustomer said: "{utterance}"'
        raw = llm.json(system, user, label="mm_llm_detect")

        action = str(raw.get("action", "browse")).lower()
        item_name = raw.get("item_name") or ""
        base_price = raw.get("base_price")
        # Prefer the authoritative inventory price when the item matches, and
        # record its index so the Papyrus trade can resolve the Form by position
        # (language-independent, avoids matching localized display names).
        item_index = -1
        for idx, it in enumerate(inventory):
            if item_name and str(it.get("item_id", "")).lower() == str(item_name).lower():
                base_price = it.get("base_price", base_price)
                item_index = idx
                break
        try:
            base_price = float(base_price) if base_price is not None else 0.0
        except (TypeError, ValueError):
            base_price = 0.0
        return {"player_action": action, "item_name": item_name,
                "item_base_price": base_price, "item_index": item_index}
    return detect_intent_and_item


def appraise_item(state: dict) -> dict:
    """Compute the hidden target and opening price from memory + intent.

    ``internal_target_price`` is the lowest the merchant will accept, derived
    from the relationship-driven ``price_modifier``. The opening price sits above
    it, with a wider margin when the buyer is expected to haggle hard.
    """
    npc = state["npc_psychosocial_state"]
    base_price = float(state.get("item_base_price", 0.0))
    modifier = float(npc.get("merchant_state", {}).get("price_modifier", 1.0))

    # No item resolved (e.g. the player only greeted, or the utterance was
    # unclear): don't quote a price. Ask what they want and re-detect next turn.
    if base_price <= 0:
        return {"negotiation_status": "clarify"}

    target = base_price * modifier
    haggle_hard = float(state.get("buyer_intent_distribution", {}).get("haggle_hard", 0.0))
    margin = OPENING_MARGIN_BASE + OPENING_MARGIN_HAGGLE * haggle_hard
    # Controlled randomness (A5): small seeded jitter on the opening margin.
    rng = _rng_from_state(state, salt=7)
    if rng is not None:
        margin = max(0.0, margin + rng.uniform(-OPENING_MARGIN_JITTER, OPENING_MARGIN_JITTER))
    opening = max(target, base_price) * (1.0 + margin)

    # Number of concession rounds the merchant tolerates scales with willingness.
    willingness = float(npc.get("behavior_modifiers", {}).get("willingness_to_haggle", 0.5))
    max_turns = int(round(2 + 4 * willingness))  # 2..6

    return {
        "internal_target_price": round(target, 2),
        "opening_price": round(opening, 2),
        "current_npc_price": round(opening, 2),
        "max_haggle_turns": max_turns,
    }


def make_generate_opening_offer(llm: NegotiationLLM):
    def generate_opening_offer(state: dict) -> dict:
        npc = state["npc_psychosocial_state"]
        identity = npc.get("core_identity", {})
        rel = npc.get("relationship_with_player", {})
        behaviour = npc.get("behavior_modifiers", {})

        # No item resolved yet -> reply in character, list the goods, steer to a
        # purchase (and reference the shared history). Stays in 'clarify'.
        if state.get("negotiation_status") == "clarify" or float(state.get("item_base_price", 0)) <= 0:
            inventory = npc.get("merchant_state", {}).get("shop_inventory_last_seen", [])
            goods = ", ".join(str(it.get("item_id", "")) for it in inventory if it.get("item_id")) \
                or "i miei articoli"
            customer_said = state.get("player_first_utterance", "") or state.get("last_player_utterance", "")
            line = llm.text(
                system=(f"You are {identity.get('name', 'a merchant')}, a merchant in "
                        f"{identity.get('city', 'Skyrim')}. Tone: {behaviour.get('dialogue_tone', 'neutral')}. "
                        f"Your relationship with this customer: {rel.get('relationship_summary', 'a customer')}. "
                        f"Speak ONLY the spoken line, 1-2 sentences, in character, no narration. "
                        f"Respond in {state.get('language', 'English')}."),
                user=(f'The customer said: "{customer_said}". Reply naturally and in character. '
                      f"You have these items for sale: {goods}. If the customer has not named a "
                      f"specific item, briefly tell them what you have and invite them to choose one. "
                      f"Do NOT quote any price yet."),
                label="mm_llm_clarify",
                history=_history_from_transcript(state.get("transcript", [])),
            )
            transcript = list(state.get("transcript", []))
            transcript.append({"speaker": "npc", "text": line})
            return {"npc_line": line, "negotiation_status": "clarify", "transcript": transcript}

        line = llm.text(
            system=(
                f"You are {identity.get('name', 'a merchant')}, a "
                f"{identity.get('role', 'merchant')} in {identity.get('city', 'Skyrim')}. "
                f"Tone: {behaviour.get('dialogue_tone', 'neutral')}. "
                f"Relationship: {rel.get('relationship_summary', 'a customer')}. "
                "Talk like a REAL shopkeeper making a pitch — warm, natural, a bit persuasive, "
                "NOT robotic. Say ONLY the spoken line, 1-2 short sentences, in character, no narration. "
                f"Respond in {state.get('language', 'English')}."
            ),
            user=(
                f"The customer wants to {state.get('player_action', 'buy')} "
                f"{state.get('item_name', 'an item')}. You are SELLING it to them, so the price is what "
                f"THEY pay YOU (never phrase it as you giving them money). Name your opening price of "
                f"{int(round(state.get('opening_price', 0)))} gold in a natural, conversational way "
                "(you may nod to your shared history). Do not say the price is negotiable. "
                f"IMPORTANT: the only number you may say is {int(round(state.get('opening_price', 0)))}; "
                "never mention any other amount. Write the number in DIGITS (e.g. 66), never spelled "
                "out in words."
            ),
            label="mm_llm_opening",
            history=_history_from_transcript(state.get("transcript", [])),
        )
        transcript = list(state.get("transcript", []))
        transcript.append({"speaker": "npc", "text": line})
        _log_line_anomalies(state, line, [state.get("opening_price")])
        research_logger.log_turn(state.get("npc_id", ""), 0, "npc_opening",
                                 npc_price=state.get("opening_price", ""),
                                 target_price=state.get("internal_target_price", ""),
                                 status="ongoing", npc_line=line)
        return {"npc_line": line, "negotiation_status": "ongoing", "transcript": transcript}
    return generate_opening_offer


def make_evaluate_counteroffer(llm: NegotiationLLM):
    """Parse the player's counteroffer and decide accept / counter / walk.

    Numbers are deterministic: the merchant concedes from its current price
    toward the hidden target over ``max_haggle_turns`` rounds, accepts when the
    player's offer meets the current price, and walks if the offer is insultingly
    low after enough rounds.
    """
    def evaluate_counteroffer(state: dict) -> dict:
        utterance = state.get("last_player_utterance", "")
        system = (
            "Extract a buyer's counteroffer in a haggle. Return JSON: "
            '{"offered_price": number|null, "stance": '
            '"accept"|"counter"|"walkaway"|"offtopic"}. '
            '"offered_price" is ONLY the sum the buyer is proposing TO PAY. '
            "If the buyer merely repeats, quotes, questions or complains about a "
            "price the merchant named, there is NO offer: return null. "
            'Examples: "ti offro 40" -> 40. "non sei sceso a 53, lo avevi gia detto" '
            '-> null. "53 e troppo" -> null. "va bene, affare fatto" -> null with '
            'stance "accept". '
            'Use "counter" for any push on the price, including without a number '
            '("e troppo caro", "non puoi scendere ancora", "fammi uno sconto"). '
            'Use "offtopic" ONLY when the buyer is not talking about the deal at '
            "all: a question about the merchant or the world, or small talk."
        )
        parsed = llm.json(system, f'Merchant price: {state.get("current_npc_price")}. '
                                  f'Buyer said: "{utterance}"', label="mm_llm_parse")
        stance = str(parsed.get("stance", "counter")).lower()
        offered = parsed.get("offered_price")
        try:
            offered = float(offered) if offered is not None else None
        except (TypeError, ValueError):
            offered = None

        target = float(state.get("internal_target_price", 0.0))
        npc_price = float(state.get("current_npc_price", 0.0))
        opening = float(state.get("opening_price", npc_price))
        turns = int(state.get("haggle_turns", 0)) + 1
        max_turns = int(state.get("max_haggle_turns", 4))

        # Rete di sicurezza sull'estrazione: se la cifra coincide con il prezzo che
        # il mercante ha appena chiesto, quasi sempre il giocatore la sta citando,
        # non offrendo. Per chiudere a quella cifra serve un'accettazione esplicita.
        if (offered is not None and stance != "accept"
                and abs(offered - round(npc_price)) < 0.51):
            offered = None

        result: dict = {"haggle_turns": turns,
                        "last_offered_price": offered,
                        "last_stance": stance,
                        "offtopic_turn": False,
                        "previous_npc_price": round(npc_price, 2)}

        # Una domanda o una chiacchiera non e' una mossa di trattativa: non
        # consuma un round di pazienza e non muove il prezzo.
        if stance == "offtopic" and offered is None:
            out = {"haggle_turns": turns - 1,
                   "last_offered_price": state.get("last_offered_price"),
                   "last_stance": stance,
                   "offtopic_turn": True,
                   "previous_npc_price": round(npc_price, 2),
                   "negotiation_status": "ongoing",
                   "current_npc_price": round(npc_price, 2)}
        elif stance == "walkaway":
            out = {**result, "negotiation_status": "walkaway", "agreed_price": None}
        elif stance == "accept":
            # Explicit acceptance of the standing price.
            out = {**result, "negotiation_status": "deal", "agreed_price": round(npc_price, 2)}
        elif offered is not None and offered >= min(npc_price, target):
            # Player named a price at or above what the merchant will take -> deal.
            out = {**result, "negotiation_status": "deal",
                   "agreed_price": round(max(offered, target), 2)}
        elif offered is not None and turns >= max_turns and offered < target * WALKAWAY_FLOOR_RATIO:
            # Insultingly low after enough rounds -> walk away.
            out = {**result, "negotiation_status": "walkaway", "agreed_price": None}
        elif turns > max_turns:
            # Pazienza esaurita: un turno di ultimatum, poi si chiude.
            if state.get("ultimatum_issued"):
                out = {**result, "negotiation_status": "walkaway", "agreed_price": None}
            else:
                out = {**result, "negotiation_status": "ongoing",
                       "ultimatum_issued": True,
                       "current_npc_price": round(target, 2)}
        else:
            # Concede along a time-dependent curve (Faratin et al.): the price
            # walks from opening to target over max_turns, shaped by the merchant's
            # style (Boulware/Conceder via agreeableness), plus a bounded tit-for-tat
            # nudge rewarding the buyer's concession, plus optional seeded jitter.
            # Always monotone (never above the current price) and clamped to target.
            npc = state.get("npc_psychosocial_state", {})
            beta = _concession_beta(npc)
            t = min(turns, max_turns)
            ratio = (t / max(1, max_turns)) ** (1.0 / beta)                 # 0..1 toward target
            ratio += _tit_for_tat_bonus(state.get("last_offered_price"), offered, opening, target)
            rng = _rng_from_state(state, salt=13)
            if rng is not None:
                ratio *= rng.uniform(1.0 - CONCESSION_JITTER, 1.0 + CONCESSION_JITTER)
            ratio = _clamp(ratio, 0.0, 1.0)
            new_price = opening - (opening - target) * ratio
            new_price = _clamp(new_price, target, npc_price)                # never above current price
            out = {**result, "negotiation_status": "ongoing", "current_npc_price": round(new_price, 2)}

        research_logger.log_turn(
            state.get("npc_id", ""), turns, "player", player_utterance=utterance,
            offered_price=offered if offered is not None else "", stance=stance,
            npc_price=out.get("current_npc_price", round(npc_price, 2)),
            target_price=round(target, 2), status=out["negotiation_status"])
        return out
    return evaluate_counteroffer


def make_respond_counter(llm: NegotiationLLM):
    def respond_counter(state: dict) -> dict:
        npc = state["npc_psychosocial_state"]
        identity = npc.get("core_identity", {})
        behaviour = npc.get("behavior_modifiers", {})
        new_price = int(round(state.get("current_npc_price", 0)))
        offered = state.get("last_offered_price")
        # Directionally-correct, colloquial instruction: the merchant is coming DOWN
        # toward the buyer but can't reach their offer (avoids the "price went up" glitch).
        if state.get("offtopic_turn"):
            # Il giocatore ha chiesto o detto qualcosa che non riguarda il prezzo:
            # gli si risponde davvero, invece di rilanciare una contrattazione.
            situation = ("The customer said something that is NOT an offer — a question, a remark, "
                         "or small talk. Answer THEM, specifically and in character, about what they "
                         f"actually said. Only afterwards, briefly, bring it back to the deal: your "
                         f"price is still {new_price} gold. Do not repeat a haggling formula. "
                         "If what they said makes no sense (garbled speech), simply say in character "
                         "that you did not catch it and ask them to repeat — do not invent a meaning.")
        elif state.get("ultimatum_issued"):
            # Pazienza esaurita: ultima offerta, dichiarata come tale.
            situation = (f"This is your FINAL offer: {new_price} gold, take it or leave it. Say plainly "
                         "that you will not go any lower and that you are ready to end the haggle. "
                         "Do not sound like your previous lines.")
        elif offered is not None:
            situation = (f"The customer offered {int(round(offered))} gold — too low for you. "
                         f"You are coming DOWN toward them, meeting them partway at {new_price} gold "
                         f"(still above their offer).")
        else:
            situation = ("The customer is pushing for a lower price WITHOUT naming a figure. "
                         f"You come DOWN a little, to {new_price} gold.")
        allowed = f"{new_price}" + (f" (and, if useful, their offer of {int(round(offered))})" if offered is not None else "")
        # Annunciare una discesa quando il prezzo NON e' sceso e' il difetto visto
        # sul campo ("scendo a 53" quando 53 lo aveva gia' chiesto). L'istruzione
        # sul movimento va data solo quando un movimento c'e' stato davvero.
        prezzo_precedente = state.get("previous_npc_price")
        sceso = (prezzo_precedente is not None
                 and float(prezzo_precedente) > float(new_price) + 0.5)
        if state.get("offtopic_turn") or not sceso:
            movimento = ("The price has NOT changed: do NOT announce a discount, do NOT say you are "
                         "lowering anything, and do not present the number as a new concession.")
        elif offered is not None:
            movimento = ("Make clear you are LOWERING the price toward the buyer — for example "
                         f"'non posso arrivare al tuo prezzo, pero' posso scendere a {new_price}'.")
        else:
            # Il compratore NON ha nominato alcuna cifra: riferirsi al "suo prezzo"
            # o alla "sua offerta" e' un'invenzione, ed e' stato osservato sul campo.
            movimento = ("Make clear you are LOWERING the price — for example "
                         f"'posso venirti incontro: te la lascio a {new_price}'. "
                         "The buyer has NOT named any price: never refer to 'your price', "
                         "'your offer' or any sum they supposedly proposed.")
        line = llm.text(
            system=(
                f"You are {identity.get('name', 'a merchant')}, haggling at your stall in a fantasy "
                f"marketplace. Tone: {behaviour.get('dialogue_tone', 'neutral')}. Talk like a REAL "
                "shopkeeper bargaining: warm, natural, a bit persuasive or playful — NOT robotic, not a "
                "flat price announcement, and never reuse the same phrasing. Say ONLY the spoken line, "
                f"1-2 short sentences, in character, no narration. Respond in {state.get('language', 'English')}."
            ),
            # Il turno entra nel prompt: quando il prezzo resta fermo sulla riserva
            # e' l'unica cosa che cambia, e senza di essa il modello ripete se stesso.
            user=(
                f"[haggle round {int(state.get('haggle_turns', 0))}] {situation} "
                "Phrase it differently from anything you have already said. Phrase it naturally and "
                f"conversationally. {movimento} IMPORTANT: the ONLY number you may say is {allowed}; "
                "never invent or mention any other amount. Write numbers in DIGITS (e.g. 63), never spelled "
                "out in words. Do NOT reveal your minimum. Keep the deal alive."
            ),
            label="mm_llm_counter",
            history=_history_from_transcript(state.get("transcript", [])),
        )
        transcript = list(state.get("transcript", []))
        transcript.append({"speaker": "player", "text": state.get("last_player_utterance", "")})
        transcript.append({"speaker": "npc", "text": line})
        _log_line_anomalies(state, line, [state.get("current_npc_price"), offered])
        research_logger.log_turn(state.get("npc_id", ""), int(state.get("haggle_turns", 0)),
                                 "npc_counter", npc_price=state.get("current_npc_price", ""),
                                 target_price=state.get("internal_target_price", ""),
                                 status="ongoing", npc_line=line)
        return {"npc_line": line, "transcript": transcript}
    return respond_counter


def make_close_deal(llm: NegotiationLLM):
    def close_deal_or_walkaway(state: dict) -> dict:
        npc = state["npc_psychosocial_state"]
        identity = npc.get("core_identity", {})
        status = state.get("negotiation_status")
        behaviour = npc.get("behavior_modifiers", {})
        if status == "deal":
            agreed = int(round(state.get("agreed_price", 0)))
            item = state.get("item_name", "the item")
            user = (f"The deal is CLOSED: you are selling {item} for {agreed} gold. Confirm the deal "
                    f"clearly and warmly, explicitly naming the item and the price ({agreed} gold), like a "
                    f"happy shopkeeper (a friendly quip is welcome). IMPORTANT: the only number you may "
                    f"say is {agreed}; never mention any other amount. Write it in DIGITS (e.g. 41), never "
                    "spelled out in words.")
        else:
            user = ("You couldn't agree on a price. Wrap up the haggle politely and in character, "
                    "leaving the door open for next time. No insults and do NOT mention any number.")
        line = llm.text(
            system=(f"You are {identity.get('name', 'a merchant')} at your market stall. Tone: "
                    f"{behaviour.get('dialogue_tone', 'neutral')}. Talk naturally, not robotic. Say ONLY "
                    f"the spoken line, 1 short sentence. Respond in {state.get('language', 'English')}."),
            user=user,
            label="mm_llm_close",
            history=_history_from_transcript(state.get("transcript", [])),
        )
        transcript = list(state.get("transcript", []))
        transcript.append({"speaker": "npc", "text": line})
        # Deal: only the agreed price may appear; walkaway: no number at all.
        allowed = [state.get("agreed_price")] if status == "deal" else []
        _log_line_anomalies(state, line, allowed)
        return {"npc_line": line, "transcript": transcript}
    return close_deal_or_walkaway


def make_update_state(base_dir: str, llm_judge=None):
    def update_psychosocial_state(state: dict) -> dict:
        npc = state["npc_psychosocial_state"]
        status = state.get("negotiation_status")
        turns = int(state.get("haggle_turns", 0))
        agreed = state.get("agreed_price")

        # Build the episodic memory for this negotiation.
        if status == "deal":
            event_type = "negotiation_hard" if turns >= 3 else "first_purchase"
            description = (f"The player bought {state.get('item_name', 'an item')} for "
                           f"{agreed} gold after {turns} rounds of haggling.")
            impact = {"respect": 0.05, "irritation": 0.02 * turns}
        else:
            event_type = "negotiation_walkaway"
            description = (f"The player walked away from {state.get('item_name', 'an item')} "
                           f"after {turns} rounds.")
            impact = {"irritation": 0.05}

        npc_id = state.get("npc_id", "")
        old_stage = npc.get("relationship_with_player", {}).get("relationship_stage", "")

        event = {"event_id": f"evt_{uuid.uuid4().hex[:10]}", "type": event_type,
                 "description": description, "emotional_impact": impact}
        importance, decay = salience.evaluate_salience(event, npc, llm_judge=llm_judge)
        event.update({"importance": round(importance, 4), "decay_rate": round(decay, 4),
                      "source": "merchant_interaction"})
        npc.setdefault("episodic_memories", []).append(event)

        # Apply rule-based relationship deltas.
        rel = npc.setdefault("relationship_with_player", {})
        rel["interactions_count"] = int(rel.get("interactions_count", 0)) + 1
        rel["respect"] = _clamp(float(rel.get("respect", 0.5)) + (0.03 if status == "deal" else 0.0), 0, 1)
        rel["affinity"] = _clamp(float(rel.get("affinity", 0.5)) + (0.02 if status == "deal" else -0.01), 0, 1)

        # Update merchant transaction stats.
        merchant = npc.setdefault("merchant_state", {})
        if status == "deal" and agreed is not None:
            merchant.setdefault("transaction_history", []).append({
                "item": state.get("item_name"),
                "base_price": state.get("item_base_price"),
                "npc_target": state.get("internal_target_price"),
                "agreed_price": agreed,
                "turns": turns,
                "outcome": "deal",
            })
        merchant["last_negotiation_outcome"] = "deal" if status == "deal" else "walkaway"
        _refresh_transaction_summary(merchant)

        # Recompute derived fields (price_modifier, behaviour, stage) and persist.
        pricing.recompute_derived(npc)
        store.save_state(base_dir, state["player_name"], npc)

        # Research logging (no-op unless the logger is configured).
        new_stage = npc.get("relationship_with_player", {}).get("relationship_stage", "")
        research_logger.log_episodic(npc_id, event)
        if status == "deal" and agreed is not None:
            research_logger.log_transaction(
                npc_id, item=state.get("item_name", ""), base_price=state.get("item_base_price", ""),
                npc_target=state.get("internal_target_price", ""), agreed_price=agreed,
                turns=turns, outcome="deal")
        research_logger.log_price_snapshot(npc_id, npc, "negotiation")
        research_logger.log_state_snapshot(npc_id, npc, "negotiation")
        research_logger.log_stage_if_changed(npc_id, old_stage, new_stage, "negotiation")
        return {"npc_psychosocial_state": npc}
    return update_psychosocial_state


def _refresh_transaction_summary(merchant: dict) -> None:
    history = merchant.get("transaction_history", [])
    deals = [t for t in history if t.get("outcome") == "deal"]
    total = len(history)
    summary = merchant.setdefault("transaction_history_summary", {})
    summary["total_transactions"] = total
    summary["total_gold_spent_by_player"] = sum(t.get("agreed_price", 0) or 0 for t in deals)
    if deals:
        summary["average_haggle_turns"] = round(sum(t.get("turns", 0) for t in deals) / len(deals), 2)
    summary["deal_rate"] = round(len(deals) / total, 3) if total else 0.0
    summary["walkaway_rate"] = round(1 - (len(deals) / total), 3) if total else 0.0
