"""CLI: inject a world event into the running Mantella backend (mid-session).

Used by the experimenter during a session
to fire the "dragon slain" event so the relevant merchants react at the next
negotiation. Requires MerchantMind enabled (MANTELLA_MERCHANTMIND=1) and Mantella
running.

Usage:
    MantellaEnv/Scripts/python.exe scripts/inject_world_event.py --player "NomeDelTuoPG"
    # other presets:
    ...  --event dragon      (default; global, affects all merchants)
    ...  --event crime --city Whiterun
"""

import argparse
import json
import urllib.request

PRESETS = {
    "dragon": {"event_type": "world_event_global", "impact_radius": 2,
               "global_event_id": "MQ104_dragon_killed",
               "description": "il giocatore ha ucciso un drago e ha salvato la città."},
    "crime": {"event_type": "crime_witnessed", "impact_radius": 1,
              "description": "il giocatore è stato visto commettere un crimine."},
    "faction": {"event_type": "faction_joined", "impact_radius": 1,
                "description": "il giocatore si è unito a una fazione."},
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject a world event into Mantella.")
    parser.add_argument("--player", required=True, help="In-game player character name.")
    parser.add_argument("--event", default="dragon", choices=list(PRESETS))
    parser.add_argument("--city", default=None, help="Restrict to a city (for local events).")
    parser.add_argument("--port", type=int, default=4999)
    args = parser.parse_args()

    event = dict(PRESETS[args.event])
    if args.city:
        event["city"] = args.city
    body = json.dumps({"player_name": args.player, "event": event}).encode("utf-8")

    req = urllib.request.Request(f"http://localhost:{args.port}/world_event",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(json.dumps(json.loads(resp.read()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
