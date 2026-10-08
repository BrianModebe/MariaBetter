"""
Savings-goal questions, answered by code.

    "when will I reach AED 500,000 saving 1,500 a month at 5%?"          -> how long
    "how long to save 1 million investing 2000 monthly at 7%?"           -> how long
    "how much do I need to save each month to reach 300k in 10 years at 6%?" -> monthly amount
    "starting with 20,000, how long until I have 250000 saving 1000 a month at 4%?"

The maths is the same as compound_interest_calculator in tools.py (monthly compounding,
the month's contribution added before that month's growth), so the numbers agree with the
rest of the app. The model is never asked to do arithmetic: this module reads the amounts
out of the message with plain pattern matching, solves the goal, and draws the balance
against the target.

If the message is clearly a goal question but a piece is missing (say the expected return),
it asks for that piece instead of letting the model guess. If it isn't a goal question, or
has no numbers at all, it returns None and the message goes on to the normal pipeline.
"""

import math
import re
from typing import Dict, List, Optional, Tuple

from calc_chart import _currency
from csv_tools import Result
from tools import compound_interest_calculator, render_chart

MAX_MONTHS = 1200   # 100 years

_MULTIPLIER = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}
_MENTION = re.compile(r"(?i)(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|mn|million|m|billion|b)?(?![\w])")

_RATE_AFTER = re.compile(r"(?i)^\s*(%|percent|per cent|pct)")
_YEARS_AFTER = re.compile(r"(?i)^\s*(-\s*)?(years?|yrs?)\b")
_MONTHS_AFTER = re.compile(r"(?i)^\s*(-\s*)?(months?|mos?)\b")
_MONTHLY_AFTER = re.compile(r"(?i)^\s*(aed|dirhams?|dhs?|usd|dollars?|eur|gbp)?\s*(a|per|each|every|/)\s*month|^\s*(aed|dirhams?|dhs?|usd)?\s*monthly\b")
_MONTHLY_BEFORE = re.compile(r"(?i)(monthly|per month|a month|each month|every month)[\w\s,]{0,25}$")
_PRINCIPAL_BEFORE = re.compile(
    r"(?i)(starting (with|balance)|start(ing)? (with|from|at)|already (have|saved|got)|initial|current (savings|balance)|principal|lump[- ]sum|upfront|have saved|opening balance|savings of)\W*[\w\s]{0,12}$"
)
_TARGET_BEFORE = re.compile(
    r"(?i)(reach|reaching|hit|hitting|get to|goal|target|have|make|build( up)?|become|save up|accumulate|worth|total of|amount of|retire with)\W*[\w\s]{0,14}$"
)

_WHEN = re.compile(r"(?i)\b(when (will|can|could|would|do|might)|how (long|many years|many months|soon|fast|quickly)|how much time|time (it takes|to reach|needed))\b")
_HOW_MUCH = re.compile(
    r"(?i)\bhow much\b[^.?!]{0,70}\b(save|invest|put (away|aside)|contribute|deposit|set aside|need)\b|"
    r"\bhow much (do|should|would|must|will) i (need|have) to\b|\bmonthly (saving|contribution|amount|deposit)s? (needed|required)\b|"
    r"\bwhat (monthly|should i (save|invest))\b"
)
_TOPIC = re.compile(r"(?i)\b(sav\w+|invest\w*|reach|hit|goal|target|nest egg|retire\w*|million|deposit\w*|contribut\w+|build up|worth)\b")


class _Mention:
    def __init__(self, value: float, start: int, end: int, before: str, after: str):
        self.value, self.start, self.end, self.before, self.after = value, start, end, before, after
        self.role: Optional[str] = None


def _mentions(text: str) -> List[_Mention]:
    found = []
    for m in _MENTION.finditer(text):
        value = float(m.group(1).replace(",", ""))
        if m.group(2):
            value *= _MULTIPLIER[m.group(2).lower()]
        found.append(_Mention(value, m.start(), m.end(), text[max(0, m.start() - 45): m.start()], text[m.end(): m.end() + 30]))
    return found


def parse_goal(text: str) -> Dict:
    """Pull the amounts out of a message: target, monthly, principal, years, rate (any may be missing)."""
    items = _mentions(text)
    rate = years = monthly = principal = target = None
    left: List[_Mention] = []
    for item in items:
        if rate is None and _RATE_AFTER.match(item.after):
            rate, item.role = item.value, "rate"
        elif years is None and _YEARS_AFTER.match(item.after):
            years, item.role = item.value, "years"
        elif years is None and _MONTHS_AFTER.match(item.after) and not _MONTHLY_BEFORE.search(item.before):
            years, item.role = item.value / 12, "years"
        elif monthly is None and (
            _MONTHLY_AFTER.match(item.after)
            # "...each month to reach 300k": that 300k is the target, not the monthly amount
            or (_MONTHLY_BEFORE.search(item.before) and not _TARGET_BEFORE.search(item.before))
        ):
            monthly, item.role = item.value, "monthly"
        elif principal is None and _PRINCIPAL_BEFORE.search(item.before):
            principal, item.role = item.value, "principal"
        else:
            left.append(item)
    explicit = [i for i in left if _TARGET_BEFORE.search(i.before)]
    pool = explicit or left
    if pool:
        target = max(pool, key=lambda i: i.value).value
    return {"target": target, "monthly": monthly, "principal": principal or 0.0, "years": years, "rate": rate}


# ----------------------------------------------------------------------------- the maths

