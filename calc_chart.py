"""
Charts and summaries built directly from a compound_interest_calculator result.

The local 3B model is unreliable at turning the calculator's yearly numbers
into a render_chart call (it prints a markdown table, or charts invented
values). But once the calculator has run, everything a chart needs is already
in its result -- so for "invest X at Y% for Z years, show me a chart" the code
builds the chart and the one-paragraph summary itself, and the model only has
to get the four calculator inputs right. The numbers in both come straight
from the calculator, so they can't be mangled.

Used by local_chatbot.py.
"""

import re
from typing import Dict, Optional, Tuple

from tools import render_chart

CHART_REQUEST = re.compile(
    r"\b(charts?|charting|graphs?|graphing|plots?|plotting|visuali[sz]\w*|visuals?|diagrams?|infographics?)\b", re.I
)
# "graph it", "chart that", "visualize the growth" -- a short chart request that
# points back at the previous answer instead of naming new data.
_POINTS_BACK = re.compile(r"\b(it|that|this|them|these|those)\b|\bthe (growth|results?|numbers|balance|investment|projection|savings)\b", re.I)

_TYPE_WORDS = (
    ("stacked_bar", re.compile(r"\bstack\w*", re.I)),
    ("pie", re.compile(r"\b(pie|donut|doughnut)\b", re.I)),
    ("bar", re.compile(r"\bbars?\b", re.I)),
    ("line", re.compile(r"\b(lines?|trend)\b", re.I)),
)
_SUPPORTED = ("line", "bar", "stacked_bar", "pie")


# Names what to chart ("bar chart OF vat rates", "graph salaries BY emirate"), so
# it isn't a follow-up about the previous calculation.
_NAMES_A_SUBJECT = re.compile(r"\b(of|for|by|vs|versus|between|comparing|compare|across|per)\b", re.I)


def is_followup_chart_request(query: str) -> bool:
    """A short chart request about the previous answer: "graph it", "visualize
    the growth", or just a chart type ("now as a pie chart")."""
    if len(query) > 80 or not CHART_REQUEST.search(query):
        return False
    if _POINTS_BACK.search(query):
        return True
    return len(query) <= 50 and not _NAMES_A_SUBJECT.search(query) and any(p.search(query) for _, p in _TYPE_WORDS)


def pick_chart_type(query: str, model_type: Optional[str] = None) -> str:
    """The user's own words win; otherwise keep the model's choice if it makes
    sense for calculator output; otherwise a line (growth over time)."""
    for chart_type, pattern in _TYPE_WORDS:
        if pattern.search(query):
            return chart_type
    return model_type if model_type in _SUPPORTED else "line"


def _currency(query: str) -> str:
    if re.search(r"\$|\b(usd|dollars?)\b", query, re.I):
        return "USD"
    if re.search(r"€|\b(eur|euros?)\b", query, re.I):
        return "EUR"
    if re.search(r"£|\b(gbp|pounds?)\b", query, re.I):
        return "GBP"
    return "AED"


def build(args: Dict, result: Dict, query: str, model_type: Optional[str] = None) -> Optional[Tuple[Dict, str]]:
    """(chart, summary text) for a successful calculator run, or None when
    there's nothing to chart (an error result, or under one full year)."""
    breakdown = (result or {}).get("yearly_breakdown")
    if not breakdown:
        return None
    try:
        principal = float(args.get("principal", 0))
        monthly = float(args.get("monthly_contribution", 0))
        rate = float(args.get("annual_rate_pct", 0))
        years = float(args.get("years", 0))
    except (TypeError, ValueError):
        return None
    if not (principal or monthly):
        return None

    cur = _currency(query)
    chart_type = pick_chart_type(query, model_type)
    labels = [f"Year {row['year']}" for row in breakdown]
    balances = [row["balance"] for row in breakdown]
    contributed = [row["total_contributed"] for row in breakdown]
    growth = [round(row["balance"] - row["total_contributed"], 2) for row in breakdown]
    title = f"Projected balance over {years:g} years at {rate:g}%"

    if chart_type == "stacked_bar":
        chart = render_chart("stacked_bar", title, labels, "Total Contributed", contributed, "Investment Growth", growth)
    elif chart_type == "pie":
        chart = render_chart(
            "pie", f"Where the final {cur} {result['ending_balance']:,.0f} comes from",
            ["Total Contributed", "Investment Growth"], "Share of final balance",
            [result["total_contributed"], result["investment_growth"]],
        )
    else:
        chart = render_chart(chart_type, title, labels, "Balance", balances)
    if "error" in chart:
        return None

    put_in = " plus ".join(
        part for part in (
            f"{cur} {principal:,.0f} upfront" if principal else "",
            f"{cur} {monthly:,.0f} a month" if monthly else "",
        ) if part
    )
    text = (
        f"Putting in {put_in} at {rate:g}% a year for {years:g} years grows to about "
        f"{cur} {result['ending_balance']:,.0f}: {cur} {result['total_contributed']:,.0f} contributed plus "
        f"{cur} {result['investment_growth']:,.0f} in growth. This assumes a constant return, so treat it "
        "as an illustration, not a forecast."
    )
    return chart, text
