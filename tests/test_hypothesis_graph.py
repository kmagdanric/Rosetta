"""Tests for hypothesis graph operations."""

import pytest

from rosetta.ssot.schema import (
    EdgeType,
    Evidence,
    HypothesisStatus,
    KillCondition,
    KillOutcome,
)
from rosetta.ssot.hypothesis_graph import (
    add_edge,
    check_kill_conditions,
    create_hypothesis,
    get_frontier,
    get_hypothesis_summary,
    kill_hypothesis,
    load_all_hypotheses,
    load_hypothesis,
    next_hypothesis_id,
    propagate_evidence,
    update_confidence,
)
from rosetta.ssot.decision_log import get_decision_diff, log_decision, read_decisions
from rosetta.ssot.queue import (
    complete_experiment,
    dequeue_experiment,
    enqueue_experiment,
    get_queue,
)


class TestHypothesisGraph:
    def test_create_and_load(self, tmp_ssot_dir):
        h = create_hypothesis(
            hypothesis_id="H001",
            title="INPP5D is a viable AD target",
            description="Microglial phosphatase with strong GWAS signal",
            gene="INPP5D",
            module="Microglia / Innate Immunity",
            ssot_dir=tmp_ssot_dir,
        )
        assert h.hypothesis_id == "H001"

        loaded = load_hypothesis("H001", tmp_ssot_dir)
        assert loaded is not None
        assert loaded.title == h.title
        assert loaded.gene == "INPP5D"

    def test_load_nonexistent(self, tmp_ssot_dir):
        assert load_hypothesis("H999", tmp_ssot_dir) is None

    def test_next_hypothesis_id(self, tmp_ssot_dir):
        assert next_hypothesis_id(tmp_ssot_dir) == "H001"
        create_hypothesis("H001", "Test 1", "Desc", ssot_dir=tmp_ssot_dir)
        assert next_hypothesis_id(tmp_ssot_dir) == "H002"
        create_hypothesis("H002", "Test 2", "Desc", ssot_dir=tmp_ssot_dir)
        assert next_hypothesis_id(tmp_ssot_dir) == "H003"

    def test_update_confidence(self, tmp_ssot_dir):
        create_hypothesis("H001", "Test", "Desc", confidence=0.5, ssot_dir=tmp_ssot_dir)

        evidence = Evidence(
            evidence_id="E001",
            source="gwas",
            phase=1,
            strength=0.8,
            summary="Strong signal",
        )
        h = update_confidence("H001", 0.8, evidence=evidence, ssot_dir=tmp_ssot_dir)
        assert h.confidence == 0.8
        assert len(h.evidence) == 1
        assert h.uncertainty < 1.0  # Reduced

    def test_update_confidence_clamped(self, tmp_ssot_dir):
        create_hypothesis("H001", "Test", "Desc", ssot_dir=tmp_ssot_dir)
        h = update_confidence("H001", 1.5, ssot_dir=tmp_ssot_dir)
        assert h.confidence == 1.0

        h = update_confidence("H001", -0.5, ssot_dir=tmp_ssot_dir)
        assert h.confidence == 0.0

    def test_kill_hypothesis_soft(self, tmp_ssot_dir):
        create_hypothesis("H001", "Test", "Desc", confidence=0.6, ssot_dir=tmp_ssot_dir)
        h = kill_hypothesis("H001", "No DE signal", hard=False, ssot_dir=tmp_ssot_dir)
        assert h.status == HypothesisStatus.DEMOTED
        assert h.confidence < 0.6
        assert h.confidence > 0.0

    def test_kill_hypothesis_hard(self, tmp_ssot_dir):
        create_hypothesis("H001", "Test", "Desc", ssot_dir=tmp_ssot_dir)
        h = kill_hypothesis("H001", "Completely disproven", hard=True, ssot_dir=tmp_ssot_dir)
        assert h.status == HypothesisStatus.KILLED
        assert h.confidence == 0.0

    def test_load_all(self, tmp_ssot_dir):
        create_hypothesis("H001", "Test 1", "Desc", ssot_dir=tmp_ssot_dir)
        create_hypothesis("H002", "Test 2", "Desc", ssot_dir=tmp_ssot_dir)
        create_hypothesis("H003", "Test 3", "Desc", ssot_dir=tmp_ssot_dir)

        all_h = load_all_hypotheses(tmp_ssot_dir)
        assert len(all_h) == 3


