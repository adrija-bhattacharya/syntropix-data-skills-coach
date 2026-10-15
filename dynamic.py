"""Dynamic prerequisite-graph construction for an arbitrary goal.

No seed graph exists for every possible goal, so build one from Wikipedia:

1. Resolve the goal to a canonical article; take the wikilinks in its **lead
   section** as candidate related concepts (plus one hop out).
2. Orient edges by an **asymmetric-link** heuristic: if ``B``'s lead links to
   ``A`` but ``A``'s lead does not link back, ``A`` is the more foundational
   concept - an edge ``A -> B`` (A is a prerequisite of B).
3. Drop people, disambiguation pages, identifiers and domain-root terms; cap the
   graph to a plannable size; run the N1 cycle-removal pass.
4. Attach a synthetic ``lesson`` + ``practice`` per concept (``harvest`` can swap
   in real resources afterwards).

Best-effort and clearly labelled - the curated seeds in :mod:`domains` are the
reliable path; this covers the long tail.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import networkx as nx

from algorithms.graph_traversal import remove_cycles
from harvest.http import OfflineError, get_json
from model.knowledge_graph import Concept, KnowledgeGraph, Resource

_CACHE = Path(__file__).resolve().parent / "harvest" / "data"
_WIKI = "https://en.wikipedia.org/w/api.php"
_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
_MAX_NODES = 16

_DROP_TITLE = re.compile(
    r"\((identifier|disambiguation)\)|^ISBN$|^Doi|^List of |^Category:|"
    r"^(Mathematics|Computer science|Economics|Physics|Engineering|Science|"
    r"Aerospace engineering|Biology|Chemistry|Statistics|Operations research)$",
    re.IGNORECASE,
)
_PERSON = re.compile(
    r"\b(is|was) an? [\w\s]{0,30}(mathematician|scientist|physicist|engineer|economist|"
    r"programmer|professor|researcher|author|philosopher|logician)\b|\(born ",
    re.IGNORECASE,
)
_BROAD = re.compile(
    r"^[A-Z][a-z-]+ ?[a-z-]* (is|are) (an?|the) (field|branch|area|discipline|study) "
    r"(of|in)\b",
    re.IGNORECASE,
)


def _slug(goal: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", goal.strip().lower()).strip("_")


def _lead_links(title: str) -> list[str]:
    url = (
        f"{_WIKI}?action=parse&page={title.replace(' ', '_')}"
        "&prop=links&section=0&redirects=1&format=json"
    )
    data = get_json(url, delay=1.2)  # the parse API throttles hard
    links = data.get("parse", {}).get("links", [])
    return [ln["*"] for ln in links if ln.get("ns") == 0 and ln.get("exists") is not None]


def _summary(title: str) -> dict[str, Any]:
    try:
        return dict(get_json(_REST.format(title.replace(" ", "_")), delay=0.3))
    except Exception:  # a missing summary just means "keep, unjudged"
        return {}


def _keep(title: str, summ: dict[str, Any], *, is_goal: bool = False) -> bool:
    if _DROP_TITLE.search(title):
        return False
    if summ.get("type") == "disambiguation":
        return False
    extract = summ.get("extract", "")
    desc = f"{summ.get('description', '')} {extract[:140]}"
    if _PERSON.search(desc):
        return False
    return is_goal or not _BROAD.match(extract)


def build_dynamic_graph(goal: str, *, refresh: bool = False) -> tuple[KnowledgeGraph, list[str]]:
    snap = _CACHE / f"dynamic_{_slug(goal)}.json"
    if snap.exists() and not refresh:
        blob = json.loads(snap.read_text())
        return _assemble(blob["concepts"], [tuple(e) for e in blob["prereqs"]], blob["goal"]), [
            blob["goal"]
        ]

    try:
        root_summ = _summary(goal)
        root = str(root_summ.get("title") or goal).strip()
        candidates = _lead_links(root)[:16]
        lead: dict[str, list[str]] = {root: candidates}
        for c in candidates[:10]:  # one hop out, for edge orientation + centrality
            lead.setdefault(c, _lead_links(c))
    except OfflineError as exc:
        raise OfflineError(f"no cached dynamic graph for {goal!r} and network is off") from exc

    summaries = {root: root_summ, **{t: _summary(t) for t in candidates}}
    centrality: dict[str, int] = {}
    for links in lead.values():
        for t in links:
            centrality[t] = centrality.get(t, 0) + 1

    nodes = {
        t
        for t in candidates
        if _keep(t, summaries.get(t, {})) and (t in lead[root] or centrality.get(t, 0) >= 2)
    }
    nodes.add(root)

    edges: list[tuple[str, str]] = []
    for b in nodes:
        for a in lead.get(b, []):
            if a in nodes and a != b and b not in lead.get(a, []):
                edges.append((a, b))  # a is a prerequisite of b

    g = nx.DiGraph()
    g.add_nodes_from(nodes)
    g.add_edges_from(edges)
    g = _trim(g, root, _MAX_NODES)
    dag, _report = remove_cycles(g)

    concepts = {t: _title_to_label(t) for t in dag.nodes}
    prereqs = [(u, v) for u, v in dag.edges]
    kg = _assemble(concepts, prereqs, root)

    snap.parent.mkdir(exist_ok=True)
    snap.write_text(
        json.dumps({"goal": _slug(root), "concepts": concepts, "prereqs": prereqs}, indent=1)
    )
    return kg, [_slug(root)]


def _trim(g: nx.DiGraph, root: str, cap: int) -> nx.DiGraph:
    if g.number_of_nodes() <= cap:
        return g
    keep = {root}
    ranked = sorted(g.nodes, key=lambda n: g.degree(n), reverse=True)
    keep.update(ranked[: cap - 1])
    return g.subgraph(keep).copy()


def _title_to_label(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)$", "", title).strip()


def _assemble(
    concepts: dict[str, str], prereqs: list[tuple[str, str]], goal_title: str
) -> KnowledgeGraph:
    idmap = {t: _slug(t) for t in concepts}
    goal_id = _slug(goal_title)
    idmap.setdefault(goal_title, goal_id)

    cs = [Concept(idmap[t], label) for t, label in concepts.items()]
    if goal_id not in {c.id for c in cs}:
        cs.append(Concept(goal_id, _title_to_label(goal_title)))
    edges = [(idmap[a], idmap[b]) for a, b in prereqs if a in idmap and b in idmap]

    g = nx.DiGraph()
    g.add_nodes_from(c.id for c in cs)
    g.add_edges_from(edges)
    depth = dict.fromkeys(g, 0)
    for n in nx.topological_sort(g):
        for s in g.successors(n):
            depth[s] = max(depth[s], depth[n] + 1)
    dmax = max(depth.values(), default=1) or 1

    resources: list[Resource] = []
    for c in cs:
        diff = round(1.0 + 3.0 * depth.get(c.id, 0) / dmax, 1)
        minutes = round(9.0 + 3.0 * diff, 1)
        resources.append(Resource(f"{c.id}:lesson", (c.id,), diff, minutes, "lesson"))
        resources.append(
            Resource(
                f"{c.id}:practice",
                (c.id,),
                max(1.0, diff - 1.0),
                round(0.6 * minutes, 1),
                "practice",
            )
        )
    return KnowledgeGraph.build(cs, edges, resources)
