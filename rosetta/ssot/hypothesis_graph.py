"""Hypothesis DAG operations.

Core operations for creating, updating, killing, and querying hypotheses
in the SSOT. All file I/O goes through this module — agents never
touch YAML directly.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from .schema import (
    Edge,
    EdgeType,
    Evidence,
    Hypothesis,
    HypothesisStatus,
    KillCondition,
    KillOutcome,
)

# Default SSOT directory
_DEFAULT_SSOT_DIR = os.environ.get("ROSETTA_SSOT_DIR", "./ssot")


def _hypotheses_dir(ssot_dir: str | Path | None = None) -> Path:
    d = Path(ssot_dir or _DEFAULT_SSOT_DIR) / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _hypothesis_path(hypothesis_id: str, ssot_dir: str | Path | None = None) -> Path:
    return _hypotheses_dir(ssot_dir) / f"{hypothesis_id}.yaml"


def _index_path(ssot_dir: str | Path | None = None) -> Path:
    return _hypotheses_dir(ssot_dir) / "_index.yaml"


# ── CRUD operations ──────────────────────────────────────────


def create_hypothesis(
    hypothesis_id: str,
    title: str,
    description: str,
    confidence: float = 0.5,
    impact: float = 0.5,
    gene: str | None = None,
    module: str | None = None,
    phase_created: int = 0,
    kill_conditions: list[KillCondition] | None = None,
    tags: list[str] | None = None,
    ssot_dir: str | Path | None = None,
) -> Hypothesis:
    """Create a new hypothesis and persist it."""
    h = Hypothesis(
        hypothesis_id=hypothesis_id,
        title=title,
        description=description,
        confidence=_clamp(confidence),
        impact=_clamp(impact),
        gene=gene,
        module=module,
        phase_created=phase_created,
        kill_conditions=kill_conditions or [],
        tags=tags or [],
    )
    save_hypothesis(h, ssot_dir)
    return h


def load_hypothesis(
    hypothesis_id: str,
    ssot_dir: str | Path | None = None,
) -> Hypothesis | None:
    """Load a hypothesis from disk. Returns None if not found."""
    path = _hypothesis_path(hypothesis_id, ssot_dir)
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text())
    return Hypothesis.model_validate(data)


def save_hypothesis(
    hypothesis: Hypothesis,
    ssot_dir: str | Path | None = None,
) -> None:
    """Persist a hypothesis to disk and regenerate the index."""
    hypothesis.updated_at = datetime.now(timezone.utc)
    path = _hypothesis_path(hypothesis.hypothesis_id, ssot_dir)
    path.write_text(yaml.dump(hypothesis.model_dump(mode="json"), default_flow_style=False, sort_keys=False))
    regenerate_index(ssot_dir)


def load_all_hypotheses(
    ssot_dir: str | Path | None = None,
) -> list[Hypothesis]:
    """Load all hypotheses from disk."""
    d = _hypotheses_dir(ssot_dir)
    hypotheses = []
    for p in sorted(d.glob("H*.yaml")):
        data = yaml.safe_load(p.read_text())
        hypotheses.append(Hypothesis.model_validate(data))
    return hypotheses


def next_hypothesis_id(ssot_dir: str | Path | None = None) -> str:
    """Generate the next sequential hypothesis ID (H001, H002, ...)."""
    existing = load_all_hypotheses(ssot_dir)
    if not existing:
        return "H001"
    max_num = max(int(h.hypothesis_id[1:]) for h in existing)
    return f"H{max_num + 1:03d}"


# ── Confidence & status updates ──────────────────────────────


def update_confidence(
    hypothesis_id: str,
    new_confidence: float,
    evidence: Evidence | None = None,
    ssot_dir: str | Path | None = None,
) -> Hypothesis:
    """Update a hypothesis's confidence score, optionally adding evidence."""
    h = load_hypothesis(hypothesis_id, ssot_dir)
    if h is None:
        raise ValueError(f"Hypothesis {hypothesis_id} not found")

    h.confidence = _clamp(new_confidence)
    # Reduce uncertainty as evidence accumulates
    h.uncertainty = max(0.1, h.uncertainty * 0.85)

    if evidence is not None:
        h.evidence.append(evidence)

    save_hypothesis(h, ssot_dir)
    return h


def kill_hypothesis(
    hypothesis_id: str,
    reason: str,
    hard: bool = False,
    ssot_dir: str | Path | None = None,
) -> Hypothesis:
    """Kill or demote a hypothesis."""
    h = load_hypothesis(hypothesis_id, ssot_dir)
    if h is None:
        raise ValueError(f"Hypothesis {hypothesis_id} not found")

    h.status = HypothesisStatus.KILLED if hard else HypothesisStatus.DEMOTED
    h.confidence = 0.0 if hard else max(0.05, h.confidence * 0.3)
    # Add kill evidence
    h.evidence.append(
        Evidence(
            evidence_id=f"kill_{hypothesis_id}",
            source="lead_decision",
            phase=0,
            direction="contradicts",
            strength=1.0 if hard else 0.7,
            summary=reason,
        )
    )
    save_hypothesis(h, ssot_dir)
    return h


