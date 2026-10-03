"""Injectable LLM interface for the MerchantGraph nodes.

The graph keeps all *numbers* (target price, concessions) rule-based and
auditable. The LLM is used only for natural
language: understanding what the player said (extracting an offered price and a
stance) and generating the in-character spoken line.

``NegotiationLLM`` is a small protocol so tests can inject a deterministic fake.
``OpenAINegotiationLLM`` is the production implementation against any
OpenAI-compatible endpoint (the same one Mantella already uses, e.g. Ollama).
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, runtime_checkable

try:  # telemetry is optional; never let it break a negotiation
    from src.telemetry.latency_tracker import tracker as _latency_tracker
except Exception:  # pragma: no cover - defensive
    _latency_tracker = None


@runtime_checkable
class NegotiationLLM(Protocol):
    """Minimal LLM surface needed by the negotiation nodes.

    The optional ``label`` is the latency-tracker phase name for the call, so
    each node's LLM round-trip is measured separately (see §5.A of the docs).
    """

    def text(self, system: str, user: str, label: str = "",
             history: list | None = None) -> str:
        """Return a short free-text completion (an in-character line).

        ``history`` is an optional list of prior ``{"role", "content"}`` messages
        (the negotiation transcript) so the model keeps conversational memory of
        the turns so far without re-prompting everything.
        """
        ...

    def json(self, system: str, user: str, label: str = "") -> dict:
        """Return a parsed JSON object completion."""
        ...


def extract_json(raw: str) -> dict:
    """Best-effort extraction of the first JSON object from an LLM reply."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (ValueError, TypeError):
            return {}
    return {}


class OpenAINegotiationLLM:
    """Production LLM client over an OpenAI-compatible Chat Completions endpoint.

    Optionally uses a **second, faster model** for the structured (``json``)
    extraction calls — intent prediction, item detection, counteroffer parsing —
    while the quality model voices the in-character lines (``text``). Both run
    on the same endpoint / key. Structured extraction is easy, so a small fast
    model (e.g. Groq ``llama-3.1-8b-instant``) cuts those round-trips sharply
    without hurting dialogue quality. If ``fast_model`` is None the single model
    is used for everything (backwards compatible).
    """

    def __init__(self, base_url: str, model: str, api_key: str = "abc123",
                 params: dict[str, Any] | None = None, timeout: float = 60.0,
                 fast_model: str | None = None,
                 fast_params: dict[str, Any] | None = None) -> None:
        # Imported lazily so the module imports without the openai package present
        from openai import OpenAI
        self._client = OpenAI(base_url=base_url, api_key=api_key or "abc123", timeout=timeout)
        self._model = model
        self._params = params or {}
        # Fall back to the main model when no fast model is configured.
        self._fast_model = fast_model or model
        self._fast_params = fast_params if fast_params is not None else self._params

    def _chat(self, messages: list, *, model: str,
              params: dict[str, Any], label: str = "") -> str:
        # Some local params (eg "stop") are fine for chat; max_tokens kept modest.
        if label and _latency_tracker is not None:
            _latency_tracker.start(label)
        try:
            resp = self._client.chat.completions.create(
                model=model, messages=messages, **params)
            return (resp.choices[0].message.content or "").strip()
        finally:
            if label and _latency_tracker is not None:
                _latency_tracker.stop(label)

    def text(self, system: str, user: str, label: str = "mm_llm_dialogue",
             history: list | None = None) -> str:
        # In-character lines: the quality model, with the transcript as history so
        # the merchant "remembers" the conversation so far (conversational memory).
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user})
        return self._chat(messages, model=self._model, params=self._params, label=label)

    def json(self, system: str, user: str, label: str = "mm_llm_structured") -> dict:
        # Structured extraction: the fast model, with a graceful fallback to the
        # main model if the fast model is unavailable on this endpoint.
        system_json = system + "\n\nRespond with strict JSON only, no prose."
        messages = [{"role": "system", "content": system_json},
                    {"role": "user", "content": user}]
        try:
            raw = self._chat(messages, model=self._fast_model,
                             params=self._fast_params, label=label)
        except Exception:
            raw = self._chat(messages, model=self._model,
                            params=self._params, label=label)
        return extract_json(raw)
