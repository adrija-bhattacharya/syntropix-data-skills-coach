from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from algorithms.pareto import dominates, epsilon_prune, is_dominated, non_dominated


def test_dominates() -> None:
    assert dominates((1, 1), (2, 2))
    assert dominates((1, 2), (1, 3))
    assert not dominates((1, 3), (2, 2))
    assert not dominates((1, 1), (1, 1))


def test_non_dominated_removes_dominated() -> None:
    pts = [(1.0, 5.0), (2.0, 2.0), (5.0, 1.0), (3.0, 3.0), (2.0, 2.0)]
    assert set(non_dominated(pts)) == {(1.0, 5.0), (2.0, 2.0), (5.0, 1.0)}


def test_front_has_no_internal_domination() -> None:
    pts = [(1.0, 5.0), (2.0, 3.0), (4.0, 2.0), (5.0, 1.0), (3.0, 4.0), (2.5, 2.5)]
    front = non_dominated(pts)
    assert all(not dominates(a, b) for a in front for b in front if a != b)


def test_epsilon_prune_bounds_and_stays_valid() -> None:
    pts = [(float(i), 100.0 - i) for i in range(100)]
    pruned = epsilon_prune(pts, 10.0)
    assert len(pruned) < len(non_dominated(pts))
    assert all(not dominates(a, b) for a in pruned for b in pruned if a != b)


@settings(max_examples=100, deadline=None)
@given(
    st.lists(st.tuples(st.floats(0, 9), st.floats(0, 9), st.floats(0, 9)), min_size=1, max_size=30)
)
def test_every_point_represented_or_dominated(pts: list[tuple[float, float, float]]) -> None:
    front = non_dominated(pts)
    for p in pts:
        assert tuple(map(float, p)) in front or is_dominated(p, front)
