"""Dataset adapters for the benchmark harness (novelty claim **N7**).

Every dataset is reduced to the *same* pair VELPO consumes elsewhere:

    (KnowledgeGraph, list_of_goal_concepts)

so `benchmarks/benchmark.py` runs one metric set (safe-behaviour, over-budget,
optimality gap, latency) across all of them.

Datasets
--------
``synthetic``
    The hand-authored algebra curriculum in ``curriculum.py``.  Fully offline.

``junyi``
    The **real prerequisite graph** of Junyi Academy (776 concepts, 985 edges).
    A 57-concept offline sample is bundled at
    ``benchmarks/data/junyi_prerequisite.sample.json``; ``full=True`` downloads
    the complete graph from the open mirror below and caches it under
    ``benchmarks/data/cache/``.

    Source : Junyi Academy Math Practicing Log
             http://base.ustc.edu.cn/data/ktbd/junyi/prerequisite.json
             (exercise-name -> index map: .../vertex_id2idx)
    The prerequisite edges are real.  Junyi ships no per-resource difficulty or
    study time, so the *resource layer* (one ``lesson`` + one ``practice`` per
    concept, difficulty from DAG depth, minutes from difficulty) is synthesised
    by :func:`_synthesise_resources` and clearly labelled as such.

Adding ASSISTments / EdNet is a new ``load_*`` here that ends in
:func:`knowledge_graph_from_edges`; their raw logs carry no prerequisite graph,
so they need an inferred one (out of scope for the course project - the hook is
here).
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import networkx as nx

from algorithms.graph_traversal import remove_cycles
from curriculum import build_curriculum
from model.knowledge_graph import Concept, KnowledgeGraph, Resource

_DATA = Path(__file__).resolve().parent / "data"
_CACHE = _DATA / "cache"
_JUNYI_BASE = "http://base.ustc.edu.cn/data/ktbd/junyi"

DATASETS = ("synthetic", "junyi")


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def load(name: str, *, full: bool = False) -> tuple[KnowledgeGraph, list[str]]:
    """``(knowledge_graph, goal_concepts)`` for one dataset name."""
    if name == "synthetic":
        kg = build_curriculum()
        return kg, kg.sink_concepts()
    if name == "junyi":
        return load_junyi(full=full)
    raise ValueError(f"unknown dataset {name!r}; choose from {DATASETS}")


# --------------------------------------------------------------------------- #
# junyi
# --------------------------------------------------------------------------- #
def load_junyi(*, full: bool = False) -> tuple[KnowledgeGraph, list[str]]:
    concepts, edges = _junyi_full_edges() if full else _junyi_sample_edges()
    kg = knowledge_graph_from_edges(concepts, edges)
    return kg, kg.sink_concepts()


def _junyi_sample_edges() -> tuple[list[str], list[tuple[str, str]]]:
    blob = json.loads((_DATA / "junyi_prerequisite.sample.json").read_text())
    return list(blob["concepts"]), [(a, b) for a, b in blob["prerequisites"]]


def _junyi_full_edges() -> tuple[list[str], list[tuple[str, str]]]:
    pre = json.loads(_fetch("prerequisite.json"))
    idx2name: dict[int, str] = {}
    for line in _fetch("vertex_id2idx").splitlines():
        if not line.strip():
            continue
        name, i = line.rsplit(",", 1)
        idx2name[int(i)] = name
    edges = [(idx2name[a], idx2name[b]) for a, b in pre if a in idx2name and b in idx2name]
    concepts = sorted({c for e in edges for c in e})
    return concepts, edges


def _fetch(fname: str) -> str:
    _CACHE.mkdir(parents=True, exist_ok=True)
    local = _CACHE / f"junyi_{fname}"
    if not local.exists():
        url = f"{_JUNYI_BASE}/{fname}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            local.write_bytes(resp.read())
    return local.read_text()


# --------------------------------------------------------------------------- #
# shared: edges -> KnowledgeGraph with a synthesised resource layer
# --------------------------------------------------------------------------- #
def knowledge_graph_from_edges(concepts: list[str], edges: list[tuple[str, str]]) -> KnowledgeGraph:
    """Build a :class:`KnowledgeGraph` from a bare prerequisite edge list.

    Real prerequisite graphs can contain cycles (annotation noise); we run the
    N1 cycle-removal pass (:func:`algorithms.graph_traversal.remove_cycles`) so
    the result is always a DAG.
    """
    g = nx.DiGraph()
    g.add_nodes_from(concepts)
    g.add_edges_from(edges)
    dag, _report = remove_cycles(g)

    kg_concepts = [Concept(c, _prettify(c)) for c in sorted(dag.nodes)]
    resources = _synthesise_resources(dag)
    clean_edges = [(u, v) for u, v in dag.edges]
    return KnowledgeGraph.build(kg_concepts, clean_edges, resources)


def _synthesise_resources(dag: nx.DiGraph) -> list[Resource]:
    """One ``lesson`` + one ``practice`` per concept.  Difficulty grows with the
    concept's depth in the DAG (longest prerequisite chain); study time grows
    with difficulty.  Deterministic - no randomness."""
    depth = _longest_path_depth(dag)
    dmax = max(depth.values(), default=1)
    out: list[Resource] = []
    for c in sorted(dag.nodes):
        diff = round(1.0 + 4.0 * depth[c] / dmax, 1)
        lesson_min = round(6.0 + 2.2 * diff, 1)
        out.append(Resource(f"{c}:lesson", (c,), diff, lesson_min, "lesson"))
        out.append(
            Resource(
                f"{c}:practice", (c,), max(1.0, diff - 1.0), round(0.6 * lesson_min, 1), "practice"
            )
        )
    return out


def _longest_path_depth(dag: nx.DiGraph) -> dict[str, int]:
    depth: dict[str, int] = {}
    for n in nx.topological_sort(dag):
        preds = list(dag.predecessors(n))
        depth[n] = 1 + max((depth[p] for p in preds), default=-1)
    return depth


def _prettify(concept_id: str) -> str:
    return concept_id.replace("_", " ").strip().capitalize()
