"""Glue between Mantella's conversation loop and the MerchantGraph.

Kept deliberately thin and side-effect free so it can be unit tested. The
feature is OFF unless explicitly enabled (env var ``MANTELLA_MERCHANTMIND``),
so a normal Mantella session is completely unaffected.

Responsibilities:
- decide whether the feature is enabled and whether an NPC is a merchant,
- derive a stable per-NPC id,
- build a :class:`MerchantNegotiation` wired to the same LLM endpoint Mantella
  is already using (reusing the live client's resolved base_url / model / key).
"""

from __future__ import annotations

import os
import re

# NOTE: LangGraph / the graph package are imported lazily inside build_*()
# so that importing this module (e.g. from conversation.py) never requires
# LangGraph to be installed. Only enabling the feature pulls it in.

# Heuristics for spotting a merchant when no explicit flag is available in-game.
MERCHANT_BIO_KEYWORDS = (
    "merchant", "shopkeeper", "shopkeep", "general goods", "trader", "trade goods",
    "blacksmith", "smith", "alchemist", "apothecary", "innkeeper", "fletcher",
    "pawnbroker", "store", "wares", "sells", "shop",
)
DEFAULT_MERCHANT_NAMES = {
    "belethor", "lucan valerius", "arcadia", "ysolda", "sayma", "sadri",
    "carlotta valentia", "fralia gray-mane", "alvor", "adrianne avenicci",
}


def enabled(config=None) -> bool:
    """Whether MerchantMind negotiation is active.

    Enabled via the ``MANTELLA_MERCHANTMIND`` environment variable, or via a
    ``merchantmind_enabled`` attribute on the config if one is ever added.
    """
    env = os.environ.get("MANTELLA_MERCHANTMIND", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    return bool(getattr(config, "merchantmind_enabled", False))


def is_merchant_character(character) -> bool:
    """Best-effort detection of whether an NPC is a merchant."""
    name = (getattr(character, "name", "") or "").strip().lower()
    if name in DEFAULT_MERCHANT_NAMES:
        return True
    bio = (getattr(character, "bio", "") or "").lower()
    return any(keyword in bio for keyword in MERCHANT_BIO_KEYWORDS)


def npc_id_for(character) -> str:
    """Stable, filesystem-safe id for a character, based on its **name**.

    Name-based (not ref-id-based) so the per-NPC state can be **pre-seeded** for
    the experiment without knowing the in-game instance id. Merchants have unique
    names, so collisions are not a concern for this use case.
    """
    name = (getattr(character, "name", "") or "npc").strip().lower()
    return re.sub(r"[^a-z0-9_]+", "_", name).strip("_") or "npc"


def base_dir_for(config) -> str:
    """Directory where per-NPC psycho-social JSON is stored."""
    save_folder = getattr(config, "save_folder", ".")
    return os.path.join(save_folder, "data", "merchantmind")


def build_llm(llm_client, config):
    """Build a NegotiationLLM reusing the live client's connection details."""
    from src import utils
    from src.merchantmind.graph.llm import OpenAINegotiationLLM
    base_url = getattr(llm_client, "_base_url", None) or utils.resolve_service_endpoint(
        getattr(config, "llm_api", "http://localhost:11434/v1"))
    model = getattr(llm_client, "_model_name", None) or getattr(config, "llm", "")
    api_key = getattr(llm_client, "_api_key", None) or "abc123"
    # Inherit the SAME request params as the main Mantella client (config llm_params)
    # so provider-specific settings apply here too — crucially "reasoning_effort":
    # "none", which disables Qwen3's <think> output. Without inheriting, the merchant
    # LLM would omit it and the negotiation would leak reasoning in English.
    params = dict(getattr(llm_client, "_request_params", None)
                  or getattr(config, "llm_params", None) or {})
    params["max_tokens"] = 160          # short, snappy in-character lines
    params.setdefault("temperature", 0.5)  # lower = more coherent Italian, fewer nonsense phrases

    # Second, faster model for the structured (json) extraction calls — intent,
    # item detection, counteroffer parsing. Same endpoint/key; quality model
    # still voices the lines. Configurable via env; set to "off"/"none" to reuse
    # the single model. Fast params are deliberately minimal (no reasoning_effort,
    # which non-reasoning models like llama-3.1-8b reject) and low max_tokens.
    fast_model: str | None = os.environ.get(
        "MANTELLA_MERCHANTMIND_FAST_MODEL", "llama-3.1-8b-instant").strip()
    fast_params: dict | None = {"temperature": 0.0, "max_tokens": 64}
    if not fast_model or fast_model.lower() in ("off", "none", "0", "disabled"):
        fast_model, fast_params = None, None
    return OpenAINegotiationLLM(base_url=base_url, model=model, api_key=api_key,
                                params=params, fast_model=fast_model, fast_params=fast_params)


def build_negotiation(llm_client, config, language: str = "en"):
    """Construct a negotiation driver for the current conversation.

    Controlled randomness (A5) is OFF unless ``MANTELLA_MERCHANTMIND_SEED`` is set:
    an integer gives reproducible jitter (same seed -> same run, good for a
    controlled study per participant); ``random``/``auto`` gives a time-based seed
    (pure variability). Absent -> deterministic (unchanged behaviour).
    """
    from src.merchantmind.graph.merchant_graph import MerchantNegotiation
    raw = os.environ.get("MANTELLA_MERCHANTMIND_SEED", "").strip().lower()
    if raw in ("random", "auto"):
        import time
        rng_seed = int(time.time())
    elif raw:
        try:
            rng_seed = int(raw)
        except ValueError:
            rng_seed = None
    else:
        rng_seed = None
    return MerchantNegotiation(base_dir_for(config), build_llm(llm_client, config),
                               language=language, rng_seed=rng_seed)


def npc_meta_for(character) -> dict:
    """Identity metadata used when first creating an NPC's state."""
    return {
        "name": getattr(character, "name", "") or "",
        "race": getattr(character, "race", "") or "",
        "role": "merchant",
        "is_merchant": True,
    }
