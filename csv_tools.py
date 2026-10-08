"""
Charts and numbers from an uploaded CSV, computed by code.

The chat calls try_answer() first for every message while a CSV is loaded. It answers
only when the message clearly refers to the file (it names a column, or says "csv",
"file", "spreadsheet", "the data" ...) AND asks for something computable:

    "chart revenue by month"            -> a chart (bar / line / pie picked from the data,
                                           or from the words "pie", "bar", "line")
    "what is the total revenue?"        -> sum / average / max / min / median / count
    "average price by region"           -> the same, broken down by a text or date column
    "top 5 clients by amount"           -> ranked list
    "forecast revenue for the next 3 months" -> a straight-line trend with a range (forecast.py)
    "how many rows are there?"          -> counts
    "describe the file"                 -> columns, types, ranges

Anything else returns None and goes to the language model, which sees a compact
description of the file (see documents.py).
"""

import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from calc_chart import CHART_REQUEST
from documents import Document, DocumentStore, Table, _norm, csv_summary
from tools import render_chart

MAX_CATEGORIES = 12
MAX_POINTS = 120
MAX_ROW_POINTS = 50


@dataclass
class Result:
    text: str
    chart: Optional[Dict] = None


# ----------------------------------------------------------------------------- wording

_CSV_WORDS = re.compile(r"(?i)\b(csv|spreadsheet|dataset|data set|the data|this data|my data|file|sheet|table|column|columns|row|rows|uploaded|attached|excel)\b")
_STOP_TOKENS = {"the", "and", "for", "total", "number", "amount", "value", "values", "name", "aed", "usd", "eur", "gbp", "with", "all", "per", "date"}
_PERIOD_NAME = re.compile(r"(?i)\b(year|yr|month|quarter|period|week|day|fy)\b")
_WANTS_PIE = re.compile(r"(?i)\b(pie|donut|doughnut)\b")
_WANTS_BAR = re.compile(r"(?i)\bbars?\b|column chart|histogram")
_WANTS_LINE = re.compile(r"(?i)\b(line|trend|over time)\b")
_WANTS_STACK = re.compile(r"(?i)\bstack\w*")
_AVERAGE = re.compile(r"(?i)\b(average|mean|avg)\b")
_TOTAL = re.compile(r"(?i)\b(total|sum|add up|altogether|overall|combined)\b")
_MAX = re.compile(r"(?i)\b(max|maximum|highest|largest|biggest|most|greatest|best|top)\b")
_MIN = re.compile(r"(?i)\b(min|minimum|lowest|smallest|least|worst|bottom|fewest)\b")
_MEDIAN = re.compile(r"(?i)\bmedian\b")
_COUNT = re.compile(r"(?i)\b(how many|number of|count)\b")
_TOPN = re.compile(r"(?i)\b(top|bottom|highest|lowest|best|worst|largest|smallest)\s+(\d{1,3})\b")
_ROWS = re.compile(r"(?i)\b(how many (rows|records|entries|lines|data points)|number of (rows|records|entries)|row count)\b")
_COLS = re.compile(r"(?i)\b(how many columns|number of columns|what columns|which columns|list (the )?columns|column names)\b")
_DESCRIBE = re.compile(r"(?i)\b(describe|summar\w*|overview|structure|preview|first (few )?rows|what'?s in|what is in|what does)\b")
_GROUP_WORDS = re.compile(r"(?i)\b(by|per|for each|in each|across|grouped|each)\b")


