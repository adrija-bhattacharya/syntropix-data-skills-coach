"""pandas & NumPy skill-check items."""

from __future__ import annotations

MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "numpy_arrays": [
        ("np.array([1, 2, 3]).shape is:", ("(3,)", "(1, 3)", "3", "(3, 1)"), 0),
        ("np.arange(4) gives:", ("[0 1 2 3]", "[1 2 3 4]", "[0 1 2 3 4]", "[4]"), 0),
    ],
    "array_ops": [
        ("np.array([1, 2]) * 3 gives:", ("[3 6]", "[1 2 1 2 1 2]", "9", "an error"), 0),
        ("(np.array([1, 5, 3]) > 2).sum() gives:", ("2", "1", "3", "8"), 0),
    ],
    "pandas_series": [
        (
            "A Series is:",
            ("a labelled 1-D array", "a 2-D table", "a Python list", "a dict of tables"),
            0,
        ),
        (
            "s = pd.Series([10, 20], index=['a', 'b']); s['b'] is:",
            ("20", "10", "'b'", "an error"),
            0,
        ),
    ],
    "dataframe": [
        ("df.shape for 100 rows and 5 columns is:", ("(100, 5)", "(5, 100)", "500", "100"), 0),
        (
            "df.head() shows by default:",
            ("the first 5 rows", "the first row", "the column names only", "10 random rows"),
            0,
        ),
    ],
    "read_write_data": [
        (
            "Read a CSV into a DataFrame:",
            (
                "pd.read_csv('f.csv')",
                "pd.open('f.csv')",
                "df.load('f.csv')",
                "csv.read_df('f.csv')",
            ),
            0,
        ),
        (
            "df.to_csv('out.csv', index=False) leaves out:",
            ("the index column", "the header", "the first row", "nothing"),
            0,
        ),
    ],
    "selecting": [
        ("df['city'] returns:", ("a Series", "a DataFrame", "a list", "a dict"), 0),
        ("df.loc[2, 'city'] selects by:", ("label", "position", "random", "dtype"), 0),
    ],
    "filtering": [
        (
            "Rows where amount > 50 AND status is 'shipped':",
            (
                "df[(df.amount > 50) & (df.status == 'shipped')]",
                "df[df.amount > 50 and df.status == 'shipped']",
                "df.filter(amount > 50)",
                "df.where('amount > 50')",
            ),
            0,
        ),
        (
            "df[df.city.isin(['Delhi', 'Mumbai'])] keeps rows where city:",
            ("is Delhi or Mumbai", "contains 'i'", "is not null", "is in the index"),
            0,
        ),
    ],
    "new_columns": [
        (
            "Add revenue = price * qty:",
            (
                "df['revenue'] = df.price * df.qty",
                "df.add('revenue')",
                "df.revenue := price*qty",
                "df.append(revenue)",
            ),
            0,
        ),
        (
            "df.assign(x=1) returns:",
            (
                "a new DataFrame with column x",
                "None",
                "the column x only",
                "the original, unchanged",
            ),
            0,
        ),
    ],
    "missing_data": [
        (
            "Count the missing values per column:",
            ("df.isna().sum()", "df.count()", "df.nulls()", "df == None"),
            0,
        ),
        (
            "df.amount.mean() when amount has NaNs:",
            ("skips the NaNs", "returns NaN", "counts them as 0", "raises an error"),
            0,
        ),
    ],
    "groupby_agg": [
        (
            "Total amount per customer:",
            (
                "df.groupby('customer_id')['amount'].sum()",
                "df.sum('customer_id')",
                "df.groupby('amount').customer_id",
                "df.agg('customer_id')",
            ),
            0,
        ),
        (
            "groupby(...).size() vs .count() differ because count():",
            ("skips NaN values", "counts groups", "sorts the result", "includes the index"),
            0,
        ),
    ],
    "merge_join": [
        (
            "Keep every customer, even those with no orders:",
            (
                "customers.merge(orders, how='left')",
                "customers.merge(orders, how='inner')",
                "pd.concat([customers, orders])",
                "orders.merge(customers, how='inner')",
            ),
            0,
        ),
        (
            "Merging orders (one row per order) with order_items (many per order) gives:",
            ("one row per item", "one row per order", "one row per customer", "an error"),
            0,
        ),
    ],
    "concat": [
        (
            "Stack two DataFrames with the same columns on top of each other:",
            ("pd.concat([a, b])", "a.merge(b)", "a.join(b)", "a + b"),
            0,
        ),
        (
            "After pd.concat([a, b]) the index may contain:",
            ("duplicate labels", "only NaN", "strings only", "nothing"),
            0,
        ),
    ],
    "pivot_melt": [
        (
            "Turn a wide table (one column per month) into long format:",
            ("df.melt(...)", "df.pivot(...)", "df.T", "df.stack(axis=2)"),
            0,
        ),
        (
            "pivot_table(index='region', columns='month', values='sales', aggfunc='sum') gives:",
            ("regions as rows, months as columns", "months as rows", "one long column", "a Series"),
            0,
        ),
    ],
    "apply_map": [
        (
            "Apply a function to every value of one column:",
            ("df.col.map(f)", "df.map_all(f)", "df.col(f)", "map(df, f)"),
            0,
        ),
        (
            "Vectorised df.a * 2 is usually ___ than df.a.apply(lambda x: x * 2):",
            ("faster", "slower", "the same speed", "less accurate"),
            0,
        ),
    ],
    "datetime_pd": [
        (
            "Parse a text date column:",
            ("pd.to_datetime(df.d)", "df.d.astype('date')", "datetime(df.d)", "df.d.parse()"),
            0,
        ),
        (
            "Month number from a datetime column:",
            ("df.d.dt.month", "df.d.month()", "df.d.str.month", "month(df.d)"),
            0,
        ),
    ],
    "string_methods_pd": [
        (
            "Upper-case a text column:",
            ("df.name.str.upper()", "df.name.upper()", "upper(df.name)", "df.name.UPPER"),
            0,
        ),
        (
            "df.email.str.contains('@gmail') returns:",
            ("a boolean Series", "the matching rows", "a count", "a list"),
            0,
        ),
    ],
    "sort_rank": [
        (
            "Largest amounts first:",
            (
                "df.sort_values('amount', ascending=False)",
                "df.sort('amount')",
                "df.order_by('amount')",
                "df.amount.sort()",
            ),
            0,
        ),
        (
            "rank(method='dense') for values 10, 20, 20, 30 gives:",
            ("1, 2, 2, 3", "1, 2, 3, 4", "1, 2, 2, 4", "0, 1, 1, 2"),
            0,
        ),
    ],
    "plot_pandas": [
        (
            "df.plot(x='month', y='sales') draws by default:",
            ("a line chart", "a pie chart", "a histogram", "nothing"),
            0,
        ),
        (
            "df.amount.plot.hist() shows:",
            (
                "the distribution of amount",
                "amount over time",
                "amount by category",
                "the mean only",
            ),
            0,
        ),
    ],
}

TASK: dict[str, tuple[str, str]] = {
    "numpy_arrays": ("What is np.array([2, 4, 6]).sum()?", "12"),
    "dataframe": ("A DataFrame has shape (120, 7). How many columns?", "7"),
    "missing_data": ("pd.Series([1, None, 3]).isna().sum() is:", "1"),
    "groupby_agg": ("Amounts per customer: A=10, A=5, B=7. What is the groupby sum for A?", "15"),
}
