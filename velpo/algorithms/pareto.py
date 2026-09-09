"""Non-dominated (Pareto) set utilities.

Every cost-vector component is "lower is better", so ``a`` **dominates** ``b``
iff ``a <= b`` component-wise and ``a < b`` somewhere.
"""

from __future__ import annotations

from collections.abc import Sequence

Vector = Sequence[float]
_EPS = 1e-12


def dominates(a: Vector, b: Vector) -> bool:
    return all(x <= y + _EPS for x, y in zip(a, b)) and any(x < y - _EPS for x, y in zip(a, b))


def is_dominated(v: Vector, others: Sequence[Vector]) -> bool:
    return any(dominates(o, v) for o in others)


def non_dominated(vectors: Sequence[Vector]) -> list[tuple[float, ...]]:
    """The Pareto-non-dominated subset, de-duplicated.  ``O(n^2 * d)``."""
    uniq: list[tuple[float, ...]] = []
    seen: set[tuple[float, ...]] = set()
    for v in vectors:
        t = tuple(float(x) for x in v)
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return [v for v in uniq if not any(dominates(o, v) for o in uniq if o != v)]


def epsilon_prune(front: Sequence[Vector], eps: float) -> list[tuple[float, ...]]:
    """Keep one representative per epsilon-grid cell to bound the front size.

    ``eps <= 0`` returns the exact non-dominated set.  ``O(n log n + n^2 d)``.
    """
    exact = non_dominated(front)
    if eps <= 0.0 or len(exact) <= 1:
        return exact
    best: dict[tuple[int, ...], tuple[float, ...]] = {}
    for v in exact:
        cell = tuple(int(x // eps) for x in v)
        if cell not in best or v < best[cell]:
            best[cell] = v
    return non_dominated(list(best.values()))
