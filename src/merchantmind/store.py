"""Persistence for per-NPC psycho-social state.

State is stored one JSON file per (player, npc) pair so the same merchant can
hold different relationships with different players, mirroring
``mantella_data/conversations/{player_name}/{npc_id}.json`` from the design doc.

The store is deliberately filesystem-only and takes an explicit ``base_dir`` so
it can be exercised in tests against a temp directory without any Mantella
config object.
"""

from __future__ import annotations

import json
import os
import re
import tempfile

from src.merchantmind import schema


def _sanitize(component: str) -> str:
    """Make a string safe to use as a single path component."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", component.strip())
    return cleaned or "unknown"


def state_path(base_dir: str, player_name: str, npc_id: str) -> str:
    """Resolve the on-disk path for a given (player, npc) state file."""
    return os.path.join(base_dir, _sanitize(player_name), f"{_sanitize(npc_id)}.json")


def load_state(base_dir: str, player_name: str, npc_id: str) -> dict | None:
    """Load a psycho-social state, or return None if it does not exist yet."""
    path = state_path(base_dir, player_name, npc_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_npc_ids(base_dir: str, player_name: str) -> list[str]:
    """List the npc ids that have a stored state for the given player."""
    player_dir = os.path.join(base_dir, _sanitize(player_name))
    if not os.path.isdir(player_dir):
        return []
    return [fn[:-5] for fn in os.listdir(player_dir) if fn.endswith(".json")]


def load_or_create(base_dir: str, player_name: str, npc_id: str, *,
                   name: str = "", is_merchant: bool = False,
                   race: str = "", role: str = "", city: str = "") -> dict:
    """Load an existing state or create (and persist) a fresh one."""
    existing = load_state(base_dir, player_name, npc_id)
    if existing is not None:
        return existing
    state = schema.new_psychosocial_state(
        npc_id, name, is_merchant=is_merchant, race=race, role=role, city=city)
    save_state(base_dir, player_name, state)
    return state


def save_state(base_dir: str, player_name: str, state: dict) -> str:
    """Atomically persist a psycho-social state. Returns the written path."""
    npc_id = state.get("npc_id")
    if not npc_id:
        raise ValueError("psycho-social state is missing 'npc_id'")
    schema.touch(state)
    path = state_path(base_dir, player_name, npc_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Write to a temp file in the same directory, then atomically replace.
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return path
