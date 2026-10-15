"""Python and pandas practice tasks - run in the Python sandbox.

The shop database is preloaded as DataFrames (``customers``, ``products``,
``orders``, ``order_items``, ``employees``); ``pd`` and ``np`` are imported.
Each ``distractors`` value is a *known-wrong* solution: if the learner's
result equals what it produces, that mistake is named.
"""

from __future__ import annotations

from practice.content import D
from practice.tasks import Task

_SCORES = (("scores", [72, 85, 90, 64, 77]),)
_CITIES = (("cities", ["Delhi", "Mumbai", "Delhi", "Pune", "Mumbai", "Delhi"]),)


def py(
    id_: str,
    concept: str,
    prompt: str,
    reference: str,
    *,
    domain: str = "python_data",
    wrong: tuple[tuple[str, str, str, str], ...] = (),
    ordered: bool = False,
    hint: str = "",
    env: tuple[tuple[str, object], ...] = (),
    uses: tuple[str, ...] = (),
) -> Task:
    return Task(
        id=id_,
        concept=concept,
        prompt=prompt,
        reference=reference,
        kind="python",
        domain=domain,
        ordered=ordered,
        distractors=tuple(D(*w) for w in wrong),
        hint=hint,
        env=env,
        uses=uses,
    )


PANDAS: tuple[Task, ...] = (
    py(
        "pd_series_prices",
        "pandas_series",
        "result = a Series of product prices indexed by product name.",
        "result = products.set_index('name')['price']",
        hint="set_index('name') makes the names the labels; then pick the price column.",
    ),
    py(
        "pd_count_orders",
        "dataframe",
        "result = how many rows the orders DataFrame has.",
        "result = len(orders)",
        wrong=(
            (
                "result = len(orders.columns)",
                "dataframe",
                "rows_vs_columns",
                "That counts columns; len(df) or df.shape[0] counts rows.",
            ),
        ),
        hint="df.shape is (rows, columns).",
    ),
    py(
        "pd_select_cols",
        "selecting",
        "result = a DataFrame with just the name and price of every product.",
        "result = products[['name', 'price']]",
        wrong=(
            (
                "result = products['name']",
                "selecting",
                "one_column",
                "Single brackets give one column; a list of names in double brackets gives several.",
            ),
        ),
        hint="df[['a', 'b']] - a list inside the brackets.",
    ),
    py(
        "pd_cheap_stationery",
        "filtering",
        "result = names of products cheaper than 10 in the 'stationery' category.",
        "result = products[(products.price < 10) & (products.category == 'stationery')]['name']",
        wrong=(
            (
                "result = products[products.price < 10]['name']",
                "filtering",
                "missing_condition",
                "Only one condition was applied - combine both with & and brackets.",
            ),
        ),
        hint="Combine conditions with & and wrap each in parentheses.",
    ),
    py(
        "pd_price_tax",
        "new_columns",
        "result = each product's name and its price including 18% tax, rounded to 2 decimals (2 columns).",
        "result = products.assign(price_with_tax=(products.price * 1.18).round(2))[['name', 'price_with_tax']]",
        wrong=(
            (
                "result = products.assign(t=(products.price * 0.18).round(2))[['name', 't']]",
                "new_columns",
                "tax_not_total",
                "That's the tax on its own - multiply by 1.18 to get the price including tax.",
            ),
        ),
        hint="price * 1.18, then .round(2).",
    ),
    py(
        "pd_missing_amount",
        "missing_data",
        "result = how many orders have a missing amount.",
        "result = int(orders.amount.isna().sum())",
        wrong=(
            (
                "result = int((orders.amount == None).sum())",
                "missing_data",
                "nan_equality",
                "NaN never equals anything, not even None - use .isna().",
            ),
        ),
        hint=".isna() marks missing values; .sum() counts the Trues.",
    ),
    py(
        "pd_spend_per_customer",
        "groupby_agg",
        "result = the total order amount per customer_id.",
        "result = orders.groupby('customer_id')['amount'].sum()",
        wrong=(
            (
                "result = orders.amount.sum()",
                "groupby_agg",
                "missing_groupby",
                "That's one grand total - group by customer_id first.",
            ),
            (
                "result = orders.groupby('customer_id')['amount'].mean()",
                "groupby_agg",
                "wrong_aggregate",
                "That's the average; the question asks for the total (.sum()).",
            ),
        ),
        hint="df.groupby(key)[column].sum()",
    ),
    py(
        "pd_orders_per_customer",
        "merge_join",
        "result = every customer's name with their number of orders - customers with none show 0.",
        "m = customers.merge(orders, left_on='id', right_on='customer_id', how='left')\nresult = m.groupby('name')['id_y'].count()",
        wrong=(
            (
                "m = customers.merge(orders, left_on='id', right_on='customer_id')\nresult = m.groupby('name')['id_y'].count()",
                "merge_join",
                "inner_merge",
                "The default merge is inner: customers with no orders disappear. Use how='left'.",
            ),
            (
                "m = customers.merge(orders, left_on='id', right_on='customer_id', how='left')\nresult = m.groupby('name').size()",
                "missing_data",
                "size_counts_nan",
                ".size() counts the NaN row a left merge adds for 'no match'; .count() on an order column skips it.",
            ),
        ),
        hint="A left merge keeps every customer; count an order column, not rows.",
        uses=("groupby_agg",),
    ),
    py(
        "pd_concat_books_electronics",
        "concat",
        "result = the 'books' products and the 'electronics' products stacked into one table (name, category).",
        "b = products[products.category == 'books']\ne = products[products.category == 'electronics']\nresult = pd.concat([b, e])[['name', 'category']]",
        hint="pd.concat([df1, df2]) stacks rows.",
    ),
    py(
        "pd_pivot_status",
        "pivot_melt",
        "result = total amount with customer_id as rows and status as columns; empty combinations show 0.",
        "result = orders.pivot_table(index='customer_id', columns='status', values='amount', aggfunc='sum', fill_value=0)",
        wrong=(
            (
                "result = orders.pivot_table(index='customer_id', columns='status', values='amount', aggfunc='sum')",
                "pivot_melt",
                "no_fill",
                "Empty combinations are NaN - pass fill_value=0.",
            ),
        ),
        hint="pivot_table(index=..., columns=..., values=..., aggfunc='sum', fill_value=0)",
    ),
    py(
        "pd_category_code",
        "apply_map",
        "result = each product's name and a code: books→B, electronics→E, stationery→S (2 columns).",
        "result = products.assign(code=products.category.map({'books': 'B', 'electronics': 'E', 'stationery': 'S'}))[['name', 'code']]",
        hint="Series.map(a_dict) looks each value up in the dict.",
    ),
    py(
        "pd_orders_per_month",
        "datetime_pd",
        "result = the number of orders per month, months written 'YYYY-MM'.",
        "result = pd.to_datetime(orders.order_date).dt.strftime('%Y-%m').value_counts().sort_index()",
        wrong=(
            (
                "result = pd.to_datetime(orders.order_date).dt.month.value_counts().sort_index()",
                "datetime_pd",
                "month_number",
                "Month numbers lose the year - format as '%Y-%m'.",
            ),
        ),
        hint="pd.to_datetime(...).dt.strftime('%Y-%m')",
    ),
    py(
        "pd_upper_names",
        "string_methods_pd",
        "result = every customer's name in upper case.",
        "result = customers.name.str.upper()",
        hint="Text methods live under .str",
    ),
    py(
        "pd_top3_prices",
        "sort_rank",
        "result = the 3 most expensive products (name, price), most expensive first.",
        "result = products.sort_values('price', ascending=False).head(3)[['name', 'price']]",
        ordered=True,
        wrong=(
            (
                "result = products.sort_values('price').head(3)[['name', 'price']]",
                "sort_rank",
                "ascending",
                "sort_values sorts ascending by default - add ascending=False.",
            ),
            (
                "result = products.sort_values('price', ascending=False)[['name', 'price']]",
                "sort_rank",
                "no_head",
                "That's every product - .head(3) keeps the top three.",
            ),
        ),
        hint="sort_values(..., ascending=False).head(3)",
    ),
    py(
        "np_mean_price",
        "numpy_arrays",
        "result = the mean product price computed with NumPy, rounded to 2 decimals.",
        "result = round(float(np.mean(products.price.to_numpy())), 2)",
        hint="np.mean(array); round(x, 2).",
    ),
    py(
        "np_discount",
        "array_ops",
        "result = a NumPy array of every product price after a 10% discount, rounded to 2 decimals.",
        "result = np.round(products.price.to_numpy() * 0.9, 2)",
        wrong=(
            (
                "result = np.round(products.price.to_numpy() * 0.1, 2)",
                "array_ops",
                "discount_amount",
                "That's the discount itself - the discounted price is price * 0.9.",
            ),
        ),
        hint="Arithmetic on an array applies to every element.",
    ),
)