class TestDAGOperations:
    def test_add_edge(self, tmp_ssot_dir):
        create_hypothesis("H001", "Source", "Desc", ssot_dir=tmp_ssot_dir)
        create_hypothesis("H002", "Target", "Desc", ssot_dir=tmp_ssot_dir)

        add_edge("H001", "H002", EdgeType.SUPPORTS, ssot_dir=tmp_ssot_dir)

        h = load_hypothesis("H001", tmp_ssot_dir)
        assert len(h.edges_out) == 1
        assert h.edges_out[0].target_id == "H002"
        assert h.edges_out[0].edge_type == EdgeType.SUPPORTS

    def test_add_edge_no_duplicates(self, tmp_ssot_dir):
        create_hypothesis("H001", "Source", "Desc", ssot_dir=tmp_ssot_dir)
        create_hypothesis("H002", "Target", "Desc", ssot_dir=tmp_ssot_dir)

        add_edge("H001", "H002", EdgeType.SUPPORTS, ssot_dir=tmp_ssot_dir)
        add_edge("H001", "H002", EdgeType.SUPPORTS, ssot_dir=tmp_ssot_dir)

        h = load_hypothesis("H001", tmp_ssot_dir)
        assert len(h.edges_out) == 1

    def test_propagate_evidence_supports(self, tmp_ssot_dir):
        create_hypothesis("H001", "Source", "Desc", confidence=0.5, ssot_dir=tmp_ssot_dir)
        create_hypothesis("H002", "Target", "Desc", confidence=0.5, ssot_dir=tmp_ssot_dir)
        add_edge("H001", "H002", EdgeType.SUPPORTS, ssot_dir=tmp_ssot_dir)

        evidence = Evidence(
            evidence_id="E001",
            source="test",
            phase=1,
            direction="supports",
            strength=0.8,
            summary="Strong support",
        )
        diffs = propagate_evidence("H001", evidence, ssot_dir=tmp_ssot_dir)

        assert len(diffs) >= 1  # At least source updated
        # Source should have increased confidence
        source = load_hypothesis("H001", tmp_ssot_dir)
        assert source.confidence > 0.5
        # Target should have increased too (supporting edge)
        target = load_hypothesis("H002", tmp_ssot_dir)
        assert target.confidence > 0.5

    def test_propagate_evidence_contradicts(self, tmp_ssot_dir):
        create_hypothesis("H001", "Source", "Desc", confidence=0.5, ssot_dir=tmp_ssot_dir)
        create_hypothesis("H002", "Target", "Desc", confidence=0.5, ssot_dir=tmp_ssot_dir)
        add_edge("H001", "H002", EdgeType.CONTRADICTS, ssot_dir=tmp_ssot_dir)

        evidence = Evidence(
            evidence_id="E001",
            source="test",
            phase=1,
            direction="supports",
            strength=0.8,
            summary="Source gains support",
        )
        diffs = propagate_evidence("H001", evidence, ssot_dir=tmp_ssot_dir)

        # Source increased, so contradicting target should decrease
        target = load_hypothesis("H002", tmp_ssot_dir)
        assert target.confidence < 0.5


class TestQueryOperations:
    def test_get_hypothesis_summary(self, tmp_ssot_dir):
        create_hypothesis(
            "H001",
            "INPP5D is viable",
            "Microglial phosphatase",
            gene="INPP5D",
            ssot_dir=tmp_ssot_dir,
        )
        summary = get_hypothesis_summary("H001", tmp_ssot_dir)
        assert "INPP5D" in summary
        assert "H001" in summary

    def test_get_hypothesis_summary_not_found(self, tmp_ssot_dir):
        summary = get_hypothesis_summary("H999", tmp_ssot_dir)
        assert "not found" in summary

    def test_get_frontier_empty(self, tmp_ssot_dir):
        result = get_frontier(tmp_ssot_dir)
        assert "No active" in result

    def test_get_frontier_ranked(self, tmp_ssot_dir):
        # High uncertainty * high impact = top of frontier
        create_hypothesis(
            "H001", "High value", "Desc",
            impact=0.9, ssot_dir=tmp_ssot_dir,
        )
        create_hypothesis(
            "H002", "Low value", "Desc",
            impact=0.1, ssot_dir=tmp_ssot_dir,
        )
        result = get_frontier(tmp_ssot_dir)
        assert result.index("H001") < result.index("H002")

    def test_check_kill_conditions_none(self, tmp_ssot_dir):
        create_hypothesis("H001", "Test", "Desc", ssot_dir=tmp_ssot_dir)
        result = check_kill_conditions(tmp_ssot_dir)
        assert "No kill conditions" in result

    def test_check_kill_conditions_triggered(self, tmp_ssot_dir):
        kc = KillCondition(
            condition_id="KC001",
            description="No instruments",
            metric="instrument_count",
            threshold=3,
            comparator="<",
            outcome=KillOutcome.CONDITIONAL_PIVOT,
            fallback="Use blood eQTLs",
            triggered=True,
        )
        create_hypothesis(
            "H001", "Test", "Desc",
            kill_conditions=[kc],
            ssot_dir=tmp_ssot_dir,
        )
        result = check_kill_conditions(tmp_ssot_dir)
        assert "TRIGGERED" in result
        assert "blood eQTLs" in result


