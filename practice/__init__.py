"""Execution-verified practice: run the learner's SQL in a sandbox, grade it by
its result, and fingerprint *why* a wrong answer is wrong as concepts."""

from practice.fingerprint import (
    Check,
    Diagnosis,
    Verdict,
    checks,
    diagnose,
    expected,
    grade,
    row_status,
    skeleton,
)
from practice.sandbox import ExecResult, describe_db, run_sql
from practice.tasks import SHOP_DB, SHOP_SCHEMA, TASKS, TASKS_BY_ID, Task, tasks_for

__all__ = [
    "SHOP_DB",
    "SHOP_SCHEMA",
    "TASKS",
    "TASKS_BY_ID",
    "Check",
    "Diagnosis",
    "ExecResult",
    "Task",
    "Verdict",
    "checks",
    "describe_db",
    "diagnose",
    "expected",
    "grade",
    "row_status",
    "run_sql",
    "skeleton",
    "tasks_for",
]