# ── DAG traversal & propagation ──────────────────────────────


def propagate_evidence(
    hypothesis_id: str,
    evidence: Evidence,
    ssot_dir: str | Path | None = None,
) -> list[dict]:
    """Add evidence to a hypothesis and cascade through downstream DAG edges.

    Returns a list of diffs describing what changed.
    """
    diffs: list[dict] = []
    all_hypotheses = {h.hypothesis_id: h for h in load_all_hypotheses(ssot_dir)}

    source = all_hypotheses.get(hypothesis_id)
    if source is None:
        raise ValueError(f"Hypothesis {hypothesis_id} not found")

    # Update the source node
    old_conf = source.confidence
    source.evidence.append(evidence)

    if evidence.direction == "supports":
        delta = evidence.strength * 0.1
        source.confidence = _clamp(source.confidence + delta)
    else:
        delta = evidence.strength * 0.15
        source.confidence = _clamp(source.confidence - delta)

    source.uncertainty = max(0.1, source.uncertainty * 0.85)
    save_hypothesis(source, ssot_dir)

    diffs.append({
        "hypothesis_id": hypothesis_id,
        "old_confidence": old_conf,
        "new_confidence": source.confidence,
        "evidence_added": evidence.evidence_id,
    })

    # Cascade to downstream nodes
    for edge in source.edges_out:
        target = all_hypotheses.get(edge.target_id)
        if target is None or target.status == HypothesisStatus.KILLED:
            continue

        old_t_conf = target.confidence
        if edge.edge_type == EdgeType.SUPPORTS:
            # Supporting edge: target moves in same direction as source change
            target.confidence = _clamp(
                target.confidence + (source.confidence - old_conf) * edge.weight * 0.5
            )
        elif edge.edge_type == EdgeType.CONTRADICTS:
            # Contradicting edge: target moves opposite
            target.confidence = _clamp(
                target.confidence - (source.confidence - old_conf) * edge.weight * 0.5
            )
        elif edge.edge_type == EdgeType.DEPENDS_ON:
            # Dependency: if source drops below 0.3, target loses confidence
            if source.confidence < 0.3:
                target.confidence = _clamp(target.confidence * 0.7)

        if target.confidence != old_t_conf:
            save_hypothesis(target, ssot_dir)
            diffs.append({
                "hypothesis_id": target.hypothesis_id,
                "old_confidence": old_t_conf,
                "new_confidence": target.confidence,
                "propagated_from": hypothesis_id,
            })

    return diffs


def add_edge(
    source_id: str,
    target_id: str,
    edge_type: EdgeType,
    weight: float = 1.0,
    ssot_dir: str | Path | None = None,
) -> None:
    """Add a typed edge between two hypotheses."""
    source = load_hypothesis(source_id, ssot_dir)
    if source is None:
        raise ValueError(f"Hypothesis {source_id} not found")

    # Avoid duplicate edges
    for e in source.edges_out:
        if e.target_id == target_id and e.edge_type == edge_type:
            return

    source.edges_out.append(Edge(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        weight=weight,
    ))
    save_hypothesis(source, ssot_dir)


# ── Query operations (pre-digested views for the lead) ───────


def get_hypothesis_summary(
    hypothesis_id: str,
    ssot_dir: str | Path | None = None,
) -> str:
    """Get a pre-digested text summary of a hypothesis and its neighborhood.

    This is what the lead sees — NOT raw YAML.
    """
    h = load_hypothesis(hypothesis_id, ssot_dir)
    if h is None:
        return f"Hypothesis {hypothesis_id} not found."

    all_h = {x.hypothesis_id: x for x in load_all_hypotheses(ssot_dir)}

    lines = [
        f"## {h.hypothesis_id}: {h.title}",
        f"Status: {h.status.value} | Confidence: {h.confidence:.2f} | "
        f"Uncertainty: {h.uncertainty:.2f} | Impact: {h.impact:.2f}",
        f"Gene: {h.gene or 'N/A'} | Module: {h.module or 'N/A'}",
        "",
    ]

    if h.description:
        lines.append(f"Description: {h.description}")
        lines.append("")

    # Evidence summary
    if h.evidence:
        lines.append(f"### Evidence ({len(h.evidence)} items)")
        for e in h.evidence[-5:]:  # Last 5 most recent
            lines.append(
                f"  - [{e.direction}] {e.source} (phase {e.phase}, "
                f"strength {e.strength:.2f}): {e.summary}"
            )
        if len(h.evidence) > 5:
            lines.append(f"  ... and {len(h.evidence) - 5} earlier items")
        lines.append("")

    # Kill conditions
    if h.kill_conditions:
        lines.append("### Kill Conditions")
        for kc in h.kill_conditions:
            status = "TRIGGERED" if kc.triggered else "active"
            lines.append(
                f"  - [{status}] {kc.description} "
                f"({kc.metric} {kc.comparator} {kc.threshold})"
            )
            if kc.fallback:
                lines.append(f"    Fallback: {kc.fallback}")
        lines.append("")

    # Edges
    if h.edges_out:
        lines.append("### Connections")
        for edge in h.edges_out:
            target = all_h.get(edge.target_id)
            target_label = f"{target.title} ({target.confidence:.2f})" if target else edge.target_id
            lines.append(f"  → {edge.edge_type.value} → {target_label}")
        lines.append("")

    # Incoming edges
    incoming = []
    for other in all_h.values():
        for edge in other.edges_out:
            if edge.target_id == hypothesis_id:
                incoming.append((other, edge))
    if incoming:
        lines.append("### Incoming Connections")
        for other, edge in incoming:
            lines.append(
                f"  ← {edge.edge_type.value} ← {other.hypothesis_id}: "
                f"{other.title} ({other.confidence:.2f})"
            )

    return "\n".join(lines)


