"""MerchantMind: persistent reflective social memory for NPC merchants.

Additive, self-contained module implementing the
psycho-social "engine" that drives voice-driven adversarial negotiation:

- ``schema``   : structure and default factories for the per-NPC state
- ``store``    : per-(player, npc) JSON persistence
- ``salience`` : social salience evaluation and differential decay
- ``pricing``  : derivation of price modifier, behaviour and relationship stage

The voice path stays in Mantella's native streaming pipeline; this module is
imported additively and can be enabled/disabled per experimental condition.
"""

from src.merchantmind import schema, store, salience, pricing

__all__ = ["schema", "store", "salience", "pricing"]