PYTHON: tuple[Task, ...] = (
    py(
        "py_last_score",
        "lists",
        "scores is a list. result = its last element.",
        "result = scores[-1]",
        domain="python",
        env=_SCORES,
        hint="Negative indexes count from the end.",
    ),
    py(
        "py_sum_above",
        "loops",
        "result = the sum of the scores above 75 (use a loop).",
        "total = 0\nfor s in scores:\n    if s > 75:\n        total += s\nresult = total",
        domain="python",
        env=_SCORES,
        wrong=(
            (
                "result = sum(scores)",
                "conditionals",
                "no_condition",
                "Every score was added - only add scores above 75.",
            ),
        ),
        hint="Loop, test with if, add to a running total.",
    ),
    py(
        "py_doubled",
        "comprehensions",
        "result = a list of each score of 77 or more, doubled.",
        "result = [s * 2 for s in scores if s >= 77]",
        domain="python",
        env=_SCORES,
        ordered=True,
        hint="[expr for x in xs if cond]",
    ),
    py(
        "py_city_counts",
        "dicts",
        "cities is a list. result = a dict mapping each city to how many times it appears.",
        "result = {}\nfor c in cities:\n    result[c] = result.get(c, 0) + 1",
        domain="python",
        env=_CITIES,
        hint="d.get(key, 0) + 1 avoids a KeyError for a new key.",
    ),
    py(
        "py_unique_cities",
        "tuples_sets",
        "result = the distinct cities, sorted alphabetically (a list).",
        "result = sorted(set(cities))",
        domain="python",
        env=_CITIES,
        ordered=True,
        hint="set() removes duplicates; sorted() returns a list.",
    ),
    py(
        "py_grade_fn",
        "functions",
        "Define grade(score) returning 'pass' for 70 or more, else 'fail'. result = [grade(s) for s in scores].",
        "def grade(score):\n    return 'pass' if score >= 70 else 'fail'\nresult = [grade(s) for s in scores]",
        domain="python",
        env=_SCORES,
        ordered=True,
        wrong=(
            (
                "result = ['pass' if s > 72 else 'fail' for s in scores]",
                "conditionals",
                "boundary",
                "Check the boundary: 70 or more passes (>= 70).",
            ),
        ),
        hint="def name(arg): ... return value",
    ),
    py(
        "py_email_domain",
        "strings",
        "email = 'asha.rao@example.com'. result = the part after the @.",
        "result = email.split('@')[1]",
        domain="python",
        env=(("email", "asha.rao@example.com"),),
        hint="str.split('@') gives a list of the two parts.",
    ),
    py(
        "py_avg_label",
        "conditionals",
        "result = 'high' if the average of scores is above 75, else 'low'.",
        "result = 'high' if sum(scores) / len(scores) > 75 else 'low'",
        domain="python",
        env=_SCORES,
        hint="average = sum / len",
    ),
    py(
        "py_safe_ints",
        "exceptions",
        "raw = ['4', 'x', '10', '7.5']. Convert each to int, skipping values that fail. result = the list of ints.",
        "result = []\nfor r in raw:\n    try:\n        result.append(int(r))\n    except ValueError:\n        pass",
        domain="python",
        ordered=True,
        env=(("raw", ["4", "x", "10", "7.5"]),),
        hint="try: int(r) except ValueError: skip it.",
    ),
    py(
        "py_fstring",
        "fstrings",
        "name = 'Asha', score = 72. result = the text 'Asha scored 72' built with an f-string.",
        "result = f'{name} scored {score}'",
        domain="python",
        env=(("name", "Asha"), ("score", 72)),
        hint="f'{variable} text'",
    ),
    py(
        "py_floor_mod",
        "operators",
        "result = a list [17 // 5, 17 % 5].",
        "result = [17 // 5, 17 % 5]",
        domain="python",
        ordered=True,
        hint="// is whole-number division, % is the remainder.",
    ),
    py(
        "py_variables",
        "variables",
        "price = 40, qty = 3. result = price times qty.",
        "result = price * qty",
        domain="python",
        env=(("price", 40), ("qty", 3)),
        hint="Assign with =, then use the names.",
    ),
)

TASKS: tuple[Task, ...] = PANDAS + PYTHON