def get_frontier(
    ssot_dir: str | Path | None = None,
    top_n: int = 10,
) -> str:
    """Get hypotheses ranked by uncertainty * impact — what to investigate next.

    Returns a pre-digested text summary for the lead.
    """
    hypotheses = load_all_hypotheses(ssot_dir)
    active = [h for h in hypotheses if h.status == HypothesisStatus.ACTIVE]

    if not active:
        return "No active hypotheses. The pipeline needs to bootstrap initial hypotheses."

    ranked = sorted(active, key=lambda h: h.information_gain_score(), reverse=True)[:top_n]

    lines = ["## Investigation Frontier (ranked by uncertainty × impact)", ""]
    for i, h in enumerate(ranked, 1):
        score = h.information_gain_score()
        lines.append(
            f"{i}. **{h.hypothesis_id}**: {h.title}\n"
            f"   Score: {score:.3f} (uncertainty={h.uncertainty:.2f}, impact={h.impact:.2f}) | "
            f"Confidence: {h.confidence:.2f} | Evidence: {len(h.evidence)} items"
        )
    return "\n".join(lines)


def check_kill_conditions(
    ssot_dir: str | Path | None = None,
) -> str:
    """Scan all active hypotheses for triggered or near-triggered kill conditions.

    Returns a pre-digested summary for the lead to review and decide.
    """
    hypotheses = load_all_hypotheses(ssot_dir)
    active = [h for h in hypotheses if h.status == HypothesisStatus.ACTIVE]

    triggered = []
    near_triggered = []

    for h in active:
        for kc in h.kill_conditions:
            if kc.triggered:
                triggered.append((h, kc))
            # Near-triggered: confidence has dropped below 0.3
            elif h.confidence < 0.3:
                near_triggered.append((h, kc))

    if not triggered and not near_triggered:
        return "No kill conditions triggered or near-triggered."

    lines = []
    if triggered:
        lines.append("## TRIGGERED Kill Conditions")
        for h, kc in triggered:
            lines.append(
                f"- **{h.hypothesis_id}** ({h.title}): {kc.description}\n"
                f"  Outcome: {kc.outcome.value}"
            )
            if kc.fallback:
                lines.append(f"  Fallback available: {kc.fallback}")
        lines.append("")

    if near_triggered:
        lines.append("## Near-Triggered (low confidence)")
        for h, kc in near_triggered:
            lines.append(
                f"- **{h.hypothesis_id}** ({h.title}): confidence={h.confidence:.2f}\n"
                f"  Condition: {kc.description}"
            )

    return "\n".join(lines)


# ── Index management ─────────────────────────────────────────


def regenerate_index(ssot_dir: str | Path | None = None) -> None:
    """Auto-generate _index.yaml with compact adjacency list."""
    hypotheses = load_all_hypotheses(ssot_dir)

    index_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(hypotheses),
        "nodes": [],
        "edges": [],
    }

    for h in hypotheses:
        index_data["nodes"].append({
            "id": h.hypothesis_id,
            "title": h.title,
            "status": h.status.value,
            "confidence": h.confidence,
            "gene": h.gene,
        })
        for edge in h.edges_out:
            index_data["edges"].append({
                "source": edge.source_id,
                "target": edge.target_id,
                "type": edge.edge_type.value,
                "weight": edge.weight,
            })

    path = _index_path(ssot_dir)
    path.write_text(yaml.dump(index_data, default_flow_style=False, sort_keys=False))


# ── Helpers ──────────────────────────────────────────────────


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))
