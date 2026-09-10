"""Self-healing prerequisite graph (novelty claim **D**).

A curated or Wikipedia-derived prerequisite graph is a *hypothesis*.  This module
attaches a **Bayesian confidence to every edge** and revises it from real learner
trajectories, then repairs the graph:

* **edge belief** ``P(a is a genuine prerequisite of c) ~ Beta(alpha, beta)`` -
  the prior comes from the edge's provenance (a hand-curated seed edge starts
  confident, a Wikipedia-asymmetry edge starts uncertain).
* **evidence**: every time a learner attempts ``c`` we look at their mastery of
  ``a`` at that moment.  The discriminating event is *attempting ``c`` without
  ``a``*: if they fail, ``a`` really does gate ``c`` (``alpha`` up); if they
  succeed, the edge is likely spurious (``beta`` up).  Having ``a`` and passing
  ``c`` is only weak evidence (many things gate ``c``).
* **repair** (:meth:`GraphEvidence.heal`): edges whose posterior mean falls below
  a threshold with enough support are **pruned**; watched non-edges (topologically
  parallel concepts that share structure) whose mean rises above a threshold are
  **suggested** (auto-added only when very confident and still acyclic).  Every
  surviving edge carries its posterior mean as ``confidence`` on the graph, and
  the cost model scales prerequisite debt by it - a shaky prerequisite bends
  instead of blocking.

The optimiser needs no change: it plans on the healed graph and reads the
per-edge ``confidence`` through :meth:`KnowledgeGraph.edge_confidence`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

import networkx as nx

from config import settings
from model.knowledge_graph import KnowledgeGraph

NodeId = str
Edge = tuple[NodeId, NodeId]
Action = Literal["prune", "suggest", "add", "strengthen", "weaken"]


# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class EdgeBelief:
    """Beta posterior over "this is a genuine prerequisite edge"."""

    alpha: float
    beta: float
    alpha0: float
    beta0: float

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def support(self) -> float:
        """Total pseudo-observations accumulated beyond the prior."""
        return (self.alpha - self.alpha0) + (self.beta - self.beta0)

    @property
    def prior_mean(self) -> float:
        return self.alpha0 / (self.alpha0 + self.beta0)

    def update(self, m_a: float, correct: bool) -> None:
        """One *clean* attempt at the child concept (every other prerequisite of
        the child was already satisfied).  ``m_a`` is the learner's mastery of the
        candidate prerequisite when they attempted the child."""
        theta = settings.mastery_threshold
        w = settings.graph_evidence_weight
        if m_a >= theta:
            # everything (incl. a) was in place: passing is uninformative, but
            # failing anyway is mild evidence a is not the real discriminator.
            if correct:
                self.alpha += 0.1 * w
            else:
                self.beta += 0.3 * w
        elif correct:  # had the other prereqs, lacked a, still passed -> a not required
            self.beta += w
        else:  # had the other prereqs, lacked a, failed -> a is the gate
            self.alpha += w


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class EdgeChange:
    a: NodeId
    b: NodeId
    a_name: str
    b_name: str
    action: Action
    mean: float
    prior_mean: float
    support: float

    @property
    def summary(self) -> str:
        arrow = f"{self.a_name} -> {self.b_name}"
        n = f"{self.support:.0f} obs"
        if self.action == "prune":
            return f"drop {arrow}: only {self.mean:.0%} of trajectories back it ({n})"
        if self.action in ("suggest", "add"):
            verb = "add" if self.action == "add" else "consider"
            return f"{verb} {arrow}: {self.mean:.0%} of learners lacking it struggled ({n})"
        if self.action == "strengthen":
            return f"{arrow} confirmed: {self.prior_mean:.0%} -> {self.mean:.0%}"
        return f"{arrow} weakened: {self.prior_mean:.0%} -> {self.mean:.0%}"


@dataclass(frozen=True, slots=True)
class GraphHealthReport:
    observations: int
    watched: int
    pruned: tuple[EdgeChange, ...] = ()
    added: tuple[EdgeChange, ...] = ()
    suggested: tuple[EdgeChange, ...] = ()
    reweighted: tuple[EdgeChange, ...] = ()

    @property
    def changed(self) -> int:
        return len(self.pruned) + len(self.added)

    @property
    def clean(self) -> bool:
        return not (self.pruned or self.added or self.suggested)


# --------------------------------------------------------------------------- #
_PRIORS: dict[str, tuple[float, float]] = {
    "seed": (6.0, 1.5),  # hand-curated - trust it until shown otherwise
    "role": (6.0, 1.5),
    "dynamic": (1.6, 1.6),  # Wikipedia asymmetry - a coin flip with a nudge
    "candidate": (1.0, 3.0),  # a non-edge we are only watching
}


@dataclass(slots=True)
class GraphEvidence:
    """Accumulates per-edge evidence for one knowledge graph."""

    source: str = "seed"
    edges: dict[Edge, EdgeBelief] = field(default_factory=dict)
    candidates: dict[Edge, EdgeBelief] = field(default_factory=dict)
    observations: int = 0
    _names: dict[NodeId, str] = field(default_factory=dict)
    _prereqs: dict[NodeId, frozenset[NodeId]] = field(default_factory=dict)
    _into: dict[NodeId, list[Edge]] = field(default_factory=dict)

    # ------------------------------------------------------------------ setup
    @classmethod
    def for_graph(cls, kg: KnowledgeGraph, *, source: str = "seed") -> GraphEvidence:
        ev = cls(source=source)
        ev._names = {cid: c.name for cid, c in kg.concepts.items()}
        ev._prereqs = {c: frozenset(kg.prereq.predecessors(c)) for c in kg.concepts}
        a0, b0 = _PRIORS.get(source, _PRIORS["seed"])
        for a, b in kg.prereq.edges():
            ev.edges[(a, b)] = EdgeBelief(a0, b0, a0, b0)
        ca, cb = _PRIORS["candidate"]
        for a, b in _candidate_pairs(kg):
            ev.candidates[(a, b)] = EdgeBelief(ca, cb, ca, cb)
        for table in (ev.edges, ev.candidates):
            for a, b in table:
                ev._into.setdefault(b, []).append((a, b))
        return ev

    # -------------------------------------------------------------- evidence
    def record(self, snapshot: dict[NodeId, float], concept: NodeId, correct: bool) -> None:
        """One learner attempted ``concept``; ``snapshot`` is their decayed
        mastery of every concept *before* this attempt."""
        self.observations += 1
        theta = settings.mastery_threshold
        into = self._into.get(concept, ())
        if not into:
            return
        # every incoming edge / candidate we currently *believe in* is a potential
        # confounder for the others - the graph de-confounds itself as beliefs move.
        believed = {
            a
            for (a, _b) in into
            if (self.edges.get((a, concept)) or self.candidates[(a, concept)]).mean >= theta - 0.05
        }
        for edge in into:
            a, _b = edge
            if a not in snapshot:
                continue
            # a *clean* test: every OTHER believed prerequisite of the child was
            # satisfied, so the outcome isolates whether `a` matters.  Confounded
            # attempts are discarded, not down-weighted.
            if any(snapshot.get(q, 0.0) < theta for q in believed if q != a):
                continue
            belief = self.edges.get(edge) or self.candidates[edge]
            belief.update(snapshot[a], correct)

    # ------------------------------------------------------------- accessors
    def confidence(self, a: NodeId, b: NodeId) -> float:
        belief = self.edges.get((a, b))
        return belief.mean if belief is not None else 1.0

    # ---------------------------------------------------------------- repair
    def heal(self, kg: KnowledgeGraph) -> tuple[KnowledgeGraph, GraphHealthReport]:
        min_prune = settings.graph_min_support_prune
        min_add = settings.graph_min_support_add
        prune_below = settings.graph_prune_below
        add_above = settings.graph_add_above
        auto_above = settings.graph_autoadd_above
        move = settings.graph_reweight_delta

        keep: list[Edge] = []
        pruned: list[EdgeChange] = []
        reweighted: list[EdgeChange] = []
        for (a, b), belief in self.edges.items():
            if belief.support >= min_prune and belief.mean <= prune_below:
                pruned.append(self._change(a, b, "prune", belief))
                continue
            keep.append((a, b))
            if belief.support >= 1 and abs(belief.mean - belief.prior_mean) >= move:
                act: Action = "strengthen" if belief.mean > belief.prior_mean else "weaken"
                reweighted.append(self._change(a, b, act, belief))

        base = nx.DiGraph()
        base.add_nodes_from(kg.concepts)
        base.add_edges_from(keep)

        added: list[EdgeChange] = []
        suggested: list[EdgeChange] = []
        for (a, b), belief in sorted(
            self.candidates.items(), key=lambda kv: kv[1].mean, reverse=True
        ):
            if belief.support < min_add or belief.mean < add_above:
                continue
            if base.has_edge(a, b) or nx.has_path(base, b, a) or nx.has_path(base, a, b):
                continue  # already implied, or would create a cycle
            if belief.mean >= auto_above:
                base.add_edge(a, b)
                added.append(self._change(a, b, "add", belief))
            else:
                suggested.append(self._change(a, b, "suggest", belief))

        healed = KnowledgeGraph.build(
            list(kg.concepts.values()),
            list(base.edges()),
            list(kg.resources.values()),
        )
        for a, b in healed.prereq.edges():
            healed.prereq[a][b]["confidence"] = round(self.confidence(a, b), 3)

        report = GraphHealthReport(
            observations=self.observations,
            watched=len(self.candidates),
            pruned=tuple(pruned),
            added=tuple(added),
            suggested=tuple(suggested),
            reweighted=tuple(reweighted),
        )
        return healed, report

    def _change(self, a: NodeId, b: NodeId, action: Action, belief: EdgeBelief) -> EdgeChange:
        return EdgeChange(
            a=a,
            b=b,
            a_name=self._names.get(a, a),
            b_name=self._names.get(b, b),
            action=action,
            mean=round(belief.mean, 3),
            prior_mean=round(belief.prior_mean, 3),
            support=round(belief.support, 1),
        )


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class RecoveryResult:
    """Outcome of a controlled graph-recovery experiment."""

    report: GraphHealthReport
    hidden: tuple[Edge, ...]  # real edges removed from the given graph
    injected: tuple[Edge, ...]  # spurious edges added to the given graph
    hidden_recovered: tuple[Edge, ...]  # of ``hidden``, which the healer proposed
    injected_pruned: tuple[Edge, ...]  # of ``injected``, which the healer dropped

    @property
    def recall(self) -> float:
        return len(self.hidden_recovered) / len(self.hidden) if self.hidden else 1.0

    @property
    def precision_drop(self) -> float:
        return len(self.injected_pruned) / len(self.injected) if self.injected else 1.0


def simulate_recovery(
    kg: KnowledgeGraph,
    *,
    learners: int = 4000,
    perturb: int = 2,
    noise: float = 0.06,
    seed: int = 0,
) -> RecoveryResult:
    """Controlled experiment: treat ``kg`` as ground truth, then hide ``perturb``
    real edges and inject ``perturb`` plausible spurious ones to make a
    *corrupted* graph.  Draw learner trajectories from the TRUE rule ("you pass a
    concept iff all its true prerequisites are mastered") and feed them into
    evidence built on the corrupted graph.  Returns what the healer recovered.
    """
    rng = random.Random(seed)
    theta = settings.mastery_threshold
    true_edges = list(kg.prereq.edges())
    order = list(nx.topological_sort(kg.prereq))
    rank = {c: i for i, c in enumerate(order)}

    hidden = tuple(rng.sample(true_edges, min(perturb, len(true_edges))))
    corrupt = nx.DiGraph()
    corrupt.add_nodes_from(kg.concepts)
    corrupt.add_edges_from(e for e in true_edges if e not in set(hidden))

    injected: list[Edge] = []
    tries = 0
    while len(injected) < perturb and tries < 500:
        tries += 1
        a, b = rng.sample(order, 2)
        if rank[a] < rank[b] and not corrupt.has_edge(a, b) and not nx.has_path(corrupt, b, a):
            corrupt.add_edge(a, b)
            injected.append((a, b))

    corrupt_kg = KnowledgeGraph.build(
        list(kg.concepts.values()), list(corrupt.edges()), list(kg.resources.values())
    )
    ev = GraphEvidence.for_graph(corrupt_kg, source="seed")
    true_reqs = {c: set(kg.prereq.predecessors(c)) for c in kg.concepts}
    children = [c for c in kg.concepts if true_reqs[c]]

    for _ in range(learners):
        mastery = {c: rng.betavariate(2.2, 1.0) for c in kg.concepts}
        for c in children:
            correct = all(mastery[q] >= theta for q in true_reqs[c])
            if rng.random() < noise:
                correct = not correct
            ev.record(mastery, c, correct)

    _healed, report = ev.heal(corrupt_kg)
    proposed = {(c.a, c.b) for c in (*report.added, *report.suggested)}
    dropped = {(c.a, c.b) for c in report.pruned}
    return RecoveryResult(
        report=report,
        hidden=hidden,
        injected=tuple(injected),
        hidden_recovered=tuple(e for e in hidden if e in proposed),
        injected_pruned=tuple(e for e in injected if e in dropped),
    )


# --------------------------------------------------------------------------- #
def _candidate_pairs(kg: KnowledgeGraph) -> list[Edge]:
    """Non-edges worth watching for a *missing* prerequisite: **incomparable**
    concepts (neither reaches the other) that sit in the same neighbourhood -
    they share an ancestor or a descendant.  Oriented toward the deeper concept
    so adding the edge can never create a cycle.  Ranked by how entangled the
    two concepts already are, capped at ``graph_max_candidates``."""
    g: nx.DiGraph = kg.prereq
    nodes = list(g.nodes())
    anc = {n: nx.ancestors(g, n) for n in nodes}
    desc = {n: nx.descendants(g, n) for n in nodes}
    scored: list[tuple[float, Edge]] = []
    for i, a in enumerate(nodes):
        for c in nodes[i + 1 :]:
            if a in anc[c] or c in anc[a] or g.has_edge(a, c) or g.has_edge(c, a):
                continue
            overlap = len(anc[a] & anc[c]) + len(desc[a] & desc[c])
            lo, hi = (a, c) if len(anc[a]) <= len(anc[c]) else (c, a)
            if overlap == 0:
                # no shared structure: only worth watching when the target looks
                # under-specified (<= 1 stated prerequisite) - a hidden edge often
                # leaves a concept looking like a root.  Watch both orientations.
                if g.in_degree(c) <= 1 and g.in_degree(a) <= 1:
                    scored.append((0.5, (a, c)))
                    scored.append((0.5, (c, a)))
                elif g.in_degree(hi) <= 1:
                    scored.append((0.5, (lo, hi)))
                continue
            scored.append((float(overlap), (lo, hi)))
    scored.sort(key=lambda t: t[0], reverse=True)
    seen: set[Edge] = set()
    out: list[Edge] = []
    for _s, e in scored:
        if e not in seen and not g.has_edge(*e):
            seen.add(e)
            out.append(e)
        if len(out) >= settings.graph_max_candidates:
            break
    return out
