"""Concepts, resources and the prerequisite knowledge graph.

The *prerequisite* relation is on **concepts** (edge ``u -> v`` == "u is a
prerequisite of v").  **Resources** teach one or more concepts and carry a
difficulty and an expected study time.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import networkx as nx

NodeId = str


@dataclass(frozen=True, slots=True)
class Concept:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Resource:
    id: str
    concepts: tuple[str, ...]
    difficulty: float
    minutes: float
    kind: str = "lesson"  # lesson | practice | article | book | video | course | paper
    title: str = ""  # human title (discovered resources)
    url: str = ""  # link out (discovered resources)
    source: str = ""  # "wikipedia" | "mdn" | "mit_learn" | "youtube" | "arxiv" | ...

    @property
    def seconds(self) -> float:
        return self.minutes * 60.0

    def __post_init__(self) -> None:
        if not self.concepts:
            raise ValueError(f"resource {self.id!r} teaches no concepts")
        if self.minutes <= 0:
            raise ValueError(f"resource {self.id!r} has non-positive minutes")
        if self.difficulty < 0:
            raise ValueError(f"resource {self.id!r} has negative difficulty")


@dataclass(slots=True)
class KnowledgeGraph:
    concepts: dict[str, Concept]
    resources: dict[str, Resource]
    prereq: nx.DiGraph = field(default_factory=nx.DiGraph)
    _by_concept: dict[str, list[str]] | None = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------------ build
    @classmethod
    def build(
        cls,
        concepts: Iterable[Concept],
        prerequisites: Iterable[tuple[str, str]],
        resources: Iterable[Resource],
    ) -> KnowledgeGraph:
        cmap = {c.id: c for c in concepts}
        rmap = {r.id: r for r in resources}
        g = nx.DiGraph()
        g.add_nodes_from(cmap)
        for a, b in prerequisites:
            if a not in cmap or b not in cmap:
                raise ValueError(f"prerequisite {a!r}->{b!r} references an unknown concept")
            g.add_edge(a, b)
        for r in rmap.values():
            unknown = set(r.concepts) - set(cmap)
            if unknown:
                raise ValueError(f"resource {r.id!r} references unknown concepts {sorted(unknown)}")
        return cls(concepts=cmap, resources=rmap, prereq=g)

    # ------------------------------------------------------------- accessors
    @property
    def concept_ids(self) -> list[str]:
        return sorted(self.concepts)

    def _index(self) -> dict[str, list[str]]:
        if self._by_concept is None:
            idx: dict[str, list[str]] = {c: [] for c in self.concepts}
            for r in self.resources.values():
                for c in r.concepts:
                    idx.setdefault(c, []).append(r.id)
            self._by_concept = {c: sorted(v) for c, v in idx.items()}
        return self._by_concept

    def resources_for(self, concept_id: str) -> list[str]:
        """Candidate resources that teach ``concept_id`` (index built once)."""
        return list(self._index().get(concept_id, ()))

    def direct_prerequisites(self, concept_id: str) -> set[str]:
        return set(self.prereq.predecessors(concept_id))

    def all_prerequisites(self, concept_id: str) -> set[str]:
        """Every transitive prerequisite concept.  ``O(V + E)``."""
        return set(nx.ancestors(self.prereq, concept_id))

    def prerequisites_of_resource(self, resource_id: str) -> set[str]:
        """Concepts that must be mastered before studying this resource."""
        covered = set(self.resources[resource_id].concepts)
        req: set[str] = set()
        for c in covered:
            req |= self.direct_prerequisites(c)
        return req - covered

    def sink_concepts(self) -> list[str]:
        return sorted(c for c in self.concept_ids if self.prereq.out_degree(c) == 0)
