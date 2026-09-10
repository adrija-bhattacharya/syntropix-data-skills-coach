"""Claim D - self-healing prerequisite graph.

A curated edge is a hypothesis; learner trajectories are the evidence.  Given
enough *clean* attempts (every other prerequisite of the child already
satisfied), the Beta posterior on each edge separates genuine prerequisites
from spurious ones, and a watched non-edge that keeps predicting failure is
proposed.
"""

from __future__ import annotations

import random

from algorithms.graph_health import GraphEvidence
from config import settings
from model.cost import _prereq_mastery_now
from model.knowledge_graph import Concept, KnowledgeGraph, Resource

_TH = settings.mastery_threshold


def _kg(ids: list[str], edges: list[tuple[str, str]]) -> KnowledgeGraph:
    concepts = [Concept(i, i.upper()) for i in ids]
    resources = [Resource(f"{i}:r", (i,), 2.0, 10.0) for i in ids]
    return KnowledgeGraph.build(concepts, edges, resources)


def _simulate(
    ev: GraphEvidence,
    child: str,
    true_reqs: list[str],
    others: list[str],
    *,
    n: int,
    noise: float = 0.04,
    seed: int = 0,
) -> None:
    rng = random.Random(seed)
    pool = sorted({*true_reqs, *others})
    for _ in range(n):
        m = {c: rng.betavariate(2.2, 1.0) for c in pool}
        correct = all(m[q] >= _TH for q in true_reqs)
        if rng.random() < noise:
            correct = not correct
        ev.record(m, child, correct)


# --------------------------------------------------------------------------- #
def test_a_spurious_edge_is_pruned_and_a_real_one_confirmed() -> None:
    kg = _kg(["b", "x", "d"], [("b", "d"), ("x", "d")])  # truth: d needs only b
    ev = GraphEvidence.for_graph(kg, source="seed")
    _simulate(ev, "d", true_reqs=["b"], others=["x"], n=3000, seed=1)

    healed, report = ev.heal(kg)
    pruned = {(c.a, c.b) for c in report.pruned}
    assert ("x", "d") in pruned
    assert ("b", "d") not in pruned
    assert set(healed.prereq.predecessors("d")) == {"b"}
    assert healed.edge_confidence("b", "d") >= 0.8


def test_a_missing_edge_is_discovered() -> None:
    # given graph: root -> b -> d, root -> e ; truth: d needs BOTH b and e
    kg = _kg(
        ["root", "b", "e", "d"],
        [("root", "b"), ("root", "e"), ("b", "d")],
    )
    ev = GraphEvidence.for_graph(kg, source="seed")
    assert ("e", "d") in ev.candidates  # parallel to d, shares the ancestor `root`

    _simulate(ev, "d", true_reqs=["b", "e"], others=[], n=5000, seed=2)
    healed, report = ev.heal(kg)

    proposed = {(c.a, c.b) for c in (*report.added, *report.suggested)}
    assert ("e", "d") in proposed
    if report.added:
        assert healed.prereq.has_edge("e", "d")
        assert "d" not in healed.prereq.predecessors("d")  # still a DAG


def test_no_evidence_is_a_no_op() -> None:
    kg = _kg(["a", "b", "c"], [("a", "b"), ("b", "c")])
    ev = GraphEvidence.for_graph(kg, source="seed")
    healed, report = ev.heal(kg)
    assert report.clean
    assert set(healed.prereq.edges()) == set(kg.prereq.edges())


def test_low_confidence_edge_carries_less_prerequisite_debt() -> None:
    kg = _kg(["p", "q", "c"], [("p", "c"), ("q", "c")])
    hl = settings.seq_half_life_steps
    taught = {"p": 0, "q": 9}  # p decayed, q fresh

    kg.prereq["p"]["c"]["confidence"] = 1.0
    kg.prereq["q"]["c"]["confidence"] = 0.1
    m_p_heavy = _prereq_mastery_now(kg, "c", taught, position=10, half_life_steps=hl)

    kg.prereq["p"]["c"]["confidence"] = 0.1
    kg.prereq["q"]["c"]["confidence"] = 1.0
    m_q_heavy = _prereq_mastery_now(kg, "c", taught, position=10, half_life_steps=hl)

    # weighting toward the fresh prerequisite q raises the effective prereq mastery
    assert m_q_heavy > m_p_heavy
    assert 0.0 <= m_p_heavy <= 1.0 and 0.0 <= m_q_heavy <= 1.0


def test_dynamic_graph_edges_start_less_confident_than_seed_edges() -> None:
    kg = _kg(["a", "b"], [("a", "b")])
    seed = GraphEvidence.for_graph(kg, source="seed")
    dyn = GraphEvidence.for_graph(kg, source="dynamic")
    assert seed.edges[("a", "b")].prior_mean > dyn.edges[("a", "b")].prior_mean


def test_controlled_recovery_on_a_real_seed_graph() -> None:
    from algorithms.graph_health import simulate_recovery
    from domains import seed_graph

    kg = seed_graph("sql")
    rec = simulate_recovery(kg, learners=6000, perturb=2, seed=7)
    assert rec.precision_drop == 1.0  # every injected spurious edge dropped
    assert rec.recall >= 0.5  # at least half the hidden real edges recovered
    # no true edge was wrongly pruned, no bogus edge wrongly added
    wrong_prune = [c for c in rec.report.pruned if (c.a, c.b) not in rec.injected]
    wrong_add = [
        c for c in (*rec.report.added, *rec.report.suggested) if (c.a, c.b) not in rec.hidden
    ]
    assert not wrong_prune and not wrong_add
