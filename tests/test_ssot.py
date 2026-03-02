"""Tests for SSOT schema models."""

from datetime import datetime, timezone

import pytest

from rosetta.ssot.schema import (
    Edge,
    EdgeType,
    Evidence,
    Hypothesis,
    HypothesisStatus,
    KillCondition,
    KillOutcome,
)


class TestHypothesis:
    def test_create_default(self):
        h = Hypothesis(
            hypothesis_id="H001",
            title="INPP5D is a viable AD target",
            description="Test hypothesis",
        )
        assert h.hypothesis_id == "H001"
        assert h.status == HypothesisStatus.ACTIVE
        assert h.confidence == 0.5
        assert h.uncertainty == 1.0
        assert h.impact == 0.5
        assert h.evidence == []
        assert h.kill_conditions == []

    def test_information_gain_score(self):
        h = Hypothesis(
            hypothesis_id="H001",
            title="Test",
            description="Test",
            uncertainty=0.8,
            impact=0.9,
        )
        assert h.information_gain_score() == pytest.approx(0.72)

    def test_serialization_roundtrip(self):
        h = Hypothesis(
            hypothesis_id="H001",
            title="Test",
            description="Test",
            gene="INPP5D",
            module="Microglia / Innate Immunity",
            evidence=[
                Evidence(
                    evidence_id="E001",
                    source="gwas_triage",
                    phase=1,
                    direction="supports",
                    strength=0.8,
                    summary="Genome-wide significant",
                )
            ],
            kill_conditions=[
                KillCondition(
                    condition_id="KC001",
                    description="No DE signal",
                    metric="de_fdr",
                    threshold=0.05,
                    comparator=">",
                    outcome=KillOutcome.SOFT_KILL,
                )
            ],
            edges_out=[
                Edge(
                    source_id="H001",
                    target_id="H002",
                    edge_type=EdgeType.SUPPORTS,
                )
            ],
        )
        data = h.model_dump(mode="json")
        h2 = Hypothesis.model_validate(data)
        assert h2.hypothesis_id == h.hypothesis_id
        assert h2.evidence[0].evidence_id == "E001"
        assert h2.kill_conditions[0].outcome == KillOutcome.SOFT_KILL
        assert h2.edges_out[0].edge_type == EdgeType.SUPPORTS


class TestEvidence:
    def test_create(self):
        e = Evidence(
            evidence_id="E001",
            source="gwas_triage",
            phase=1,
            strength=0.9,
            summary="Strong GWAS signal",
        )
        assert e.direction == "supports"
        assert isinstance(e.timestamp, datetime)


class TestKillCondition:
    def test_default_not_triggered(self):
        kc = KillCondition(
            condition_id="KC001",
            description="No instruments",
            metric="instrument_count",
            threshold=3,
            comparator="<",
        )
        assert not kc.triggered
        assert kc.outcome == KillOutcome.SOFT_KILL

    def test_with_fallback(self):
        kc = KillCondition(
            condition_id="KC002",
            description="Brain eQTL power failure",
            metric="instrument_count",
            threshold=3,
            comparator="<",
            outcome=KillOutcome.CONDITIONAL_PIVOT,
            fallback="Pivot to blood eQTLs (eQTLGen, N=31684)",
        )
        assert kc.fallback is not None
        assert kc.outcome == KillOutcome.CONDITIONAL_PIVOT
