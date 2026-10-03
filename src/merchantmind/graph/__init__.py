"""MerchantGraph: LangGraph orchestration for adversarial merchant negotiation.

- ``state``          : the negotiation state schema
- ``llm``            : injectable LLM interface (+ OpenAI-compatible impl)
- ``nodes``          : the graph node implementations
- ``merchant_graph`` : builds the StateGraphs and the negotiation driver
"""

from src.merchantmind.graph.merchant_graph import MerchantNegotiation

__all__ = ["MerchantNegotiation"]
