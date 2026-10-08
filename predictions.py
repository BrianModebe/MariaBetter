"""
Questions about the future ("what will inflation be in 2027?", "will the dirham lose its
peg?", "predict the bitcoin price").

The small local model got these badly wrong in testing -- it once answered a 2027 inflation
question with a hydrocarbon-GDP forecast (25.7%) and invented a "4.3% base rate for 2027"
that appears nowhere in the sources -- so they are handled here, by code:

  * Official forecasts we actually hold (the Central Bank of the UAE's June 2026 review, and
    the IMF debt projection it quotes) are looked up in a small table and reported as
    forecasts, with who made them.
  * Anything else the user wants predicted -- interest rates, exchange rates, property
    prices, stocks, crypto, commodity prices -- gets a polite "I don't make my own forecasts
    of that", plus the latest real figure we do have.

Nothing here predicts anything itself. (For trend forecasts of a user's own CSV, see
csv_tools.py; for savings goals, savings_goal.py.)

Every number below also appears in knowledge/uae_statistics.json, and test_predictions.py
checks that.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional

from csv_tools import Result

CITE = "Central Bank of the UAE, Quarterly Economic Review, June 2026, data cut-off 12 May 2026"
CBUAE = "The Central Bank of the UAE"

OFFICIAL_FORECASTS: Dict[str, Dict] = {
    "inflation": {"label": "inflation", "values": {2026: 2.3, 2027: 1.9}, "who": CBUAE, "verb": "forecasts", "cite": CITE},
    "gdp": {"label": "real GDP growth", "values": {2026: 1.7, 2027: 9.8}, "who": CBUAE, "verb": "forecasts", "cite": CITE},
    "non_oil": {"label": "non-oil (non-hydrocarbon) GDP growth", "values": {2026: 1.9, 2027: 4.5}, "who": CBUAE, "verb": "forecasts", "cite": CITE},
    "oil_gas": {"label": "oil and gas (hydrocarbon) GDP growth", "values": {2026: 0.8, 2027: 25.7}, "who": CBUAE, "verb": "forecasts", "cite": CITE},
    "debt": {"label": "government gross debt as a share of GDP", "values": {2026: 31.4}, "who": "The IMF", "verb": "projects",
             "cite": "as quoted in the Central Bank of the UAE's June 2026 review"},
}

# topics the app does not forecast, and the latest real information it does have
DECLINED_TOPICS = [
    ("interest rates", re.compile(r"(?i)\b(base rate|interest rates?|eibor|mortgage( rates?)?|fixed[- ]rate|variable[- ]rate|floating[- ]rate|fed (funds )?rate|rate (hike|cut)s?)\b"),
     "The Central Bank of the UAE raised its Base Rate to 3.9% on 17 September 2026, and it follows the US Federal Reserve's policy rate. "
     "Three-month EIBOR was 4.20% on 24 September 2026."),
    ("the dirham's exchange rate", re.compile(r"(?i)\b(peg|pegged|exchange rate|dirham (vs|against|to)|aed (vs|to)|usd/?aed)\b|\b(dirham|aed)\b.*\b(dollar|usd)\b"),
     "The dirham is fixed at AED 3.6725 per US dollar, and the Central Bank of the UAE has stated that the fixed-peg policy will remain in place."),
    ("property prices", re.compile(r"(?i)\b(property|real estate|house|home|villa|apartment|housing)\b.*\b(prices?|market|values?|crash|bubble|boom)\b|\b(prices?|market)\b.*\b(property|real estate|villas?|apartments?)\b"),
     "Dubai recorded real estate transactions worth AED 252 billion in Q1 2026, up 31% in value on a year earlier, according to the Dubai Land Department."),
    ("stock markets", re.compile(r"(?i)\b(stocks?|shares|share prices?|dfm|adx|stock market|equities)\b"),
     "At the end of Q1 2026 the Dubai Financial Market index was up 6.6% and the Abu Dhabi index up 1.6% on a year earlier."),
    ("salaries and wages", re.compile(r"(?i)\b(salar(y|ies)|wages?|pay (rises?|raises?|increases?))\b"),
     "As of March 2026 the number of employees covered by the Wages Protection System was up 11.7% year on year, while the average wage rose only 0.7%."),
    ("cryptocurrency prices", re.compile(r"(?i)\b(bitcoin|btc|ethereum|crypto\w*|dogecoin|altcoins?)\b"), ""),
    ("commodity prices", re.compile(r"(?i)\b(gold price|oil price|price of (gold|oil)|brent|crude price)\b"), ""),
]

_YEAR = re.compile(r"\b(20[2-4]\d)\b")
_METRICS = [
    ("non_oil", re.compile(r"(?i)\bnon-?\s?(oil|hydrocarbons?)\b")),
    ("oil_gas", re.compile(r"(?i)\b(hydrocarbons?|oil (and|&) gas|oil gdp|oil sector)\b")),
    ("inflation", re.compile(r"(?i)\binflation\b|\bcpi\b|consumer prices?")),
    ("debt", re.compile(r"(?i)\b(government|public|national|uae|federal)\b.*\bdebt\b|\bdebt\b.*\b(to gdp|of gdp|gdp)\b")),
    ("gdp", re.compile(r"(?i)\bgdp\b|economic growth|economy (to )?grow|growth (rate )?of the (uae )?economy|\bthe (uae )?economy\b")),
]
_FORECAST_WORDS = re.compile(r"(?i)\b(forecast\w*|predict\w*|project(ed|ion|ions)|outlook|estimate[sd]?)\b")
_WILL_WORDS = re.compile(r"(?i)\b(will|would|going to|expect(ed|s)?|be in|end up|likely)\b")
_NEXT_WORDS = re.compile(
    r"(?i)\b(next (week|month|quarter|year|decade)|next (few|couple of|several|\d+) (months?|years?)|over the next|coming (months?|years?)|years? ahead|"
    r"in \d+ years?|by the end of (the )?(this |next )?year|soon|in the future|end of (this|next) year)\b"
)
_TIMING = re.compile(
    r"(?i)\b(good|right|best|wrong|bad) time to\b|\bshould i (wait|lock in|fix|buy now|sell now)\b|\bbefore (rates?|prices?|the market) (rise|rises|fall|falls|go|goes|drop|drops|move|moves|change|changes)\b"
)


def _current_year() -> int:
    return datetime.now().year


def _years_in(query: str) -> List[int]:
    years = [int(y) for y in _YEAR.findall(query)]
    if re.search(r"(?i)\bnext year\b", query):
        years.append(_current_year() + 1)
    return years


def _is_future_question(query: str) -> bool:
    if _TIMING.search(query):
        return True           # "is now a good time to lock in a rate?" asks the same thing as a prediction
    forecast_words = bool(_FORECAST_WORDS.search(query))
    will_words = bool(_WILL_WORDS.search(query))
    future = any(y >= _current_year() for y in _years_in(query)) or bool(_NEXT_WORDS.search(query))
    return forecast_words or (will_words and future)


def _fmt(value: float) -> str:
    return f"{value:g}%"


def try_answer(query: str) -> Optional[Result]:
    """An official forecast we hold, or a polite decline for something we don't predict; None otherwise."""
    if not _is_future_question(query):
        return None
    years = _years_in(query)
    past_only = years and all(y < _current_year() for y in years) and not _NEXT_WORDS.search(query)
    if past_only:
        return None

    for key, pattern in _METRICS:
        if pattern.search(query):
            return _official(key, years)

    for topic, pattern, fact in DECLINED_TOPICS:
        if pattern.search(query):
            reply = f"I don't make my own forecasts of {topic} -- nobody can call that reliably, and a made-up number would only mislead you."
            if fact:
                reply += " What I can tell you: " + fact
            return Result(reply + " For anything that affects a real decision, check the official publications or speak to a licensed adviser.")
    return None


def _official(key: str, years: List[int]) -> Result:
    forecast = OFFICIAL_FORECASTS[key]
    values = forecast["values"]
    wanted = [y for y in dict.fromkeys(years) if y >= _current_year()] or sorted(values)
    known = [y for y in wanted if y in values]
    unknown = [y for y in wanted if y not in values]
    if not known:
        held = " and ".join(f"{_fmt(v)} for {y}" for y, v in sorted(values.items()))
        return Result(
            f"I don't have an official forecast of {forecast['label']} for {', '.join(str(y) for y in unknown)}. {forecast['who']} "
            f"{forecast['verb']} {held} ({forecast['cite']}), and I don't make projections of my own beyond that."
        )
    parts = "; ".join(f"{_fmt(values[y])} for {y}" for y in known)
    text = f"{forecast['who']} {forecast['verb']} {forecast['label']} of {parts} ({forecast['cite']})."
    if unknown:
        text += f" I don't hold a forecast for {', '.join(str(y) for y in unknown)}."
    return Result(text + " These are official forecasts, not results, and they are revised as new data arrives.")
