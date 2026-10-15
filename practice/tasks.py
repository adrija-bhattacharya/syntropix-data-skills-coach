"""SQL practice tasks over one small shop database.

The data is built to make the classic misconceptions *visible in the output*:

* customers 5 and 6 have no orders, so an INNER JOIN silently drops them;
* customer 4's city is NULL, so ``city = NULL`` returns nothing;
* order 104 has a NULL amount, so ``COUNT(amount)`` and ``COUNT(*)`` differ;
* most orders have several line items, so joining ``order_items`` and then
  summing ``orders.amount`` inflates every total by an integer factor.

Concept ids are the ``sql`` seed graph's (:mod:`domain_data`).  ``uses`` lists
the other concepts the task exercises.
"""

from __future__ import annotations

from dataclasses import dataclass

SHOP_DB = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT, signup_date TEXT);
CREATE TABLE products  (id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT, price REAL);
CREATE TABLE orders    (id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT,
                        status TEXT, amount REAL);
CREATE TABLE order_items (order_id INTEGER, product_id INTEGER, qty INTEGER);
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT NOT NULL, manager_id INTEGER);

INSERT INTO customers VALUES
  (1, 'Asha',  'Kolkata', '2025-01-10'),
  (2, 'Bilal', 'Mumbai',  '2025-02-03'),
  (3, 'Chen',  'Kolkata', '2025-02-20'),
  (4, 'Dana',  NULL,      '2025-03-05'),
  (5, 'Eshan', 'Delhi',   '2025-03-18'),
  (6, 'Farah', 'Mumbai',  '2025-04-01');

INSERT INTO products VALUES
  (10, 'Notebook',   'stationery',  4.5),
  (11, 'Pen set',    'stationery',  8.0),
  (12, 'SQL book',   'books',      32.0),
  (13, 'Stats book', 'books',      28.0),
  (14, 'Headphones', 'electronics', 45.0),
  (15, 'USB cable',  'electronics', 6.0);

INSERT INTO orders VALUES
  (100, 1, '2025-05-02', 'shipped',   40.5),
  (101, 1, '2025-05-20', 'shipped',   32.0),
  (102, 2, '2025-05-21', 'pending',   51.0),
  (103, 3, '2025-06-01', 'shipped',   36.5),
  (104, 3, '2025-06-15', 'cancelled', NULL),
  (105, 4, '2025-06-30', 'shipped',   60.0),
  (106, 2, '2025-07-04', 'shipped',   12.0);

INSERT INTO order_items VALUES
  (100, 10, 1), (100, 12, 1), (100, 15, 1),
  (101, 12, 1),
  (102, 14, 1), (102, 15, 1),
  (103, 13, 1), (103, 11, 1),
  (104, 10, 2),
  (105, 14, 1), (105, 15, 2), (105, 10, 1),
  (106, 15, 2);

INSERT INTO employees VALUES
  (1, 'Meera', NULL), (2, 'Nikhil', 1), (3, 'Ojas', 1), (4, 'Priya', 2), (5, 'Rohan', 2);
