"""Data-engineering drills written in SQL against the shop database.

Same SQLite sandbox and fingerprints as the SQL track; ``distractors`` are
known-wrong queries - if the learner's result equals one, that mistake is named.
"""

from __future__ import annotations

from practice.content import D
from practice.tasks import Task


def de(
    id_: str,
    concept: str,
    prompt: str,
    ref: str,
    *,
    wrong: tuple[tuple[str, str, str, str], ...] = (),
    hint: str = "",
    ordered: bool = False,
) -> Task:
    return Task(
        id=id_,
        concept=concept,
        prompt=prompt,
        reference=ref,
        kind="sql",
        domain="data_eng",
        distractors=tuple(D(*w) for w in wrong),
        hint=hint,
        ordered=ordered,
    )


TASKS: tuple[Task, ...] = (
    de(
        "de_incremental",
        "incremental_loads",
        "Incremental load: the watermark is '2025-06-01'. Select the orders (id, order_date) placed strictly after it.",
        "SELECT id, order_date FROM orders WHERE order_date > '2025-06-01'",
        wrong=(
            (
                "SELECT id, order_date FROM orders WHERE order_date >= '2025-06-01'",
                "incremental_loads",
                "inclusive_watermark",
                "'>=' re-loads the watermark day's rows that the last run already loaded - load strictly after (>).",
            ),
        ),
        hint="Only rows newer than the last value you loaded.",
    ),
    de(
        "de_latest_order",
        "dedup_keys",
        "Deduplicate to each customer's most recent order: customer_id, order id, order_date.",
        "SELECT customer_id, id, order_date FROM (SELECT o.*, ROW_NUMBER() OVER (PARTITION BY customer_id "
        "ORDER BY order_date DESC) AS rn FROM orders o) WHERE rn = 1",
        wrong=(
            (
                "SELECT customer_id, id, order_date FROM (SELECT o.*, ROW_NUMBER() OVER (PARTITION BY customer_id "
                "ORDER BY order_date) AS rn FROM orders o) WHERE rn = 1",
                "dedup_keys",
                "kept_oldest",
                "Ordering ascending keeps each customer's oldest order - order by date DESC.",
            ),
        ),
        hint="ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ... DESC) and keep rn = 1.",
    ),
    de(
        "de_null_test",
        "data_quality",
        "A not_null test on orders.amount: return the ids of the rows that would fail it.",
        "SELECT id FROM orders WHERE amount IS NULL",
        hint="The failing rows are the ones where the column is missing.",
    ),
    de(
        "de_fact_revenue",
        "dimensional_modeling",
        "Build a small fact for a dashboard: revenue (qty × price) per product category (category, revenue).",
        "SELECT p.category, SUM(i.qty * p.price) FROM order_items i JOIN products p ON p.id = i.product_id GROUP BY p.category",
        wrong=(
            (
                "SELECT p.category, SUM(p.price) FROM order_items i JOIN products p ON p.id = i.product_id GROUP BY p.category",
                "dimensional_modeling",
                "ignored_qty",
                "Revenue is quantity × price at the order-item grain - the quantity was left out.",
            ),
        ),
        hint="Join the item facts to the product dimension, then aggregate by category.",
    ),
)