def months_to_goal(target: float, principal: float, monthly: float, rate_pct: float) -> Optional[int]:
    """Months until the balance reaches the target (same order of operations as
    compound_interest_calculator), or None if it never does within 100 years."""
    monthly_rate = rate_pct / 100 / 12
    balance = principal
    if balance >= target:
        return 0
    for month in range(1, MAX_MONTHS + 1):
        balance = (balance + monthly) * (1 + monthly_rate)
        if balance >= target:
            return month
    return None


def monthly_needed(target: float, principal: float, years: float, rate_pct: float) -> float:
    """The level monthly contribution that reaches the target in `years`."""
    n = round(years * 12)
    i = rate_pct / 100 / 12
    if n <= 0:
        return float("inf")
    if i == 0:
        return max((target - principal) / n, 0.0)
    growth = (1 + i) ** n
    return max((target - principal * growth) * i / ((1 + i) * (growth - 1)), 0.0)


# ----------------------------------------------------------------------------- the answer

def _plan_chart(cur: str, target: float, principal: float, monthly: float, rate: float, years_needed: float) -> Optional[Dict]:
    whole_years = max(int(math.ceil(years_needed - 1e-9)), 1)
    result = compound_interest_calculator(principal, monthly, rate, whole_years)
    rows = result["yearly_breakdown"]
    if len(rows) < 2:
        return None
    chart = render_chart(
        "line", f"Balance vs. goal ({cur} {target:,.0f})", [f"Year {r['year']}" for r in rows],
        "Balance", [r["balance"] for r in rows], "Goal", [target] * len(rows),
    )
    return None if "error" in chart else chart


def _duration(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if rest:
        parts.append(f"{rest} month{'s' if rest != 1 else ''}")
    return " and ".join(parts) or "0 months"


_CAVEAT = " This assumes a constant return with monthly compounding and no fees or taxes -- an illustration, not a forecast or advice."


def try_answer(text: str) -> Optional[Result]:
    when = bool(_WHEN.search(text))
    how_much = bool(_HOW_MUCH.search(text))
    if not (when or how_much) or not _TOPIC.search(text):
        return None
    if not _mentions(text):
        return None           # a general question ("how long does it take to save for a house?")
    p = parse_goal(text)
    cur = _currency(text)
    target, monthly, principal, years, rate = p["target"], p["monthly"], p["principal"], p["years"], p["rate"]

    if how_much and not (when and monthly is not None):
        need = []
        if target is None:
            need.append("the target amount")
        if years is None:
            need.append("how many years you have")
        if rate is None:
            need.append("the annual return to assume (use 0% for plain saving)")
        if need:
            return Result("To work out the monthly amount I need " + _join(need) + ". For example: \"how much do I need to save each month "
                          "to reach 300,000 in 10 years at 6%?\"")
        if not (0 <= rate <= 100 and 0 < years <= 100 and target > 0):
            return Result("Those numbers don't look right -- the return should be between 0% and 100% and the period at most 100 years.")
        if principal >= target:
            return Result(f"You already have {cur} {principal:,.0f}, which is at least the {cur} {target:,.0f} target.")
        need_monthly = math.ceil(monthly_needed(target, principal, years, rate))
        plan = compound_interest_calculator(principal, need_monthly, rate, years)
        text_out = (
            f"To reach {cur} {target:,.0f} in {years:g} year{'s' if years != 1 else ''} at {rate:g}% a year"
            + (f", starting with {cur} {principal:,.0f}," if principal else "")
            + f" you'd need to save about {cur} {need_monthly:,.0f} a month: {cur} {plan['total_contributed']:,.0f} contributed plus "
            f"{cur} {plan['investment_growth']:,.0f} in growth, ending at about {cur} {plan['ending_balance']:,.0f}." + _CAVEAT
        )
        return Result(text_out, _plan_chart(cur, target, principal, need_monthly, rate, years))

    need = []
    if target is None:
        need.append("the target amount")
    if monthly is None:
        need.append("how much you save each month")
    if rate is None:
        need.append("the annual return to assume (use 0% for plain saving)")
    if need:
        return Result("To work out how long it will take I need " + _join(need) + ". For example: \"when will I reach 500,000 saving 1,500 a "
                      "month at 5%?\"")
    if not (0 <= rate <= 100 and monthly >= 0 and target > 0):
        return Result("Those numbers don't look right -- the return should be between 0% and 100%.")
    months = months_to_goal(target, principal, monthly, rate)
    if months == 0:
        return Result(f"You already have {cur} {principal:,.0f}, which is at least the {cur} {target:,.0f} target.")
    if months is None:
        return Result(f"At {cur} {monthly:,.0f} a month and {rate:g}% a year you wouldn't reach {cur} {target:,.0f} within 100 years. "
                      "Try a higher monthly amount or a higher assumed return.")
    plan = compound_interest_calculator(principal, monthly, rate, months / 12)
    text_out = (
        f"Saving {cur} {monthly:,.0f} a month at {rate:g}% a year"
        + (f", starting with {cur} {principal:,.0f}," if principal else "")
        + f" you'd reach {cur} {target:,.0f} in about {_duration(months)} ({months} months). By then you'd have contributed "
        f"{cur} {plan['total_contributed']:,.0f} and earned about {cur} {plan['investment_growth']:,.0f} in growth." + _CAVEAT
    )
    return Result(text_out, _plan_chart(cur, target, principal, monthly, rate, months / 12))


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