def _sing(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def find_columns(table: Table, query: str) -> List[int]:
    """Columns the message mentions, in the order they appear."""
    padded = f" {_norm(query)} "
    hits: Dict[int, int] = {}
    for i, name in enumerate(table.header):
        n = _norm(name)
        if not n:
            continue
        for variant in (n, n[:-1] if n.endswith("s") else n + "s"):
            pos = padded.find(f" {variant} ")
            if pos >= 0:
                hits[i] = pos
                break
    owners: Dict[str, set] = {}
    for i, name in enumerate(table.header):
        for token in _norm(name).split():
            if len(token) >= 3 and token not in _STOP_TOKENS:
                owners.setdefault(_sing(token), set()).add(i)
    for word in _norm(query).split():
        found = owners.get(_sing(word))
        if found and len(found) == 1:
            i = next(iter(found))
            hits.setdefault(i, padded.find(f" {word} "))
    return [i for i, _ in sorted(hits.items(), key=lambda kv: kv[1])]


def refers_to_csv(doc: Document, query: str) -> bool:
    stem = doc.name.lower().rsplit(".", 1)[0]
    return bool(find_columns(doc.table, query) or _CSV_WORDS.search(query) or stem in query.lower())


def fmt_number(x: float) -> str:
    if x == int(x) and abs(x) < 1e15:
        return f"{int(x):,}"
    if abs(x) >= 1000:
        return f"{x:,.2f}"
    return f"{x:,.4g}" if abs(x) < 1 else f"{x:,.2f}".rstrip("0").rstrip(".")


# ----------------------------------------------------------------------------- entry point

def try_answer(store: DocumentStore, query: str) -> Optional[Result]:
    """A computed answer for a message about an uploaded CSV, or None (let the model answer)."""
    docs = store.csvs()
    if not docs:
        return None
    scored = sorted(
        ((len(find_columns(d.table, query)), i, d) for i, d in enumerate(docs) if refers_to_csv(d, query)),
        key=lambda t: (-t[0], -t[1]),
    )
    if not scored:
        return None
    doc = scored[0][2]
    try:
        if _FORECAST.search(query):
            return forecast_answer(doc, query)
        if CHART_REQUEST.search(query):
            return chart_answer(doc, query)
        if _ROWS.search(query):
            return Result(f"{doc.name} has {len(doc.table.rows):,} rows and {len(doc.table.header)} columns.")
        if _COLS.search(query):
            t = doc.table
            return Result("Columns in " + doc.name + ": " + ", ".join(f"{n} ({t.types[i]})" for i, n in enumerate(t.header)) + ".")
        stats = stats_answer(doc, query)
        if stats:
            return stats
        if _DESCRIBE.search(query) and (_CSV_WORDS.search(query) or doc.name.lower().rsplit(".", 1)[0] in query.lower()):
            return Result(describe(doc))
    except _NeedsColumn as exc:
        return Result(str(exc))
    return None


class _NeedsColumn(Exception):
    pass


# ----------------------------------------------------------------------------- describe

def describe(doc: Document) -> str:
    t = doc.table
    lines = [csv_summary(doc).split(" Try:")[0]]
    for i in t.number_columns()[:6]:
        nums = [n for n in t.numbers(i) if n is not None]
        if nums:
            lines.append(
                f"{t.header[i]}: {len(nums):,} values, total {fmt_number(sum(nums))}, average {fmt_number(sum(nums) / len(nums))}, "
                f"from {fmt_number(min(nums))} to {fmt_number(max(nums))}."
            )
    for i, kind in enumerate(t.types):
        if kind == "date":
            dates = [d for d in t.dates(i) if d]
            if dates:
                lines.append(f"{t.header[i]}: {min(dates):%d %b %Y} to {max(dates):%d %b %Y}.")
    return " ".join(lines)


# ----------------------------------------------------------------------------- grouping

def _label_column(table: Table, index: int) -> List[Tuple[str, Optional[datetime]]]:
    """(label, sort key) for each row of a category column."""
    if table.types[index] == "date":
        out = []
        for value, when in zip(table.column(index), table.dates(index)):
            out.append((when.strftime("%Y-%m-%d") if when else value, when))
        return out
    numbers = table.numbers(index) if table.types[index] == "number" else None
    if numbers is not None:
        return [((str(int(n)) if n is not None and n == int(n) else v), None) for v, n in zip(table.column(index), numbers)]
    return [(v or "(blank)", None) for v in table.column(index)]


def _group(table: Table, x: Optional[int], ys: List[Optional[int]], mean: bool):
    """Aggregate y columns by the x column. ys may contain None for "count rows".
    Returns (labels, series list, is_date, number of source rows used)."""
    n = len(table.rows)
    labels = _label_column(table, x) if x is not None else [(f"Row {i + 1}", None) for i in range(n)]
    is_date = x is not None and table.types[x] == "date"
    columns = [[1.0] * n if y is None else table.numbers(y) for y in ys]

    order: "OrderedDict[str, List]" = OrderedDict()
    for row_index, (label, when) in enumerate(labels):
        slot = order.setdefault(label, [when, [[] for _ in ys]])
        for k, col in enumerate(columns):
            if col[row_index] is not None:
                slot[1][k].append(col[row_index])
    keys = list(order.keys())
    if is_date:
        keys.sort(key=lambda k: (order[k][0] is None, order[k][0] or datetime.min, k))
        if len(keys) > MAX_POINTS // 2:  # too many days: roll up to months
            monthly: "OrderedDict[str, List]" = OrderedDict()
            for k in keys:
                month = k[:7] if re.match(r"\d{4}-\d{2}", k) else k
                slot = monthly.setdefault(month, [order[k][0], [[] for _ in ys]])
                for j in range(len(ys)):
                    slot[1][j].extend(order[k][1][j])
            order, keys = monthly, list(monthly.keys())
    series = []
    for j, y in enumerate(ys):
        vals = []
        for k in keys:
            values = order[k][1][j]
            if not values:
                vals.append(0.0)
            elif mean and y is not None:
                vals.append(sum(values) / len(values))
            else:
                vals.append(sum(values))
        series.append(vals)
    return keys, series, is_date


# ----------------------------------------------------------------------------- charts

def chart_answer(doc: Document, query: str) -> Result:
    t = doc.table
    mentioned = find_columns(t, query)
    nums = [i for i in mentioned if t.types[i] == "number"]
    cats = [i for i in mentioned if t.types[i] != "number"]
    mean = bool(_AVERAGE.search(query))

    # "revenue by year": a number column named year/month/quarter is the axis, not a measure
    periods = [i for i in nums if _PERIOD_NAME.search(t.header[i])]
    if periods and len(nums) > 1:
        cats.insert(0, periods[0])
        nums = [i for i in nums if i != periods[0]]

    if nums:
        ys: List[Optional[int]] = nums[:2]
        x = cats[0] if cats else next((i for i in t.category_columns()), None)
    elif cats:
        ys, x = [None], cats[0]                       # count the rows in each category
    else:
        default_y = t.number_columns()
        x = next((i for i in t.category_columns() if t.types[i] == "date"), None)
        if x is None:
            x = next(iter(t.category_columns()), None)
        if default_y:
            ys = [default_y[0]]
        elif x is not None:
            ys = [None]
        else:
            raise _NeedsColumn("I couldn't find anything to chart in that file.")

    if x is None and len(t.rows) > MAX_ROW_POINTS:
        n = MAX_ROW_POINTS
    else:
        n = len(t.rows)
    src = t if n == len(t.rows) else Table(t.header, t.rows[:n], t.types, t.date_formats)
    labels, series, is_date = _group(src, x, ys, mean)

    note = ""
    if x is None and len(t.rows) > n:
        note = f" Showing the first {n} of {len(t.rows):,} rows."
    if is_date and len(labels) > MAX_POINTS:
        labels, series = labels[-MAX_POINTS:], [s[-MAX_POINTS:] for s in series]
        note += f" Showing the last {MAX_POINTS} periods."
    if not is_date and x is not None and len(labels) > MAX_CATEGORIES:
        order = sorted(range(len(labels)), key=lambda i: -series[0][i])
        keep = order[: MAX_CATEGORIES - (0 if mean else 1)]
        rest = order[len(keep):]
        labels_out = [labels[i] for i in keep]
        series_out = [[s[i] for i in keep] for s in series]
        if not mean and rest:
            labels_out.append(f"All other ({len(rest)})")
            for k, s in enumerate(series):
                series_out[k].append(sum(s[i] for i in rest))
        labels, series = labels_out, series_out
        note += f" Showing the top {len(keep)} categories" + ("" if mean else ", the rest combined") + "."

    y_names = ["Number of rows" if y is None else t.header[y] + (" (average)" if mean else "") for y in ys]
    x_name = t.header[x] if x is not None else "row"
    title = f"{y_names[0]} by {x_name}" if len(ys) == 1 else f"{y_names[0]} and {y_names[1]} by {x_name}"

    if _WANTS_PIE.search(query) and len(series) == 1 and all(v >= 0 for v in series[0]) and 1 < len(labels) <= MAX_CATEGORIES:
        chart_type = "pie"
    elif _WANTS_STACK.search(query) and len(series) == 2:
        chart_type = "stacked_bar"
    elif _WANTS_LINE.search(query) or (is_date and not _WANTS_BAR.search(query)):
        chart_type = "line"
    else:
        chart_type = "bar"
        if _WANTS_PIE.search(query):
            note += " (A pie chart needs one measure with no negative values and at most 12 slices, so this is a bar chart.)"

    args = dict(chart_type=chart_type, title=f"{title} ({doc.name})", labels=labels,
                series_1_label=y_names[0], series_1_values=series[0])
    if len(series) > 1 and chart_type != "pie":
        args.update(series_2_label=y_names[1], series_2_values=series[1])
    chart = render_chart(**args)
    if "error" in chart:
        return Result("I couldn't draw that chart: " + chart["error"])

    first = series[0]
    text = f"Here is {title[:1].lower() + title[1:]} from {doc.name}"
    if len(labels) > 1:
        hi, lo = max(range(len(first)), key=first.__getitem__), min(range(len(first)), key=first.__getitem__)
        text += f". Highest: {labels[hi]} ({fmt_number(first[hi])}); lowest: {labels[lo]} ({fmt_number(first[lo])})"
        if not mean and ys[0] is not None:
            text += f"; total {fmt_number(sum(first))}"
    text += "." + note
    return Result(text, chart)


# ----------------------------------------------------------------------------- numbers

def stats_answer(doc: Document, query: str) -> Optional[Result]:
    t = doc.table
    topn = _TOPN.search(query)
    metric = None
    if topn:
        metric = "topn"
    elif _MEDIAN.search(query):
        metric = "median"
    elif _AVERAGE.search(query):
        metric = "mean"
    elif _TOTAL.search(query):
        metric = "sum"
    elif _MAX.search(query):
        metric = "max"
    elif _MIN.search(query):
        metric = "min"
    elif _COUNT.search(query):
        metric = "count"
    if metric is None:
        return None

    mentioned = find_columns(t, query)
    nums = [i for i in mentioned if t.types[i] == "number"]
    cats = [i for i in mentioned if t.types[i] != "number"]
    if not nums and not cats and not _CSV_WORDS.search(query):
        return None
    if metric == "count" and not nums:
        if cats:
            return _counts(doc, cats[0])
        return Result(f"{doc.name} has {len(t.rows):,} rows.")
    if not nums:
        candidates = t.number_columns()
        if len(candidates) == 1:
            nums = candidates
        elif not candidates:
            raise _NeedsColumn(f"{doc.name} has no numeric columns to work out a {metric} from.")
        else:
            names = ", ".join(t.header[i] for i in candidates)
            raise _NeedsColumn(f"Which column? The numeric columns in {doc.name} are: {names}.")
    y = nums[0]
    values = t.numbers(y)
    used = [v for v in values if v is not None]
    if not used:
        raise _NeedsColumn(f"{t.header[y]} has no numbers in it.")
    label_col = cats[0] if cats else None
    grouped = label_col is not None and (_GROUP_WORDS.search(query) or metric == "topn" or metric in ("max", "min"))

    if metric == "topn" or (grouped and metric in ("max", "min")):
        return _ranking(doc, y, label_col, query, topn, metric)
    if grouped:
        return _grouped(doc, y, label_col, metric)

    name = t.header[y]
    if metric == "sum":
        answer = f"The total {name} in {doc.name} is {fmt_number(sum(used))}"
    elif metric == "mean":
        answer = f"The average {name} in {doc.name} is {fmt_number(sum(used) / len(used))}"
    elif metric == "median":
        s = sorted(used)
        mid = len(s) // 2
        answer = f"The median {name} in {doc.name} is {fmt_number(s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2)}"
    elif metric == "count":
        answer = f"{doc.name} has {len(used):,} values in {name}"
    else:
        valid = [(i, v) for i, v in enumerate(values) if v is not None]
        best, best_value = (max if metric == "max" else min)(valid, key=lambda pair: pair[1])
        row = t.rows[best]
        text_cols = [i for i, kind in enumerate(t.types) if kind == "text"]
        who = next((row[i] for i in text_cols + t.category_columns() if row[i]), f"row {best + 2}")
        answer = f"The {'highest' if metric == 'max' else 'lowest'} {name} in {doc.name} is {fmt_number(best_value)} ({who})"
    skipped = len(values) - len(used)
    return Result(answer + f" (from {len(used):,} rows" + (f"; {skipped:,} blank or non-numeric skipped" if skipped else "") + ").")


def _counts(doc: Document, col: int) -> Result:
    t = doc.table
    counts: Dict[str, int] = {}
    for label, _ in _label_column(t, col):
        counts[label] = counts.get(label, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    lines = [f"{k}: {v:,}" for k, v in ranked[:MAX_CATEGORIES]]
    more = f" (and {len(ranked) - MAX_CATEGORIES} more)" if len(ranked) > MAX_CATEGORIES else ""
    return Result(f"Rows in {doc.name} per {t.header[col]}: " + "; ".join(lines) + more + ".")


def _grouped(doc: Document, y: int, x: int, metric: str) -> Result:
    t = doc.table
    labels, series, _ = _group(t, x, [y], metric == "mean")
    pairs = sorted(zip(labels, series[0]), key=lambda kv: -kv[1])
    word = "average" if metric == "mean" else "total"
    lines = [f"{k}: {fmt_number(v)}" for k, v in pairs[:MAX_CATEGORIES]]
    more = f" (and {len(pairs) - MAX_CATEGORIES} more)" if len(pairs) > MAX_CATEGORIES else ""
    return Result(f"{word.capitalize()} {t.header[y]} by {t.header[x]} in {doc.name}: " + "; ".join(lines) + more + ".")


def _ranking(doc: Document, y: int, x: Optional[int], query: str, topn, metric: str) -> Result:
    t = doc.table
    if x is None:
        x = next(iter(t.category_columns()), None)
    n = int(topn.group(2)) if topn else 1
    lowest = bool(topn and topn.group(1).lower() in ("bottom", "lowest", "worst", "smallest")) or metric == "min" or (
        not topn and _MIN.search(query) is not None
    )
    labels, series, _ = _group(t, x, [y], False) if x is not None else ([f"Row {i + 2}" for i in range(len(t.rows))], [t.numbers(y)], False)
    pairs = [(k, v) for k, v in zip(labels, series[0]) if v is not None]
    pairs.sort(key=lambda kv: kv[1], reverse=not lowest)
    shown = pairs[: max(n, 1)]
    which = "Lowest" if lowest else "Top"
    body = "; ".join(f"{i + 1}. {k}: {fmt_number(v)}" for i, (k, v) in enumerate(shown))
    if n == 1:
        k, v = shown[0]
        return Result(f"The {'lowest' if lowest else 'highest'} {t.header[y]} is {k} with {fmt_number(v)} (totals per {t.header[x] if x is not None else 'row'} in {doc.name}).")
    return Result(f"{which} {len(shown)} by {t.header[y]} in {doc.name}: {body}.")


# ----------------------------------------------------------------------------- forecasts

_FORECAST = re.compile(
    r"(?i)\b(forecast\w*|predict\w*|extrapolat\w*|projections?|projected)\b|\bnext\s+(\d+\s+)?(days?|weeks?|months?|quarters?|years?|periods?|rows?)\b|\bwhat will\b"
)
_RATE_LIKE = re.compile(r"(?i)\b(rate|price|average|avg|margin|percent|pct|ratio|score|index|temperature)\b")
_HORIZON = re.compile(r"(?i)\bnext\s+(?:(\d+)\s+)?(day|week|month|quarter|year|period|row)s?\b")
_FREQ_WORDS = (
    ("daily", re.compile(r"(?i)\b(daily|per day|by day|each day)\b")),
    ("weekly", re.compile(r"(?i)\b(weekly|per week|by week|each week)\b")),
    ("monthly", re.compile(r"(?i)\b(monthly|per month|by month|each month)\b")),
    ("quarterly", re.compile(r"(?i)\b(quarterly|per quarter|by quarter|each quarter)\b")),
    ("yearly", re.compile(r"(?i)\b(yearly|annual\w*|per year|by year|each year)\b")),
)
_MIN_PERIODS = 6
_MAX_FIT_PERIODS = 60
_DEFAULT_HORIZON = {"daily": 14, "weekly": 8, "monthly": 6, "quarterly": 4, "yearly": 3, "rows": 5}
# how many periods of each frequency fit in one unit the user might ask for
_PERIODS_PER_UNIT = {
    "daily": {"day": 1, "week": 7, "month": 30, "quarter": 90, "year": 365},
    "weekly": {"day": 1, "week": 1, "month": 4, "quarter": 13, "year": 52},
    "monthly": {"day": 1, "week": 1, "month": 1, "quarter": 3, "year": 12},
    "quarterly": {"day": 1, "week": 1, "month": 1, "quarter": 1, "year": 4},
    "yearly": {"day": 1, "week": 1, "month": 1, "quarter": 1, "year": 1},
}


def _bucket(when: datetime, freq: str) -> int:
    """An integer index for the period `when` falls in (consecutive periods differ by 1)."""
    if freq == "daily":
        return when.toordinal()
    if freq == "weekly":
        return (when.toordinal() - 1) // 7
    if freq == "monthly":
        return when.year * 12 + when.month - 1
    if freq == "quarterly":
        return when.year * 4 + (when.month - 1) // 3
    return when.year


def _bucket_label(index: int, freq: str) -> str:
    if freq == "daily":
        return datetime.fromordinal(index).strftime("%d %b %Y")
    if freq == "weekly":
        return "Week of " + datetime.fromordinal(index * 7 + 1).strftime("%d %b %Y")
    if freq == "monthly":
        return datetime(index // 12, index % 12 + 1, 1).strftime("%b %Y")
    if freq == "quarterly":
        return f"Q{index % 4 + 1} {index // 4}"
    return str(index)


def _infer_frequency(dates: List[datetime]) -> str:
    unique = sorted({d.date() for d in dates})
    if len(unique) < 2:
        return "monthly"
    gaps = sorted((b - a).days for a, b in zip(unique, unique[1:]))
    median = gaps[len(gaps) // 2]
    if median <= 1:
        return "daily"
    if median <= 10:
        return "weekly"
    if median <= 45:
        return "monthly"
    if median <= 120:
        return "quarterly"
    return "yearly"


def _fmt_forecast(x: float) -> str:
    """Forecasts are estimates: no decimals once the number is in the hundreds."""
    return f"{x:,.0f}" if abs(x) >= 100 else fmt_number(x)


def forecast_answer(doc: Document, query: str) -> Result:
    from forecast import fit_line

    t = doc.table
    mentioned = find_columns(t, query)
    nums = [i for i in mentioned if t.types[i] == "number"]
    if not nums:
        candidates = t.number_columns()
        if len(candidates) == 1:
            nums = candidates
        elif not candidates:
            raise _NeedsColumn(f"{doc.name} has no numeric column to forecast.")
        else:
            raise _NeedsColumn("Which column should I forecast? The numeric columns in " + doc.name + " are: "
                               + ", ".join(t.header[i] for i in candidates) + ".")
    y = nums[0]
    name = t.header[y]
    date_col = next((i for i in mentioned if t.types[i] == "date"), None)
    if date_col is None:
        date_col = next((i for i, kind in enumerate(t.types) if kind == "date"), None)
    mean = bool(_AVERAGE.search(query)) or bool(_RATE_LIKE.search(name))

    values = t.numbers(y)
    if date_col is None:
        freq = "rows"
        series = OrderedDict((i, [v]) for i, v in enumerate(values) if v is not None)
        labels_for = lambda idx: f"Row {idx + 1}"
        future_label = lambda k: f"Next {k}"
    else:
        dates = t.dates(date_col)
        pairs = [(d, v) for d, v in zip(dates, values) if d is not None and v is not None]
        if len({d.date() for d, _ in pairs}) < 2:
            raise _NeedsColumn(f"I need several dates in {t.header[date_col]} to see a trend.")
        freq = next((f for f, pattern in _FREQ_WORDS if pattern.search(query)), None) or _infer_frequency([d for d, _ in pairs])
        series = OrderedDict()
        for d, v in sorted(pairs, key=lambda p: p[0]):
            series.setdefault(_bucket(d, freq), []).append(v)
        labels_for = lambda idx: _bucket_label(idx, freq)
        future_label = None

    indexes = sorted(series)
    if len(indexes) < _MIN_PERIODS:
        raise _NeedsColumn(
            f"I need at least {_MIN_PERIODS} periods of history to fit a trend, and {doc.name} only has {len(indexes)} "
            f"({'rows' if freq == 'rows' else freq + ' periods'} with {name})."
        )
    indexes = indexes[-_MAX_FIT_PERIODS:]
    ys = [sum(series[i]) / len(series[i]) if mean else sum(series[i]) for i in indexes]

    # how far ahead
    horizon = _DEFAULT_HORIZON[freq]
    match = _HORIZON.search(query)
    if match:
        count = int(match.group(1)) if match.group(1) else 1
        unit = match.group(2).lower()
        per = 1 if unit in ("period", "row") or freq == "rows" else _PERIODS_PER_UNIT[freq][unit]
        horizon = max(count * per, 1)
    horizon = min(horizon, max(len(indexes), 6), 36)

    try:
        fit = fit_line([float(i) for i in indexes], ys)
    except ValueError:
        raise _NeedsColumn("I couldn't fit a trend to that column.")
    non_negative = all(v >= 0 for v in ys)
    last = indexes[-1]
    future = []
    for k in range(1, horizon + 1):
        yhat, lo, hi = fit.predict(last + k)
        if non_negative:
            yhat, lo, hi = max(yhat, 0.0), max(lo, 0.0), max(hi, 0.0)
        future.append((k, yhat, lo, hi))

    # chart: every period in range (gaps stay empty), then the forecast periods
    span = list(range(indexes[0], last + 1)) if freq != "rows" else indexes
    hist_labels = [labels_for(i) for i in span]
    by_index = dict(zip(indexes, ys))
    actual = [by_index.get(i) for i in span]
    fut_labels = [(_bucket_label(last + k, freq) if freq != "rows" else f"Next {k}") for k, *_ in future]
    n_hist = len(span)
    pad = [None] * (n_hist - 1)
    join = ys[-1]
    chart = {
        "chart_type": "line",
        "title": f"{name}: actual and {horizon}-period forecast ({doc.name})",
        "labels": hist_labels + fut_labels,
        "datasets": [
            {"label": "Actual", "values": actual + [None] * horizon},
            {"label": "Forecast (straight-line trend)", "style": "forecast", "values": pad + [join] + [round(f[1], 2) for f in future]},
            {"label": "80% range", "style": "band", "values": pad + [join] + [round(f[2], 2) for f in future]},
            {"label": "80% range (upper edge)", "style": "band", "hide_legend": True, "values": pad + [join] + [round(f[3], 2) for f in future]},
        ],
    }

    unit_word = {"daily": "day", "weekly": "week", "monthly": "month", "quarterly": "quarter", "yearly": "year", "rows": "row"}[freq]
    shown = future[:6]
    lines = "; ".join(f"{fut_labels[k - 1]}: {_fmt_forecast(yhat)} ({_fmt_forecast(lo)} to {_fmt_forecast(hi)})" for k, yhat, lo, hi in shown)
    more = f" (and {horizon - len(shown)} more on the chart)" if horizon > len(shown) else ""
    direction = "up" if fit.slope > 0 else "down" if fit.slope < 0 else "flat"
    text = (
        f"Forecast for {name}{' (average)' if mean else ''} from {doc.name}, next {horizon} {unit_word}{'s' if horizon != 1 else ''}, with an 80% range: "
        f"{lines}{more}. "
        f"This is a straight line fitted to the last {len(indexes)} {unit_word}{'s' if len(indexes) != 1 else ''} "
        f"(trend {direction} {_fmt_forecast(abs(fit.slope))} per {unit_word}; fit R² {fit.r2:.2f})"
    )
    if fit.r2 < 0.2:
        text += ". The trend is weak, so treat the range as more meaningful than the central line"
    text += ". It ignores seasonality and one-off events -- an illustration of the trend, not advice."
    return Result(text, chart)
