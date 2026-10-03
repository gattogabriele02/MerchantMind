"""Runtime anomaly detection on the merchant's spoken lines (RQ4, section 9).

The negotiation prompts impose a hard contract on each in-character line: speak
in the game language, *only* the single allowed number for that turn, no leaked
chain-of-thought, no breaking character. This module flags lines that violate
that contract so ``anomaly_log.csv`` gets populated during a session.

Pure and side-effect free (the caller does the logging), so it is fully unit
testable. Number detection is digit-based: it catches the common failure mode
(the model inventing a numeric anchor like "from 72 to 54") but not numbers
spelled out as words — a documented limitation.
"""

from __future__ import annotations

import re

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

# Phrases that betray the model breaking character / disclosing it is an AI.
_PERSONA_MARKERS = (
    "as an ai", "as a language model", "i am an ai", "i'm an ai",
    "large language model", "come modello linguistico", "come un'intelligenza artificiale",
    "non posso aiutarti come", "i cannot fulfill", "i can't fulfill",
)

# Markers of leaked reasoning / meta commentary (e.g. Qwen3 <think> leakage).
_REASONING_MARKERS = ("<think", "</think", "reasoning:", "chain of thought", "let me think")


def find_numbers(text: str) -> list[float]:
    """Extract numeric tokens from a line (handles ``,`` as decimal separator)."""
    out: list[float] = []
    for tok in _NUMBER_RE.findall(text or ""):
        try:
            out.append(float(tok.replace(",", ".")))
        except ValueError:
            pass
    return out


def detect_line_anomalies(line: str, *, allowed_numbers: list | None = None,
                          expect_line: bool = True, tolerance: float = 0.5) -> list[dict]:
    """Return a list of anomalies for one spoken line.

    Args:
        line: the raw line produced by the LLM.
        allowed_numbers: the only amounts the line may contain (e.g. the opening
            price, or the agreed price). An empty list means *no* number is
            allowed (e.g. a walkaway close). ``None`` disables the number check.
        expect_line: when True an empty line is itself an anomaly.
        tolerance: absolute gold tolerance when matching a spoken number.

    Each anomaly is ``{"category", "description", "raw_text"}`` — the shape
    :meth:`ResearchLogger.log_anomaly` expects.
    """
    anomalies: list[dict] = []
    text = (line or "").strip()
    if expect_line and not text:
        anomalies.append({"category": "empty_line",
                          "description": "no spoken line produced",
                          "raw_text": ""})
        return anomalies

    low = text.lower()
    if any(m in low for m in _REASONING_MARKERS):
        anomalies.append({"category": "reasoning_leak",
                          "description": "line contains leaked reasoning / meta text",
                          "raw_text": text[:200]})
    if any(m in low for m in _PERSONA_MARKERS):
        anomalies.append({"category": "persona_break",
                          "description": "line breaks character / discloses AI",
                          "raw_text": text[:200]})
    if allowed_numbers is not None:
        allowed = [round(float(a)) for a in allowed_numbers if a is not None]
        for n in find_numbers(text):
            if not any(abs(n - a) <= tolerance for a in allowed):
                allowed_str = ", ".join(str(a) for a in allowed) or "none"
                anomalies.append({
                    "category": "number_violation",
                    "description": f"line says {n:g}; only allowed: {allowed_str}",
                    "raw_text": text[:200]})
                break  # one violation per line is enough
    return anomalies
