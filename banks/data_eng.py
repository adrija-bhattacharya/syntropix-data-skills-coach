"""Data engineering skill-check items."""

from __future__ import annotations

MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "de_data_modeling": [
        (
            "A primary key must be:",
            ("unique and not null", "a number", "the first column", "indexed only"),
            0,
        ),
        (
            "Storing a customer's city on every order row is:",
            ("denormalised", "third normal form", "a surrogate key", "an index"),
            0,
        ),
    ],
    "dimensional_modeling": [
        (
            "The grain of a fact table is:",
            (
                "what one row represents",
                "its number of columns",
                "its size on disk",
                "its refresh rate",
            ),
            0,
        ),
        (
            "A dimension table holds:",
            (
                "descriptive attributes (who, what, where)",
                "only numeric measures",
                "logs",
                "staging data",
            ),
            0,
        ),
    ],
    "file_formats": [
        ("A columnar, compressed format good for analytics:", ("Parquet", "CSV", "JSON", "TXT"), 0),
        ("CSV files do NOT store:", ("column data types", "values", "a header row", "commas"), 0),
    ],
    "etl_elt": [
        (
            "In ELT, the transformation happens:",
            (
                "inside the warehouse after loading",
                "before extraction",
                "on the source system",
                "in the BI tool",
            ),
            0,
        ),
        (
            "dbt is mainly a tool for the ___ step:",
            ("transform", "extract", "load", "visualise"),
            0,
        ),
    ],
    "warehouses": [
        (
            "BigQuery and Snowflake separate:",
            ("storage from compute", "rows from columns", "SQL from Python", "users from roles"),
            0,
        ),
        (
            "A data warehouse is optimised for:",
            (
                "analytical queries over large data",
                "single-row updates",
                "file storage",
                "streaming video",
            ),
            0,
        ),
    ],
    "batch_stream": [
        (
            "Fraud alerts within seconds need:",
            ("streaming", "a nightly batch", "a weekly report", "manual export"),
            0,
        ),
        (
            "A nightly job loading yesterday's orders is:",
            ("batch processing", "stream processing", "CDC only", "real time"),
            0,
        ),
    ],
    "incremental_loads": [
        (
            "An incremental load reads:",
            (
                "only rows new or changed since the last run",
                "the whole table every time",
                "a random sample",
                "only deletes",
            ),
            0,
        ),
        (
            "A watermark is usually:",
            ("the max updated_at already loaded", "the row count", "a file name", "a primary key"),
            0,
        ),
    ],
    "dedup_keys": [
        (
            "Keep only the latest row per customer_id:",
            (
                "ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) = 1",
                "SELECT DISTINCT *",
                "GROUP BY *",
                "ORDER BY customer_id LIMIT 1",
            ),
            0,
        ),
        (
            "A surrogate key is:",
            (
                "a warehouse-generated id with no business meaning",
                "the email address",
                "the source system's id",
                "a foreign key",
            ),
            0,
        ),
    ],
    "idempotency": [
        (
            "An idempotent job run twice for the same day:",
            ("gives the same result as running once", "doubles the rows", "fails", "deletes data"),
            0,
        ),
        (
            "Plain INSERT of a day's data on a retry risks:",
            ("duplicate rows", "lost rows", "schema change", "nothing"),
            0,
        ),
    ],
    "scd": [
        (
            "SCD type 2 keeps history by:",
            (
                "adding a new row with validity dates",
                "overwriting the value",
                "deleting old rows",
                "adding a column per change",
            ),
            0,
        ),
        (
            "SCD type 1:",
            (
                "overwrites the old value",
                "keeps every version",
                "stores the previous value in another column",
                "never changes",
            ),
            0,
        ),
    ],
    "data_quality": [
        (
            "A 'not_null' test on order_id fails when:",
            ("some order_id is NULL", "order_id repeats", "the table is empty", "order_id is text"),
            0,
        ),
        (
            "Checking that every orders.customer_id exists in customers is a:",
            (
                "referential integrity (relationships) test",
                "uniqueness test",
                "freshness test",
                "volume test",
            ),
            0,
        ),
    ],
    "dbt_models": [
        (
            "In dbt, a model is:",
            (
                "a SELECT statement saved as a .sql file",
                "a Python class",
                "a table you create by hand",
                "a dashboard",
            ),
            0,
        ),
        (
            "{{ ref('stg_orders') }} lets dbt:",
            (
                "build models in dependency order",
                "skip tests",
                "connect to Airflow",
                "rename columns",
            ),
            0,
        ),
    ],
    "dbt_tests": [
        (
            "dbt's four generic tests are unique, not_null, accepted_values and:",
            ("relationships", "freshness", "volume", "schema"),
            0,
        ),
        (
            "dbt docs generate builds:",
            ("a site with model descriptions and lineage", "the tables", "test data", "a backup"),
            0,
        ),
    ],
    "orchestration": [
        (
            "In Airflow, a DAG is:",
            (
                "tasks with dependencies, run on a schedule",
                "a database",
                "a SQL dialect",
                "a dbt test",
            ),
            0,
        ),
        (
            "Task B should run only after task A succeeds:",
            ("A >> B", "B >> A", "A + B", "parallel(A, B)"),
            0,
        ),
    ],
    "partitioning": [
        (
            "Partitioning a table by date mostly speeds up queries that:",
            ("filter on date", "select all columns", "join on id", "sort by name"),
            0,
        ),
        (
            "Too many tiny partitions cause:",
            ("overhead and slow queries", "faster scans", "less storage", "nothing"),
            0,
        ),
    ],
    "spark_basics": [
        (
            "Spark transformations like filter() are:",
            ("lazy until an action runs", "run immediately", "only for SQL", "written in R"),
            0,
        ),
        (
            "A shuffle happens during:",
            ("groupBy / join across partitions", "filter", "select", "reading a file"),
            0,
        ),
    ],
    "containers_cloud": [
        (
            "A Docker image packages:",
            ("code with its dependencies", "only data", "only the OS", "a cloud account"),
            0,
        ),
        (
            "Object storage like S3/GCS stores:",
            ("files (objects) by key", "SQL tables only", "running containers", "emails"),
            0,
        ),
    ],
}

TASK: dict[str, tuple[str, str]] = {
    "incremental_loads": (
        "Last load watermark 2025-06-01. Source has 3 rows on 2025-05-30 and 4 after 2025-06-01. How many rows does the next incremental load read?",
        "4",
    ),
    "dedup_keys": (
        "Customer 7 has 3 versions of their row. After keeping ROW_NUMBER() = 1 per customer, how many rows remain for customer 7?",
        "1",
    ),
    "scd": (
        "A customer changed city twice under SCD type 2. How many rows does that customer have in the dimension?",
        "3",
    ),
}