"""

SHOP_SCHEMA = {
    "customers": ("id", "name", "city", "signup_date"),
    "products": ("id", "name", "category", "price"),
    "orders": ("id", "customer_id", "order_date", "status", "amount"),
    "order_items": ("order_id", "product_id", "qty"),
    "employees": ("id", "name", "manager_id"),
}


@dataclass(frozen=True, slots=True)
class Distractor:
    """A wrong answer a known mistake produces - matching it diagnoses the mistake."""

    value: str
    concept: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class Task:
    """One practice task.  ``kind`` says how it is checked:

    * ``sql``    - ``reference`` is a query; results are compared in the SQLite sandbox
    * ``python`` - ``reference`` is Python that sets ``result``; run in the Python sandbox
    * ``excel``  - ``reference`` is a formula for ``cell`` on the practice sheet
    * ``value``  - ``reference`` is the answer (a number or one of ``options``)
    """

    id: str
    concept: str
    prompt: str
    reference: str
    ordered: bool = False
    uses: tuple[str, ...] = ()
    hint: str = ""
    kind: str = "sql"
    domain: str = "sql"
    cell: str = ""  # excel: the cell the formula goes in
    fill_down: bool = False  # excel: also check the formula copied one row down
    options: tuple[str, ...] = ()  # value: pick one of these
    tolerance: float = 0.0  # value: numeric tolerance
    distractors: tuple[Distractor, ...] = ()
    context: tuple[tuple[str, ...], ...] = ()  # value: a small table to reason about
    context_note: str = ""
    env: tuple[tuple[str, object], ...] = ()  # python: extra variables for the code
    hint2: str = ""  # second hint; SQL derives it from the reference's shape


TASKS: tuple[Task, ...] = (
    Task(
        "products_list",
        "select_from",
        "List every product's name and price.",
        "SELECT name, price FROM products",
    ),
    Task(
        "pricey_products",
        "where",
        "Names of the products that cost more than 20.",
        "SELECT name FROM products WHERE price > 20",
    ),
    Task(
        "top3_products",
        "order_limit",
        "The 3 most expensive products (name, price), most expensive first.",
        "SELECT name, price FROM products ORDER BY price DESC LIMIT 3",
        ordered=True,
    ),
    Task(
        "categories",
        "distinct",
        "Each product category, listed once.",
        "SELECT DISTINCT category FROM products",
    ),
    Task(
        "unknown_city",
        "null_logic",
        "Names of the customers whose city is unknown.",
        "SELECT name FROM customers WHERE city IS NULL",
        uses=("where",),
    ),
    Task(
        "order_totals",
        "aggregates",
        "The number of orders and the total of their amounts (two columns).",
        "SELECT COUNT(*), SUM(amount) FROM orders",
    ),
    Task(
        "orders_per_status",
        "group_by",
        "How many orders are in each status (status, count)?",
        "SELECT status, COUNT(*) FROM orders GROUP BY status",
        uses=("aggregates",),
    ),
    Task(
        "spend_per_customer",
        "group_by",
        "Total order amount per customer name (name, total), for customers with orders.",
        "SELECT c.name, SUM(o.amount) FROM customers c "
        "JOIN orders o ON o.customer_id = c.id GROUP BY c.name",
        uses=("aggregates", "inner_join"),
    ),
    Task(
        "repeat_customers",
        "having",
        "customer_id of every customer with more than one order.",
        "SELECT customer_id FROM orders GROUP BY customer_id HAVING COUNT(*) > 1",
        uses=("group_by",),
    ),
    Task(
        "order_customer",
        "inner_join",
        "Each order id with the name of the customer who placed it.",
        "SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id",
    ),
    Task(
        "orders_per_customer",
        "outer_join",
        "Every customer's name with their number of orders - customers with none show 0.",
        "SELECT c.name, COUNT(o.id) FROM customers c "
        "LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name",
        uses=("group_by", "aggregates"),
    ),
    Task(
        "employee_manager",
        "self_join",
        "Each employee's name with their manager's name (leave out the top boss).",
        "SELECT e.name, m.name FROM employees e JOIN employees m ON m.id = e.manager_id",
        uses=("inner_join",),
    ),
    Task(
        "above_average",
        "subqueries",
        "Names of the products priced above the average product price.",
        "SELECT name FROM products WHERE price > (SELECT AVG(price) FROM products)",
        uses=("aggregates",),
    ),
    Task(
        "big_spenders",
        "ctes",
        "Using WITH, find the customer_id of customers whose orders total more than 70.",
        "WITH t AS (SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id) "
        "SELECT customer_id FROM t WHERE total > 70",
        uses=("group_by",),
    ),
    Task(
        "price_band",
        "case_when",
        "Each product name with a band: 'budget' under 10, 'mid' 10 to 30, 'premium' above 30.",
        "SELECT name, CASE WHEN price < 10 THEN 'budget' WHEN price <= 30 THEN 'mid' "
        "ELSE 'premium' END FROM products",
    ),
    Task(
        "order_vs_customer_total",
        "window_functions",
        "Every order (id, customer_id, amount) alongside that customer's total order amount.",
        "SELECT id, customer_id, amount, SUM(amount) OVER (PARTITION BY customer_id) FROM orders",
        uses=("group_by",),
    ),
    Task(
        "ordered_or_books",
        "set_ops",
        "Product ids that were ever ordered, together with the ids of all 'books' (no repeats).",
        "SELECT product_id FROM order_items UNION SELECT id FROM products WHERE category = 'books'",
    ),
    Task(
        "orders_per_month",
        "date_fns_sql",
        "Number of orders per month, month written as YYYY-MM (month, count).",
        "SELECT strftime('%Y-%m', order_date), COUNT(*) FROM orders "
        "GROUP BY strftime('%Y-%m', order_date)",
        uses=("group_by",),
    ),
    Task(
        "shout_names",
        "string_fns_sql",
        "Every customer's name in upper case.",
        "SELECT UPPER(name) FROM customers",
    ),
)

TASKS_BY_ID: dict[str, Task] = {t.id: t for t in TASKS}

# first-level hint per concept: what to reach for, not the answer
CONCEPT_HINTS: dict[str, str] = {
    "select_from": "List the columns you need after SELECT, then name the table after FROM.",
    "where": "WHERE keeps only the rows whose condition is true.",
    "order_limit": "ORDER BY sorts (DESC for highest first); LIMIT keeps the top n rows.",
    "distinct": "DISTINCT removes repeated rows from the result.",
    "null_logic": "NULL means unknown: test it with IS NULL / IS NOT NULL, never with =.",
    "aggregates": "COUNT, SUM, AVG, MIN and MAX fold many rows into one value.",
    "group_by": "GROUP BY makes one row per group; every other column must be aggregated.",
    "having": "HAVING filters groups after GROUP BY; WHERE filters rows before it.",
    "inner_join": "JOIN ... ON matches rows from two tables; join only the tables you need.",
    "outer_join": "LEFT JOIN keeps every row of the left table, with NULLs where nothing matches.",
    "self_join": "Join a table to itself with two aliases, e.g. employees e and employees m.",
    "subqueries": "A query in brackets can produce a value to compare against.",
    "ctes": "WITH name AS (query) names a step you can then select from.",
    "case_when": "CASE WHEN ... THEN ... ELSE ... END picks a value per row, top condition first.",
    "window_functions": "f(...) OVER (PARTITION BY ...) computes per group but keeps every row.",
    "set_ops": "UNION stacks two results with the same columns and removes duplicates.",
    "date_fns_sql": "strftime('%Y-%m', date_column) turns a date into its year-month.",
    "string_fns_sql": "UPPER(), LOWER() and SUBSTR() change text values.",
}


def tasks_for(concept: str) -> list[Task]:
    """SQL tasks whose target is ``concept`` (accepts a role-graph ``sql.`` prefix).
    :func:`practice.catalogue.tasks_for` covers every domain."""
    bare = concept.removeprefix("sql.")
    return [t for t in TASKS if t.concept == bare]
