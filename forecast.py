"""
A deliberately simple forecast: a straight-line trend fitted by least squares, with a
prediction range around it.

This is the honest kind of "prediction" for a small data file -- it says what the recent
trend implies if it simply continues, and how uncertain that is. It knows nothing about
seasonality, one-off events, or anything outside the numbers it is given, and the code that
uses it says so in the answer.
"""

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass
class LineFit:
    slope: float
    intercept: float
    r2: float
    resid_sd: float
    n: int
    xbar: float
    sxx: float

    def predict(self, x: float, level: float = 0.8) -> Tuple[float, float, float]:
        """(central estimate, low, high) at x; the range is a `level` prediction interval."""
        yhat = self.intercept + self.slope * x
        if self.n <= 2 or self.sxx == 0:
            return yhat, yhat, yhat
        se = self.resid_sd * math.sqrt(1 + 1 / self.n + (x - self.xbar) ** 2 / self.sxx)
        margin = t_critical(self.n - 2, level) * se
        return yhat, yhat - margin, yhat + margin


def t_critical(df: int, level: float) -> float:
    """Two-sided Student-t multiplier for a `level` interval (falls back to the normal
    value if scipy isn't available)."""
    try:
        from scipy.stats import t
        return float(t.ppf(0.5 + level / 2, max(df, 1)))
    except Exception:  # pragma: no cover - scipy comes with scikit-learn
        return {0.8: 1.2816, 0.9: 1.6449, 0.95: 1.96}.get(round(level, 2), 1.2816)


def fit_line(xs: Sequence[float], ys: Sequence[float]) -> LineFit:
    n = len(xs)
    if n < 3 or n != len(ys):
        raise ValueError("need at least 3 points")
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("all x values are the same")
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sxx
    intercept = ybar - slope * xbar
    sse = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    sst = sum((y - ybar) ** 2 for y in ys)
    r2 = 1 - sse / sst if sst > 0 else 1.0
    resid_sd = math.sqrt(sse / (n - 2))
    return LineFit(slope, intercept, r2, resid_sd, n, xbar, sxx)
