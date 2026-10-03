"""Backfill ``observed_outcome`` in the buyer-intent log (RQ1 post-processing).

Reads the research logs produced during play, matches each intent prediction to
what the buyer actually did, and writes ``buyer_intent_predictions_scored.csv``
with an ``observed_outcome`` and ``correct`` column, plus a quick accuracy print.

Usage:
    python scripts/backfill_observed_outcome.py \
        --logs "%USERPROFILE%/Documents/My Games/Mantella/data/merchantmind/logs"
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.merchantmind.analysis import backfill_observed_outcome


def main() -> None:
    default_logs = os.path.join(
        os.path.expanduser("~"), "Documents", "My Games", "Mantella",
        "data", "merchantmind", "logs")
    ap = argparse.ArgumentParser(description="Backfill observed_outcome for RQ1.")
    ap.add_argument("--logs", default=default_logs, help="MerchantMind logs directory")
    args = ap.parse_args()

    rows, out_path = backfill_observed_outcome(args.logs)
    scored = [r for r in rows if r.get("observed_outcome")]
    correct = sum(1 for r in scored if r.get("correct") == "1")
    print(f"Wrote {out_path}")
    print(f"Predictions: {len(rows)} | matched to an outcome: {len(scored)}")
    if scored:
        print(f"Top-1 accuracy (predicted_top == observed): {correct}/{len(scored)} "
              f"= {correct / len(scored):.2%}")
    else:
        print("No predictions could be matched to an outcome yet "
              "(play some negotiations first).")


if __name__ == "__main__":
    main()
