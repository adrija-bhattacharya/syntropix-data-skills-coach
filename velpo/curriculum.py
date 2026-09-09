"""A small hand-authored algebra curriculum used by the demo, the API and tests.

Clearly labelled synthetic data - the benchmark numbers in ``benchmarks/`` are
the only measured claims, and those run on this same graph purely as a
controlled comparison between planners.
"""

from __future__ import annotations

from velpo.model.knowledge_graph import Concept, KnowledgeGraph, Resource

_CONCEPTS: list[tuple[str, str]] = [
    ("integers", "Integers & number line"),
    ("fractions", "Fractions"),
    ("decimals", "Decimals & percentages"),
    ("exponents", "Exponents"),
    ("roots", "Square & cube roots"),
    ("order_ops", "Order of operations"),
    ("expressions", "Algebraic expressions"),
    ("linear_eq", "Linear equations"),
    ("inequalities", "Linear inequalities"),
    ("systems", "Systems of equations"),
    ("quadratics", "Quadratic equations"),
    ("functions", "Functions & notation"),
    ("graphing", "Graphing lines"),
    ("word_problems", "Modelling word problems"),
]

_PREREQS: list[tuple[str, str]] = [
    ("integers", "fractions"),
    ("integers", "decimals"),
    ("integers", "exponents"),
    ("exponents", "roots"),
    ("integers", "order_ops"),
    ("fractions", "order_ops"),
    ("order_ops", "expressions"),
    ("expressions", "linear_eq"),
    ("linear_eq", "inequalities"),
    ("linear_eq", "systems"),
    ("linear_eq", "graphing"),
    ("linear_eq", "quadratics"),
    ("roots", "quadratics"),
    ("expressions", "functions"),
    ("functions", "graphing"),
    ("linear_eq", "word_problems"),
    ("systems", "word_problems"),
]

# (concept, difficulty, minutes, has a shorter "practice" alternative?)
_RESOURCES: list[tuple[str, float, float, bool]] = [
    ("integers", 1.0, 6, True),
    ("fractions", 2.0, 9, True),
    ("decimals", 2.0, 7, False),
    ("exponents", 2.0, 8, True),
    ("roots", 3.0, 8, True),
    ("order_ops", 2.0, 6, False),
    ("expressions", 3.0, 10, True),
    ("linear_eq", 3.0, 12, True),
    ("inequalities", 3.0, 9, False),
    ("systems", 4.0, 14, True),
    ("quadratics", 4.0, 15, True),
    ("functions", 3.0, 11, False),
    ("graphing", 3.0, 10, True),
    ("word_problems", 4.0, 13, True),
]


def build_curriculum() -> KnowledgeGraph:
    concepts = [Concept(cid, name) for cid, name in _CONCEPTS]
    resources: list[Resource] = []
    for cid, diff, minutes, has_practice in _RESOURCES:
        resources.append(Resource(f"{cid}:lesson", (cid,), diff, minutes, "lesson"))
        if has_practice:
            resources.append(
                Resource(f"{cid}:practice", (cid,), max(1.0, diff - 1.0), minutes * 0.6, "practice")
            )
    return KnowledgeGraph.build(concepts, _PREREQS, resources)
