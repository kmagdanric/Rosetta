"""Experiment queue for the pipeline.

Workers enqueue experiments they want run; the lead dequeues and
dispatches them. Persisted as YAML.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_SSOT_DIR = os.environ.get("ROSETTA_SSOT_DIR", "./ssot")


def _queue_path(ssot_dir: str | Path | None = None) -> Path:
    d = Path(ssot_dir or _DEFAULT_SSOT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d / "queue.yaml"


def _load_queue(ssot_dir: str | Path | None = None) -> list[dict[str, Any]]:
    path = _queue_path(ssot_dir)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, list) else []


def _save_queue(queue: list[dict[str, Any]], ssot_dir: str | Path | None = None) -> None:
    path = _queue_path(ssot_dir)
    path.write_text(yaml.dump(queue, default_flow_style=False, sort_keys=False))


def enqueue_experiment(
    experiment_type: str,
    description: str,
    hypothesis_id: str | None = None,
    priority: int = 5,
    parameters: dict[str, Any] | None = None,
    ssot_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Add an experiment to the queue.

    Parameters
    ----------
    experiment_type : str
        Type of experiment (e.g., "gwas_triage", "expression_de", "mr_analysis").
    description : str
        What this experiment will test.
    hypothesis_id : str, optional
        Which hypothesis this experiment targets.
    priority : int
        1 (highest) to 10 (lowest). Default 5.
    parameters : dict, optional
        Experiment-specific parameters.

    Returns
    -------
    The enqueued experiment dict.
    """
    queue = _load_queue(ssot_dir)

    entry = {
        "experiment_id": f"EXP{len(queue) + 1:03d}",
        "experiment_type": experiment_type,
        "description": description,
        "hypothesis_id": hypothesis_id,
        "priority": priority,
        "parameters": parameters or {},
        "status": "pending",
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    }

    queue.append(entry)
    # Sort by priority (lower = higher priority)
    queue.sort(key=lambda x: x["priority"])
    _save_queue(queue, ssot_dir)

    return entry


def dequeue_experiment(
    ssot_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    """Remove and return the highest-priority pending experiment."""
    queue = _load_queue(ssot_dir)

    for i, entry in enumerate(queue):
        if entry["status"] == "pending":
            entry["status"] = "in_progress"
            entry["started_at"] = datetime.now(timezone.utc).isoformat()
            _save_queue(queue, ssot_dir)
            return entry

    return None


def get_queue(ssot_dir: str | Path | None = None) -> str:
    """Get a human-readable summary of the experiment queue."""
    queue = _load_queue(ssot_dir)

    if not queue:
        return "Experiment queue is empty."

    pending = [e for e in queue if e["status"] == "pending"]
    in_progress = [e for e in queue if e["status"] == "in_progress"]

    lines = [f"## Experiment Queue ({len(pending)} pending, {len(in_progress)} in progress)"]

    if in_progress:
        lines.append("\n### In Progress")
        for e in in_progress:
            lines.append(f"- {e['experiment_id']} [{e['experiment_type']}]: {e['description']}")

    if pending:
        lines.append("\n### Pending (by priority)")
        for e in pending:
            hyp = f" (→ {e['hypothesis_id']})" if e.get("hypothesis_id") else ""
            lines.append(
                f"- {e['experiment_id']} [P{e['priority']}] "
                f"{e['experiment_type']}{hyp}: {e['description']}"
            )

    return "\n".join(lines)


def complete_experiment(
    experiment_id: str,
    result_summary: str | None = None,
    ssot_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    """Mark an experiment as completed."""
    queue = _load_queue(ssot_dir)

    for entry in queue:
        if entry["experiment_id"] == experiment_id:
            entry["status"] = "completed"
            entry["completed_at"] = datetime.now(timezone.utc).isoformat()
            if result_summary:
                entry["result_summary"] = result_summary
            _save_queue(queue, ssot_dir)
            return entry

    return None