class TestDecisionLog:
    def test_log_and_read(self, tmp_ssot_dir):
        log_decision(
            action="dispatch_worker",
            rationale="GWAS triage is the cheapest first step",
            hypothesis_id="H001",
            phase=1,
            ssot_dir=tmp_ssot_dir,
        )
        entries = read_decisions(tmp_ssot_dir)
        assert len(entries) == 1
        assert entries[0]["action"] == "dispatch_worker"

    def test_multiple_entries(self, tmp_ssot_dir):
        log_decision("create_hypothesis", "Bootstrap", ssot_dir=tmp_ssot_dir)
        log_decision("dispatch_worker", "Run GWAS", phase=1, ssot_dir=tmp_ssot_dir)
        log_decision("kill_hypothesis", "No DE signal", hypothesis_id="H005", ssot_dir=tmp_ssot_dir)

        entries = read_decisions(tmp_ssot_dir)
        assert len(entries) == 3

    def test_action_filter(self, tmp_ssot_dir):
        log_decision("create_hypothesis", "A", ssot_dir=tmp_ssot_dir)
        log_decision("dispatch_worker", "B", ssot_dir=tmp_ssot_dir)
        log_decision("dispatch_worker", "C", ssot_dir=tmp_ssot_dir)

        entries = read_decisions(tmp_ssot_dir, action_filter="dispatch_worker")
        assert len(entries) == 2

    def test_decision_diff(self, tmp_ssot_dir):
        log_decision("dispatch_worker", "GWAS triage", ssot_dir=tmp_ssot_dir)
        diff = get_decision_diff(ssot_dir=tmp_ssot_dir)
        assert "dispatch_worker" in diff
        assert "GWAS triage" in diff


class TestExperimentQueue:
    def test_enqueue_dequeue(self, tmp_ssot_dir):
        enqueue_experiment(
            experiment_type="gwas_triage",
            description="Run GWAS analysis on Bellenguez 2022",
            priority=1,
            ssot_dir=tmp_ssot_dir,
        )
        exp = dequeue_experiment(tmp_ssot_dir)
        assert exp is not None
        assert exp["experiment_type"] == "gwas_triage"
        assert exp["status"] == "in_progress"

    def test_priority_ordering(self, tmp_ssot_dir):
        enqueue_experiment("low_priority", "Low", priority=10, ssot_dir=tmp_ssot_dir)
        enqueue_experiment("high_priority", "High", priority=1, ssot_dir=tmp_ssot_dir)

        exp = dequeue_experiment(tmp_ssot_dir)
        assert exp["experiment_type"] == "high_priority"

    def test_dequeue_empty(self, tmp_ssot_dir):
        assert dequeue_experiment(tmp_ssot_dir) is None

    def test_get_queue_display(self, tmp_ssot_dir):
        enqueue_experiment("gwas", "GWAS run", priority=1, ssot_dir=tmp_ssot_dir)
        enqueue_experiment("expression", "DE analysis", priority=3, ssot_dir=tmp_ssot_dir)

        display = get_queue(tmp_ssot_dir)
        assert "gwas" in display
        assert "expression" in display

    def test_complete_experiment(self, tmp_ssot_dir):
        enqueue_experiment("test", "Test exp", ssot_dir=tmp_ssot_dir)
        exp = dequeue_experiment(tmp_ssot_dir)
        result = complete_experiment(exp["experiment_id"], "Success", tmp_ssot_dir)
        assert result["status"] == "completed"
