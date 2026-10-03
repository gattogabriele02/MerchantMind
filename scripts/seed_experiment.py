"""CLI: pre-load the three experiment merchants for a participant.

Run BEFORE each participant's session so the merchants start with the injected
histories (admiration / distrust / neutral) and fixed inventory prices.

Usage (from the repo root, with the Mantella venv):
    MantellaEnv/Scripts/python.exe scripts/seed_experiment.py --player "NomeDelTuoPG"

The player name MUST match the in-game player character name (what Skyrim sends
to Mantella). Re-running resets the merchants to their pre-loaded state.
"""

import argparse
import os
import sys

# Allow running as a plain script (add repo root to sys.path).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import utils
from src.merchantmind.experiment import seed_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the 3 experiment merchants.")
    parser.add_argument("--player", required=True,
                        help="In-game player character name (must match Skyrim).")
    parser.add_argument("--base-dir", default=None,
                        help="Override the merchantmind data dir (default: Mantella save folder).")
    args = parser.parse_args()

    base_dir = args.base_dir or os.path.join(
        utils.get_my_games_directory(custom_user_folder=""), "data", "merchantmind")

    result = seed_experiment(base_dir, args.player)

    print(f"\nSeeded {len(result)} merchants for player '{args.player}' in:\n  {base_dir}\n")
    print(f"{'npc_id':<18}{'condition':<14}{'price_modifier':<16}{'stage'}")
    print("-" * 60)
    for npc_id, state in result.items():
        rel = state["relationship_with_player"]
        pm = state["merchant_state"]["price_modifier"]
        # Look up the condition label from the spec order.
        from src.merchantmind.experiment import EXPERIMENT_MERCHANTS
        cond = next((m["condition"] for m in EXPERIMENT_MERCHANTS if m["npc_id"] == npc_id), "?")
        print(f"{npc_id:<18}{cond:<14}{pm:<16}{rel['relationship_stage']}")
    print("\nAtteso: admiration < neutral < distrust (prezzi crescenti).")


if __name__ == "__main__":
    main()
