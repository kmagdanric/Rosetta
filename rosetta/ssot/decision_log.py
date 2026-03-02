"""Append-only JSONL decision log.

Every decision the lead makes (dispatch, kill, pivot, update) is logged
here with a rationale. This is the audit trail for the pipeline.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_DEFAULT_SSOT_DIR = os.environ.get("ROSETTA_SSOT_DIR", "./ssot")


def _log_path(ssot_dir: str | Path | None = None) -> Path:
    d = Path(ssot_dir or _DEFAULT_SSOT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d / "decisions.jsonl"


def log_decision(
    action: str,
    rationale: str,
    hypothesis_id: str | None = None,
    phase: int | None = None,
    data: dict[str, Any] | None = None,
    ssot_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Append a decision to the log.

    Parameters
    ----------
    action : str
        What was decided (e.g., "dispatch_worker", "kill_hypothesis",
        "pivot_eqtl_source", "update_confidence", "create_hypothesis").
    rationale : str
        Why this decision was made — the lead's reasoning.
    hypothesis_id : str, optional
        Related hypothesis ID.
    phase : int, optional
        Pipeline phase when this decision was made.
    data : dict, optional
        Additional structured data.

    Returns
    -------
    The logged entry dict.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "rationale": rationale,
        "hypothesis_id": hypothesis_id,
        "phase": phase,
        "data": data or {},
    }

    path = _log_path(ssot_dir)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def read_decisions(
    ssot_dir: str | Path | None = None,
    since: str | None = None,
    action_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Read decisions from the log.

    Parameters
    ----------
    since : str, optional
        ISO timestamp — only return entries after this time.
    action_filter : str, optional
        Only return entries with this action type.

    Returns
    -------
    list of decision dicts.
    """
    path = _log_path(ssot_dir)
    if not path.exists():
        return []

    entries = []
    for line in path.read_text().strip().split("\n"):
        if not line:
            continue
        entry = json.loads(line)

        if since and entry["timestamp"] < since:
            continue
        if action_filter and entry["action"] != action_filter:
            continue

        entries.append(entry)

    return entries


def get_decision_diff(
    since: str | None = None,
    ssot_dir: str | Path | None = None,
) -> str:
    """Get a human-readable summary of recent decisions.

    This is what the lead calls to see what changed since last cycle.
    """
    entries = read_decisions(ssot_dir, since=since)

    if not entries:
        return "No decisions recorded" + (f" since {since}" if since else "") + "."

    lines = [f"## Decision Log ({len(entries)} entries)"]
    for e in entries[-20:]:  # Last 20
        hyp = f" [{e['hypothesis_id']}]" if e.get("hypothesis_id") else ""
        lines.append(f"- **{e['action']}**{hyp}: {e['rationale']}")

    if len(entries) > 20:
        lines.append(f"... and {len(entries) - 20} earlier entries")

    return "\n".join(lines)
