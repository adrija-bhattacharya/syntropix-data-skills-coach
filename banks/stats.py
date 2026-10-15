"""Statistics skill-check items."""

from __future__ import annotations

MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "data_types_stats": [
        ("Customer satisfaction rated 1-5 is:", ("ordinal", "nominal", "continuous", "ratio"), 0),
        ("City names are:", ("nominal", "ordinal", "interval", "continuous"), 0),
    ],
    "descriptive": [
        (
            "For incomes with a few billionaires, the best 'typical' value is:",
            ("the median", "the mean", "the max", "the range"),
            0,
        ),
        ("The mean of 2, 4, 6, 8 is:", ("5", "4", "6", "20"), 0),
    ],
    "quartiles": [
        ("The interquartile range is:", ("Q3 - Q1", "max - min", "Q2 - Q1", "mean - median"), 0),
        (
            "50% of the data lies between:",
            ("Q1 and Q3", "min and Q1", "Q2 and max", "mean ± 1 SD"),
            0,
        ),
    ],
    "probability_basics": [
        ("P(heads twice) with a fair coin:", ("0.25", "0.5", "0.75", "1"), 0),
        ("If P(A) = 0.3, P(not A) is:", ("0.7", "0.3", "1.3", "0"), 0),
    ],
    "distributions": [
        (
            "In a normal distribution, about 95% of values lie within:",
            ("2 SD of the mean", "1 SD", "3 SD", "the IQR"),
            0,
        ),
        (
            "A long tail to the right means the distribution is:",
            ("right-skewed", "left-skewed", "symmetric", "uniform"),
            0,
        ),
    ],
    "sampling": [
        (
            "Surveying only your own app's users about 'all phone users' risks:",
            ("selection bias", "random error only", "overfitting", "nothing"),
            0,
        ),
        (
            "A simple random sample gives every member:",
            ("the same chance of selection", "a weight", "a group", "two chances"),
            0,
        ),
    ],
    "clt": [
        (
            "The central limit theorem says sample means are approximately:",
            ("normal for large n", "uniform", "skewed like the data", "always exact"),
            0,
        ),
        (
            "As n grows, the spread of sample means:",
            ("shrinks", "grows", "stays the same", "becomes zero at n = 30"),
            0,
        ),
    ],
    "standard_error": [
        ("Standard error of the mean is:", ("s / sqrt(n)", "s * n", "s / n", "sqrt(s)"), 0),
        (
            "Quadrupling the sample size makes the standard error:",
            ("half as large", "a quarter as large", "twice as large", "unchanged"),
            0,
        ),
    ],
    "confidence_intervals": [
        ("A 95% CI is (10, 14). The sample mean was:", ("12", "10", "14", "4"), 0),
        (
            "A wider confidence interval comes from:",
            ("a higher confidence level", "a larger sample", "less variance", "a smaller SD"),
            0,
        ),
    ],
    "hypothesis_testing": [
        (
            "The null hypothesis usually states:",
            (
                "no effect / no difference",
                "the effect you hope for",
                "the sample mean",
                "the p-value",
            ),
            0,
        ),
        (
            "Rejecting a true null hypothesis is a:",
            ("type I error", "type II error", "power", "confidence level"),
            0,
        ),
    ],
    "p_value": [
        (
            "p = 0.03 at α = 0.05 means you:",
            (
                "reject the null",
                "accept the null as proven",
                "prove the alternative",
                "need a bigger α",
            ),
            0,
        ),
        (
            "A p-value is the probability of data at least this extreme:",
            (
                "if the null were true",
                "that the null is true",
                "that the result is important",
                "of a type II error",
            ),
            0,
        ),
    ],
    "t_test": [
        (
            "Compare mean spend of two independent groups:",
            ("two-sample t-test", "paired t-test", "chi-square test", "correlation"),
            0,
        ),
        (
            "Same users measured before and after a change:",
            ("paired t-test", "two-sample t-test", "chi-square test", "ANOVA of one group"),
            0,
        ),
    ],
    "chi_square": [
        (
            "Is device type related to purchased yes/no? Use:",
            ("chi-square test of independence", "t-test", "linear regression", "correlation"),
            0,
        ),
        (
            "Chi-square tests work on:",
            ("counts in categories", "means", "medians", "continuous pairs"),
            0,
        ),
    ],
    "correlation": [
        (
            "r = -0.9 means:",
            (
                "a strong negative linear relation",
                "no relation",
                "a weak positive relation",
                "causation",
            ),
            0,
        ),
        ("Correlation r always lies between:", ("-1 and 1", "0 and 1", "0 and 100", "-∞ and ∞"), 0),
    ],
    "corr_causation": [
        (
            "Ice-cream sales and drownings rise together because of:",
            (
                "a confounder (summer heat)",
                "ice-cream causing drowning",
                "chance only",
                "reverse causation",
            ),
            0,
        ),
        (
            "To show causation you ideally need:",
            ("a randomised experiment", "a high r", "a big sample only", "a scatter plot"),
            0,
        ),
    ],
    "linear_regression": [
        ("y = 3 + 2x. When x = 5, y is:", ("13", "10", "16", "25"), 0),
        (
            "The slope 2 in y = 3 + 2x means:",
            ("y rises 2 per unit of x", "y starts at 2", "x rises 2 per unit of y", "r = 2"),
            0,
        ),
    ],
    "r_squared": [
        (
            "R² = 0.64 means the model explains:",
            ("64% of the variance in y", "64% of the data points", "r = 0.64", "a 64% error"),
            0,
        ),
        (
            "Adding more predictors to a regression makes R²:",
            ("never decrease", "always decrease", "become 1", "become negative"),
            0,
        ),
    ],
    "ab_testing": [
        (
            "In an A/B test users must be assigned to variants:",
            ("at random", "by signup date", "by country", "by who clicks first"),
            0,
        ),
        (
            "Stopping the test as soon as p < 0.05 ('peeking') inflates:",
            ("the false-positive rate", "the sample size", "power", "the effect size"),
            0,
        ),
    ],
    "stat_power": [
        (
            "Power is the probability of:",
            ("detecting a real effect", "a false positive", "the null being true", "a big p-value"),
            0,
        ),
        (
            "To detect a smaller effect with the same power you need:",
            ("a larger sample", "a smaller sample", "a higher p-value", "fewer variants"),
            0,
        ),
    ],
}

TASK: dict[str, tuple[str, str]] = {
    "descriptive": ("What is the median of 3, 9, 1, 7, 5?", "5"),
    "probability_basics": (
        "A fair die: what is P(rolling a 6)? Give a decimal to 3 places.",
        "0.167",
    ),
    "linear_regression": ("y = 10 - 0.5x. What is y when x = 8?", "6"),
    "quartiles": ("Q1 = 12 and Q3 = 30. What is the IQR?", "18"),
}
