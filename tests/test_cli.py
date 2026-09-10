"""The ``python velpo.py`` entry point - one easy command per task."""

from __future__ import annotations

import contextlib
import io

import pytest

import velpo


def _run(*argv: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = velpo.main(list(argv))
    return rc, buf.getvalue()


def test_demo_prints_a_plan() -> None:
    rc, out = _run("demo", "--goal", "quadratics", "--minutes", "90")
    assert rc == 0
    assert "quadratics:" in out
    assert "steps -" in out


def test_demo_speed_changes_the_plan() -> None:
    _, fast = _run("demo", "--goal", "quadratics", "--minutes", "90", "--speed", "fast")
    _, slow = _run("demo", "--goal", "quadratics", "--minutes", "90", "--speed", "slow")
    assert fast != slow


def test_demo_rejects_unknown_goal() -> None:
    rc, out = _run("demo", "--goal", "not_a_concept")
    assert rc == 2 and "unknown goal" in out


def test_datasets_lists_both() -> None:
    rc, out = _run("datasets")
    assert rc == 0
    assert "synthetic" in out and "junyi" in out


def test_no_subcommand_errors() -> None:
    with pytest.raises(SystemExit):
        velpo.main([])
