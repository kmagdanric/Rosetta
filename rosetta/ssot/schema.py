"""Pydantic models for the SSOT hypothesis graph.

Defines the core data structures: Hypothesis nodes, Evidence records,
typed Edges between hypotheses, and KillConditions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EdgeType(str, Enum):
    """Typed relationships between hypothesis nodes."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"


class HypothesisStatus(str, Enum):
    """Lifecycle status of a hypothesis."""

    ACTIVE = "active"
    KILLED = "killed"
    DEMOTED = "demoted"
    GRADUATED = "graduated"  # Promoted to final target


class KillOutcome(str, Enum):
    """What happens when a kill condition triggers."""

    HARD_KILL = "hard_kill"
    SOFT_KILL = "soft_kill"
    CONDITIONAL_PIVOT = "conditional_pivot"


class KillCondition(BaseModel):
    """A pre-declared rule for when a hypothesis should be killed/demoted."""

    condition_id: str
    description: str
    metric: str  # e.g., "mr_pvalue", "de_fdr", "instrument_count"
    threshold: float
    comparator: str = ">"  # ">", "<", ">=", "<=", "=="
    outcome: KillOutcome = KillOutcome.SOFT_KILL
    fallback: str | None = None  # e.g., "pivot to blood eQTLs"
    triggered: bool = False
    triggered_at: datetime | None = None


class Evidence(BaseModel):
    """A piece of evidence supporting or contradicting a hypothesis."""

    evidence_id: str
    source: str  # e.g., "gwas_triage", "expression_filter", "mr_analysis"
    phase: int  # Pipeline phase that generated this
    direction: str = "supports"  # "supports" or "contradicts"
    strength: float = 0.0  # 0-1 scale
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str = ""


class Edge(BaseModel):
    """A typed edge in the hypothesis DAG."""

    source_id: str  # Hypothesis ID
    target_id: str  # Hypothesis ID
    edge_type: EdgeType
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Hypothesis(BaseModel):
    """A hypothesis node in the DAG.

    Represents a scientific claim like "INPP5D is a viable AD target".
    """

    hypothesis_id: str  # e.g., "H001"
    title: str
    description: str
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    confidence: float = 0.5  # 0-1 scale, starts at prior
    uncertainty: float = 1.0  # 0-1 scale, decreases as evidence accumulates
    impact: float = 0.5  # 0-1 scale, how important if true

    # Evidence collected
    evidence: list[Evidence] = Field(default_factory=list)

    # Kill conditions
    kill_conditions: list[KillCondition] = Field(default_factory=list)

    # Edges (stored on node for per-file serialization)
    edges_out: list[Edge] = Field(default_factory=list)

    # Metadata
    gene: str | None = None  # Associated gene symbol if applicable
    module: str | None = None  # Pathway module
    phase_created: int = 0
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def information_gain_score(self) -> float:
        """Rank by uncertainty * impact — higher means more worth investigating."""
        return self.uncertainty * self.impact
