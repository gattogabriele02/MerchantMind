"""Run the buyer-intent ablation (RQ1) and write a CSV of the results.

Compares predicted intent WITH vs WITHOUT customer history over a set of
utterances, using the real negotiation LLM. Reads the Groq key from
``secret_keys.json`` by default (same file Mantella uses).

Usage:
    python scripts/run_intent_ablation.py --out ablation_intent.csv
    python scripts/run_intent_ablation.py --model qwen/qwen3-32b --out out.csv
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.merchantmind.ablation import run_intent_ablation
from src.merchantmind.graph.llm import OpenAINegotiationLLM

INTENT_COLS = ["haggle_hard", "accept_quickly", "bundle_interest",
               "walkaway_likely", "intelligence_gathering"]


def _load_api_key(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Accept a few common shapes.
        for key in ("Groq", "GROQ_API_KEY", "groq", "secret_key"):
            if isinstance(data, dict) and data.get(key):
                return str(data[key])
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, str) and v.startswith("gsk_"):
                    return v
    except (OSError, ValueError):
        pass
    return os.environ.get("GROQ_API_KEY", "")


def main() -> None:
    ap = argparse.ArgumentParser(description="Buyer-intent ablation (RQ1).")
    ap.add_argument("--base-url", default="https://api.groq.com/openai/v1")
    ap.add_argument("--model", default="qwen/qwen3-32b")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--secret-keys", default="secret_keys.json")
    ap.add_argument("--out", default="ablation_intent.csv")
    args = ap.parse_args()

    api_key = args.api_key or _load_api_key(args.secret_keys)
    if not api_key:
        print("No API key found (pass --api-key or set secret_keys.json / GROQ_API_KEY).")
        sys.exit(1)

    llm = OpenAINegotiationLLM(
        base_url=args.base_url, model=args.model, api_key=api_key,
        params={"temperature": 0.0, "max_tokens": 200, "reasoning_effort": "none"})

    rows = run_intent_ablation(llm)
    fieldnames = ["condition", "utterance", "predicted_top"] + INTENT_COLS
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {args.out} ({len(rows)} rows).")
    # Quick eyeball: how often does the top label differ across conditions?
    by_utt: dict[str, dict] = {}
    for r in rows:
        by_utt.setdefault(r["utterance"], {})[r["condition"]] = r["predicted_top"]
    diffs = sum(1 for tops in by_utt.values()
                if len(set(tops.values())) > 1)
    print(f"Utterances where history changed the top intent: {diffs}/{len(by_utt)}")


if __name__ == "__main__":
    main()
