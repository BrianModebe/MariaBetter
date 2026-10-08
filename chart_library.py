"""
A small library of ready-made charts built from numbers that are already in the
knowledge base (tax bands and thresholds, the Dubai rent-increase cap, gratuity,
notice periods, the 50/30/20 rule).

The local 3B model is unreliable at extracting numbers from passages into a
render_chart call -- it invents values or gets stuck. For data we actually have,
the code doesn't need the model to do that: when a chart request matches one of
these, local_chatbot.py answers with the chart and a short summary directly (no
model call, so it's also instant). Anything not in this library still goes to the
model, and the model is told to decline rather than invent.

Every number here is copied from a knowledge-base answer, and the tests in
test_chart_library.py check that each chart value really appears in the entry it
cites -- add a chart, add its `kb` question.

Chart specs use render_chart's own argument names (see tools.py).
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from chart_specs_stats import STATS_CHARTS
from knowledge_loader import load_knowledge_base
from tools import render_chart

# id, the KB questions the numbers come from, words a request must contain
# (`require`: every regex in the list must match), keywords for ranking, the chart,
# and a one-to-two sentence summary. Optional `prefer`: regexes that, when all match,
# make this chart win over other candidates. Optional `exclude`: regexes that rule the
# chart out (e.g. "accounts", "fees" -- a question about what banks charge isn't a
# request for the bank-count chart).
CHARTS: List[Dict] = [
    {
        "id": "budget_50_30_20",
        "kb": ["What is the 50/30/20 rule?"],
        "require": [r"50\s*[/-]\s*30\s*[/-]\s*20|\b503020\b"],
        "keywords": "50/30/20 budget rule needs wants savings debt repayment split",
        "chart": {
            "chart_type": "pie",
            "title": "The 50/30/20 budgeting rule",
            "labels": ["Needs", "Wants", "Savings and debt repayment"],
            "series_1_label": "% of after-tax income",
            "series_1_values": [50, 30, 20],
        },
        "summary": (
            "The 50/30/20 rule splits after-tax income into 50% needs (rent, utilities, groceries), "
            "30% wants (dining out, entertainment) and 20% savings and debt repayment. It's a starting "
            "point, not a strict law."
        ),
    },
    {
        "id": "corporate_tax_bands",
        "kb": ["What is UAE corporate tax and who has to pay it?"],
        "require": [r"corporate tax|company tax|business tax", r"rates?|bands?|brackets?|income|taxable"],
        "keywords": "uae corporate tax rate rates income band bands bracket taxable income 0% 9%",
        "chart": {
            "chart_type": "bar",
            "title": "UAE corporate tax rate by taxable income",
            "labels": ["Taxable income up to AED 375,000", "Taxable income above AED 375,000"],
            "series_1_label": "Corporate tax rate (%)",
            "series_1_values": [0, 9],
        },
        "summary": "UAE corporate tax is 0% on taxable income up to AED 375,000 and 9% on taxable income above that.",
    },
    {
        "id": "vat_registration_thresholds",
        "kb": ["What is the VAT registration threshold in the UAE?"],
        "require": [r"\bvat\b|value added tax", r"thresholds?|regist\w*|limit|turnover"],
        "keywords": "vat registration threshold voluntary mandatory taxable supplies imports",
        "chart": {
            "chart_type": "bar",
            "title": "VAT registration thresholds (AED per year)",
            "labels": ["Voluntary registration from", "Mandatory registration above"],
            "series_1_label": "Taxable supplies and imports (AED)",
            "series_1_values": [187500, 375000],
        },
        "summary": (
            "VAT registration is mandatory once taxable supplies and imports exceed AED 375,000 a year; "
            "voluntary registration is allowed from AED 187,500."
        ),
    },
    {
        "id": "uae_tax_thresholds",
        "kb": [
            "What is the VAT registration threshold in the UAE?",
            "What is UAE corporate tax and who has to pay it?",
            "Are freelancers and self-employed individuals taxed in the UAE?",
            "How does UAE corporate tax treat small businesses?",
        ],
        "require": [r"thresholds?|limits?|cut-?offs?", r"tax|vat|freelanc|corporate"],
        # A request that names both VAT and corporate tax/freelancers is asking for this
        # side-by-side, not the VAT-only chart, even though the VAT chart's text is closer.
        "prefer": [r"\bvat\b", r"corporate|freelanc|small business|relief"],
        "keywords": (
            "uae tax thresholds compare vat registration voluntary mandatory corporate tax 0% band "
            "freelancer freelancers self-employed turnover small business relief"
        ),
        "chart": {
            "chart_type": "bar",
            "title": "UAE tax thresholds (AED)",
            "labels": [
                "VAT voluntary registration (supplies)",
                "VAT mandatory registration (supplies)",
                "Corporate tax 0% band (taxable income)",
                "Freelancer corporate tax applies (turnover)",
                "Small Business Relief (revenue below)",
            ],
            "series_1_label": "Threshold (AED per year)",
            "series_1_values": [187500, 375000, 375000, 1000000, 3000000],
        },
        "summary": (
            "UAE tax thresholds side by side: voluntary VAT registration from AED 187,500, mandatory VAT above "
            "AED 375,000, the 0% corporate tax band up to AED 375,000 of taxable income, freelancers entering "
            "corporate tax once turnover exceeds AED 1 million, and Small Business Relief for revenue below "
            "AED 3 million (a limited run of tax periods, with conditions)."
        ),
    },
    {
        "id": "dubai_rent_increase_cap",
        "kb": ["How much can my landlord raise my rent in Dubai?"],
        "require": [r"\brent\w*", r"increase|caps?|raise|rera|index|limit"],
        "keywords": "dubai rent increase cap rera rental index smart rental index landlord raise percent below market average",
        "chart": {
            "chart_type": "bar",
            "title": "Dubai: maximum rent increase by how far your rent is below the RERA index",
            "labels": [
                "Within 10% of the index average",
                "11-20% below",
                "21-30% below",
                "31-40% below",
                "More than 40% below",
            ],
            "series_1_label": "Maximum rent increase (%)",
            "series_1_values": [0, 5, 10, 15, 20],
        },
        "summary": (
            "Dubai's RERA rental index caps rent increases by how far your rent sits below the market average: "
            "0% within 10%, 5% if 11-20% below, 10% if 21-30% below, 15% if 31-40% below, and up to 20% if more "
            "than 40% below. Check your exact figure on the Dubai Land Department's rental index calculator."
        ),
    },
    {
        "id": "gratuity_days_per_year",
        "kb": ["How is end-of-service gratuity calculated in the UAE?"],
        "require": [r"gratuity|end.of.service"],
        "keywords": "end-of-service gratuity days basic pay per year of service first 5 years",
        "chart": {
            "chart_type": "bar",
            "title": "End-of-service gratuity: days of basic pay per year of service",
            "labels": ["Each of the first 5 years", "Each year after year 5"],
            "series_1_label": "Days of basic pay",
            "series_1_values": [21, 30],
        },
        "summary": (
            "End-of-service gratuity is 21 days' basic pay for each of the first 5 years and 30 days for each "
            "year after that. It's based on basic salary only and capped at 2 years' basic pay."
        ),
    },
    {
        "id": "notice_periods",
        "kb": [
            "What notice period applies to resign or be terminated in the UAE?",
            "What are the probation period rules in the UAE?",
        ],
        "require": [r"notice"],
        "keywords": "notice period days resign terminate probation employer employee leaving the uae standard minimum maximum",
        "chart": {
            "chart_type": "bar",
            "title": "Notice periods in the UAE (days)",
            "labels": [
                "Standard notice: legal minimum",
                "Standard notice: legal maximum",
                "Probation: employer ends it",
                "Probation: moving to another UAE employer",
                "Probation: leaving the UAE",
            ],
            "series_1_label": "Notice (days)",
            "series_1_values": [30, 90, 14, 30, 14],
        },
        "summary": (
            "Standard notice is set by the contract within a legal range of 30 to 90 days. During probation it's "
            "14 days if the employer ends it, 30 days if you're moving to another UAE employer, and 14 days if "
            "you're leaving the UAE."
        ),
    },
    {
        "id": "sector_growth_2025",
        "kb": ["Which sectors grew fastest and contribute most to the UAE's non-oil economy?"],
        "require": [r"sectors?|industr\w*", r"grow\w*|fastest|expan\w*"],
        "prefer": [r"grow\w*|fastest"],
        "keywords": "uae sectors fastest growth 2025 construction finance insurance real estate transport storage",
        "chart": {
            "chart_type": "bar",
            "title": "UAE sectors with the fastest growth in 2025 (%)",
            "labels": ["Construction", "Finance and insurance", "Real estate", "Transport and storage"],
            "series_1_label": "Growth in 2025 (%)",
            "series_1_values": [11.1, 10.4, 7.9, 7.8],
        },
        "summary": (
            "The fastest-growing UAE sectors in 2025 were construction (11.1%), finance and insurance (10.4%), "
            "real estate (7.9%) and transport and storage (7.8%)."
        ),
    },
    {
        "id": "non_oil_gdp_contribution_2025",
        "kb": ["Which sectors grew fastest and contribute most to the UAE's non-oil economy?"],
        "require": [r"sectors?|industr\w*|gdp|economy", r"contribut\w*|share|breakdown|composition|biggest|largest|by sector|make up|drives?"],
        "keywords": "uae non-oil gdp contribution by sector 2025 trade finance insurance construction manufacturing largest contributors",
        "chart": {
            "chart_type": "bar",
            "title": "Largest contributors to UAE non-oil GDP, 2025 (%)",
            "labels": ["Trade", "Finance and insurance", "Construction", "Manufacturing"],
            "series_1_label": "Share of non-oil GDP (%)",
            "series_1_values": [16.9, 13.2, 12.9, 12.8],
        },
        "summary": (
            "The four largest contributors to UAE non-oil GDP in 2025 were trade (16.9%), finance and insurance "
            "(13.2%), construction (12.9%) and manufacturing (12.8%); other sectors make up the rest."
        ),
    },
    {
        "id": "banks_by_emirate",
        "kb": ["How many banks are there in the UAE?"],
        "require": [r"banks?|banking", r"emirates?|dubai|abu dhabi|head office|each|per|by"],
        "exclude": [r"\b(accounts?|fees?|charg\w*|offer\w*|best|savings|loans?|mortgages?|rates?|interest|branch\w*|atm|islamic|foreign|national|assets|share)\b"],
        "keywords": "number of banks by emirate head office abu dhabi dubai other emirates uae banks",
        "pie_ok": True,
        "chart": {
            "chart_type": "bar",
            "title": "UAE banks by head-office emirate (Q2 2026)",
            "labels": ["Abu Dhabi", "Dubai", "Other five emirates"],
            "series_1_label": "Number of banks",
            "series_1_values": [22, 31, 9],
        },
        "summary": (
            "Of the 62 banks operating in the UAE, 31 have their head office in Dubai, 22 in Abu Dhabi and 9 in the "
            "other five emirates (Central Bank, Q2 2026). A bank's whole business is counted in the emirate of its "
            "head office."
        ),
    },
    {
        "id": "bank_assets_by_emirate",
        "kb": ["How many banks are there in the UAE?"],
        "require": [r"banks?|banking", r"assets", r"emirates?|dubai|abu dhabi|head office|each|by|share|split|distribution"],
        "exclude": [r"\b(accounts?|fees?|charg\w*|offer\w*|best|savings|islamic|conventional|foreign|national|domestic)\b"],
        "keywords": "share of banking assets by emirate head office abu dhabi dubai other emirates",
        "chart": {
            "chart_type": "pie",
            "title": "Share of UAE banking assets by head-office emirate (%)",
            "labels": ["Abu Dhabi", "Dubai", "Other five emirates"],
            "series_1_label": "Share of banking assets (%)",
            "series_1_values": [48.2, 43.7, 8.0],
        },
        "summary": (
            "Banks headquartered in Abu Dhabi hold 48.2% of UAE banking assets, those headquartered in Dubai "
            "43.7% and those in the other five emirates 8.0% (Central Bank, Q2 2026). A bank's whole business is "
            "counted in the emirate of its head office."
        ),
    },
    {
        "id": "eibor_by_tenor",
        "kb": ["What is EIBOR and what are the current EIBOR rates?"],
        "require": [r"eibor|interbank"],
        "keywords": "eibor rates by tenor overnight 1 week 1 month 3 months 6 months 1 year yield curve",
        "chart": {
            "chart_type": "line",
            "title": "EIBOR by tenor, 24 September 2026 (%)",
            "labels": ["Overnight", "1 week", "1 month", "3 months", "6 months", "1 year"],
            "series_1_label": "EIBOR (%)",
            "series_1_values": [3.70, 4.06, 4.04, 4.20, 4.43, 5.12],
        },
        "summary": (
            "On 24 September 2026 EIBOR ran from 3.70% overnight to 4.20% for 3 months and 5.12% for 1 year "
            "(Central Bank of the UAE). It is published every business day, so check the CBUAE website for "
            "today's rates."
        ),
    },
]


CHARTS.extend(STATS_CHARTS)  # population, GDP/macro, trade and banking charts (chart_specs_stats.py)


@dataclass
class ChartHit:
    chart: Dict
    text: str
    citation: str = ""  # not folded into .text by default -- see prompts.py's citation ground rule


_kb_by_question: Optional[Dict[str, Dict]] = None
_vectorizer = None
_matrix = None


def _kb_entry(question: str) -> Dict:
    global _kb_by_question
    if _kb_by_question is None:
        _kb_by_question = {e["question"]: e for e in load_knowledge_base()}
    return _kb_by_question[question]


def _citation(spec: Dict) -> str:
    """The compact trailing tag the system prompt asks for, built from the entries
    the chart's numbers come from: legal references when they have them, else the
    source, else nothing (general-knowledge entries)."""
    entries = [_kb_entry(q) for q in spec["kb"]]
    first = entries[0]
    if not first.get("source"):
        return ""
    host = urlparse(first["source"]).netloc.removeprefix("www.")
    refs = []
    for e in entries:
        if e.get("legal_ref") and e["legal_ref"] not in refs:
            refs.append(e["legal_ref"])
    label = "; ".join(refs) if refs else "Source: " + host
    tag = f"{label} -- {host}, as of {first['as_of']}" if refs else f"{label}, as of {first['as_of']}"
    return f"[{tag}]"


def _index():
    global _vectorizer, _matrix
    if _vectorizer is None:
        _vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        _matrix = _vectorizer.fit_transform([f"{c['chart']['title']} {c['keywords']}" for c in CHARTS])
    return _vectorizer, _matrix


def find_chart(query: str, min_score: float = 0.05) -> Optional[ChartHit]:
    """The best-matching ready-made chart for a chart request, or None. A chart is
    only a candidate if the request contains the words that tie it to its subject
    (`require`), so "chart the average rent in Dubai" doesn't get the rent-cap chart."""
    text = query.lower()
    candidates = [
        i for i, c in enumerate(CHARTS)
        if all(re.search(p, text) for p in c["require"]) and not any(re.search(p, text) for p in c.get("exclude", ()))
    ]
    if not candidates:
        return None
    vectorizer, matrix = _index()
    scores = cosine_similarity(vectorizer.transform([text]), matrix)[0]
    preferred = [i for i in candidates if all(re.search(p, text) for p in CHARTS[i].get("prefer", ()))
                 and CHARTS[i].get("prefer")]
    best = max(preferred or candidates, key=lambda i: scores[i])
    if scores[best] < min_score:
        return None
    spec = CHARTS[best]
    args = dict(spec["chart"])
    # The request's own chart type wins where the data allows it: a share-of-a-whole set
    # can be a bar as well as a pie, and a count that partitions a whole can be a pie.
    if args["chart_type"] == "pie" and re.search(r"\bbars?\b", text):
        args["chart_type"] = "bar"
    elif spec.get("pie_ok") and re.search(r"\b(pie|doughnut|donut)\b", text):
        args["chart_type"] = "pie"
    chart = render_chart(**args)
    if "error" in chart:
        return None
    # The citation is kept separate, not folded into .text -- the chat only shows it when
    # the user actually asks for the source (see prompts.py's citation ground rule); a
    # follow-up like "what's the source for that?" falls through to the model, which
    # re-retrieves passages widened with this turn's query and can cite from those.
    return ChartHit(chart=chart, text=spec["summary"].strip(), citation=_citation(spec))
