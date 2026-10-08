"""
Checks for the two "prediction" features: trend forecasts on an uploaded CSV
(forecast.py + csv_tools.py) and savings-goal questions (savings_goal.py).
Run:  python test_predictions.py   (or pytest).  No model, no network.
"""

import io
import math
import random
import sys
from types import SimpleNamespace

import csv_tools
import savings_goal
from documents import DocumentStore
from forecast import fit_line
from tools import compound_interest_calculator


def monthly_csv(n=12, start_year=2024, slope=4000, base=100000, noise=0, seed=1, name="Revenue (AED)"):
    rnd = random.Random(seed)
    rows = [f"Month,{name},Orders"]
    for k in range(n):
        year, month = start_year + k // 12, k % 12 + 1
        rows.append(f"{year}-{month:02d}-01,{base + k * slope + rnd.randint(-noise, noise) if noise else base + k * slope},{50 + k}")
    return "\n".join(rows) + "\n"


def ask(query, csv_text, filename="monthly.csv"):
    store = DocumentStore()
    store.add_upload(filename, csv_text.encode())
    return csv_tools.try_answer(store, query)


# ------------------------------------------------------------------------------ the line fit

def test_fit_line_recovers_a_known_trend():
    fit = fit_line([0, 1, 2, 3, 4, 5], [10, 12, 14, 16, 18, 20])
    assert abs(fit.slope - 2) < 1e-9 and abs(fit.intercept - 10) < 1e-9 and abs(fit.r2 - 1) < 1e-9
    yhat, lo, hi = fit.predict(6)
    assert abs(yhat - 22) < 1e-9 and lo == hi        # a perfect line has no spread


def test_prediction_range_widens_with_noise_and_distance():
    noisy = fit_line(list(range(12)), [100 + 4 * i + (7 if i % 2 else -7) for i in range(12)])
    _, lo1, hi1 = noisy.predict(12)
    _, lo2, hi2 = noisy.predict(24)
    assert hi1 - lo1 > 0 and (hi2 - lo2) > (hi1 - lo1)


def test_fit_line_needs_three_points():
    for xs, ys in [([1, 2], [1, 2]), ([1, 1, 1], [1, 2, 3])]:
        try:
            fit_line(xs, ys)
        except ValueError:
            pass
        else:
            raise AssertionError("bad input accepted")


# ------------------------------------------------------------------------------ CSV forecasts

def test_forecast_continues_a_clean_trend():
    r = ask("forecast revenue for the next 3 months", monthly_csv())
    assert r.chart is not None and r.chart["chart_type"] == "line"
    labels = r.chart["labels"]
    assert labels[0] == "Jan 2024" and labels[-3:] == ["Jan 2025", "Feb 2025", "Mar 2025"]
    actual, forecast, low, high = (d["values"] for d in r.chart["datasets"])
    assert actual[-4:] == [None, None, None, None][:0] + actual[-4:]           # shape check below
    assert actual[-3:] == [None, None, None] and actual[11] == 100000 + 11 * 4000
    assert forecast[11] == actual[11]                                          # the forecast line starts where the data ends
    assert [round(v) for v in forecast[-3:]] == [100000 + 12 * 4000, 100000 + 13 * 4000, 100000 + 14 * 4000]
    assert all(l <= f <= h for l, f, h in zip(low[-3:], forecast[-3:], high[-3:]))
    assert "next 3 months" in r.text and "not advice" in r.text and "ignores seasonality" in r.text
    assert "148,000" in r.text or "Jan 2025: 148,000" in r.text


def test_forecast_horizon_words():
    csv_text = monthly_csv(24)
    assert len(ask("forecast revenue for the next 6 months", csv_text).chart["labels"]) == 24 + 6
    assert len(ask("predict revenue next year", csv_text).chart["labels"]) == 24 + 12
    assert len(ask("what will revenue be next quarter?", csv_text).chart["labels"]) == 24 + 3
    default = ask("forecast revenue", csv_text)
    assert len(default.chart["labels"]) == 24 + 6


def test_forecast_never_goes_negative_for_a_positive_series():
    falling = monthly_csv(12, slope=-9000, base=100000)
    r = ask("forecast revenue for the next 12 months", falling)
    assert all(v is None or v >= 0 for d in r.chart["datasets"] for v in d["values"])
    assert "trend down" in r.text


def test_forecast_needs_enough_history_and_a_clear_column():
    short = ask("forecast revenue", monthly_csv(4))
    assert "at least 6 periods" in short.text and short.chart is None
    two = ask("forecast next month", monthly_csv(12))
    assert two is not None and "Which column" in two.text                      # Revenue and Orders: it won't guess


def test_forecast_uses_the_averaged_series_for_rates_and_handles_gaps_and_rows():
    prices = "Month,Unit price,Units\n" + "\n".join(f"2024-{m:02d}-01,{10 + m},{m}" for m in range(1, 9)) + "\n"
    r = ask("forecast unit price for the next 2 months", prices)
    assert "(average)" in r.text
    gap = "Month,Sales\n" + "\n".join(f"2024-{m:02d}-01,{100 + 5 * m}" for m in (1, 2, 3, 4, 6, 7, 8, 9)) + "\n"
    g = ask("forecast sales for the next 3 months", gap)
    assert g.chart["datasets"][0]["values"].count(None) >= 4                     # May stays empty, plus the 3 future months
    no_dates = "Day,Sales\n" + "\n".join(f"d{i},{100 + 3 * i}" for i in range(10)) + "\n"
    n = ask("predict sales for the next 3 rows", no_dates)
    assert n.chart["labels"][-3:] == ["Next 1", "Next 2", "Next 3"]


def test_quarterly_and_daily_data_are_detected():
    quarters = "Date,Revenue\n" + "\n".join(f"{2023 + q // 4}-{(q % 4) * 3 + 1:02d}-15,{1000 + 50 * q}" for q in range(8)) + "\n"
    r = ask("forecast revenue for the next 2 quarters", quarters)
    assert r.chart["labels"][-2:] == ["Q1 2025", "Q2 2025"]
    days = "Date,Visits\n" + "\n".join(f"2025-03-{d:02d},{200 + 4 * d}" for d in range(1, 21)) + "\n"
    d = ask("forecast visits for the next 5 days", days)
    assert d.chart["labels"][-1] == "25 Mar 2025"


def test_a_weak_trend_is_flagged():
    zigzag = [100, 92, 108, 95, 104, 99, 101, 93, 107, 96, 103, 100]
    assert fit_line(list(range(12)), zigzag).r2 < 0.2
    flat = "Month,Sales\n" + "\n".join(f"2024-{m:02d}-01,{v}" for m, v in enumerate(zigzag, start=1)) + "\n"
    r = ask("forecast sales", flat)
    assert "trend is weak" in r.text


def test_forecasts_only_when_asked():
    assert "Forecast" not in ask("what is the total revenue?", monthly_csv()).text
    assert ask("who is the ruler of dubai?", monthly_csv()) is None


# ------------------------------------------------------------------------------ savings goals

def simulate_months(target, principal, monthly, rate):
    balance, i = principal, rate / 100 / 12
    for m in range(1, 1201):
        balance = (balance + monthly) * (1 + i)
        if balance >= target:
            return m
    return None


def test_how_long_matches_an_independent_simulation():
    r = savings_goal.try_answer("when will I reach AED 500,000 saving 1,500 a month at 5% a year?")
    months = simulate_months(500000, 0, 1500, 5)
    assert f"({months} months)" in r.text and "AED 500,000" in r.text
    assert r.chart is not None and r.chart["datasets"][1]["label"] == "Goal"
    assert r.chart["datasets"][0]["values"][-1] >= 500000 > r.chart["datasets"][0]["values"][-2]


def test_how_long_phrasings_and_units():
    cases = [
        ("how long to save 1 million if i invest 2000 monthly at 7%", (1_000_000, 0, 2000, 7)),
        ("starting with 20,000, how long until i have 250000 saving 1000 a month at 4%?", (250000, 20000, 1000, 4)),
        ("when can I hit 2.5 million putting away 5k per month at 6.5 percent", (2_500_000, 0, 5000, 6.5)),
    ]
    for text, (target, principal, monthly, rate) in cases:
        r = savings_goal.try_answer(text)
        assert f"({simulate_months(target, principal, monthly, rate)} months)" in r.text, text


def test_monthly_amount_needed_reaches_the_goal():
    r = savings_goal.try_answer("how much do I need to save each month to reach 300k in 10 years at 6%?")
    import re
    amount = int(re.search(r"about AED ([\d,]+) a month", r.text).group(1).replace(",", ""))
    plan = compound_interest_calculator(0, amount, 6, 10)
    assert plan["ending_balance"] >= 300000 > compound_interest_calculator(0, amount - 5, 6, 10)["ending_balance"]
    zero = savings_goal.try_answer("how much should I save monthly to reach 12000 in 1 year at 0%?")
    assert "about AED 1,000 a month" in zero.text


def test_it_asks_for_what_is_missing_instead_of_guessing():
    a = savings_goal.try_answer("when will I reach 100000 saving 500 a month")
    assert "annual return" in a.text and a.chart is None
    b = savings_goal.try_answer("how much do i need to save each month to reach 300k at 6%?")
    assert "how many years" in b.text
    c = savings_goal.try_answer("how long will it take to save 50000 at 5%?")
    assert "how much you save each month" in c.text


def test_goal_edge_cases():
    assert "already have" in savings_goal.try_answer("starting with 600000, when will i reach 500000 saving 1000 a month at 5%?").text
    never = savings_goal.try_answer("when will i reach 1000000 saving 1 a month at 0%?")
    assert "within 100 years" in never.text
    assert "don't look right" in savings_goal.try_answer("when will i reach 100000 saving 500 a month at 250%?").text


def test_non_goal_messages_are_left_alone():
    for q in ["what is compound interest?", "how much can my landlord raise my rent in dubai?", "how long does it take to save for a house?",
              "when is the vat deadline?", "how much is the vat registration threshold?", "how long is the notice period for resigning?",
              "what is the total revenue?", "how many banks are there in the uae?"]:
        assert savings_goal.try_answer(q) is None, q


# ------------------------------------------------------------------------------ official forecasts and declined predictions

def _in_2026(fn):
    """Run a test as if it were 2026 (the forecasts and 'next year' depend on today's date)."""
    def wrapper():
        import predictions
        original = predictions._current_year
        predictions._current_year = lambda: 2026
        try:
            fn()
        finally:
            predictions._current_year = original
    wrapper.__name__ = fn.__name__
    return wrapper


@_in_2026
def test_official_forecasts_are_looked_up_not_guessed():
    import predictions as p
    a = p.try_answer("what will inflation be in 2027?").text
    assert "1.9% for 2027" in a and "Central Bank" in a and "forecasts, not results" in a and "25.7" not in a
    both = p.try_answer("what is the gdp growth forecast for 2026 and 2027?").text
    assert "1.7% for 2026" in both and "9.8% for 2027" in both
    assert "4.5% for 2027" in p.try_answer("forecast non-oil gdp growth for 2027").text
    assert "25.7% for 2027" in p.try_answer("what will hydrocarbon gdp growth be in 2027").text
    assert "IMF projects" in p.try_answer("what will uae government debt be in 2026?").text
    assert "1.9% for 2027" in p.try_answer("what will the inflation rate be next year?").text
    assert "2.3% for 2026" in p.try_answer("what is the inflation forecast?").text and "1.9% for 2027" in p.try_answer("inflation forecast").text


@_in_2026
def test_no_forecast_is_invented_beyond_what_is_held():
    import predictions as p
    far = p.try_answer("what will inflation be in 2030?").text
    assert "don't have an official forecast" in far and "2.3% for 2026 and 1.9% for 2027" in far
    debt = p.try_answer("what will the government debt to gdp ratio be in 2028?").text
    assert "don't have an official forecast" in debt and "31.4% for 2026" in debt


@_in_2026
def test_things_we_dont_predict_get_a_polite_no_and_a_real_fact():
    import predictions as p
    rates = p.try_answer("what will the uae base rate be in 2027?").text
    assert "don't make my own forecasts of interest rates" in rates and "3.9%" in rates and "4.3" not in rates
    assert "3.6725" in p.try_answer("will the dirham lose its peg to the dollar next year?").text
    assert "AED 252 billion" in p.try_answer("will dubai property prices fall next year?").text
    assert "6.6%" in p.try_answer("will the dfm index go up next year?").text
    crypto = p.try_answer("predict the bitcoin price at the end of next year").text
    assert "cryptocurrency prices" in crypto and "What I can tell you" not in crypto
    assert "commodity prices" in p.try_answer("what will the gold price be next year?").text


@_in_2026
def test_wordings_the_model_got_wrong_are_caught():
    import predictions as p
    assert "property prices" in p.try_answer("how high will dubai villa values go by 2030?").text
    salaries = p.try_answer("should i expect higher salaries in the uae next year?").text
    assert "salaries and wages" in salaries and "11.7%" in salaries and "0.7%" in salaries
    economy = p.try_answer("how will the economy do over the next few years?").text
    assert "1.7% for 2026" in economy and "9.8% for 2027" in economy
    mortgage = p.try_answer("is now a good time to lock in a fixed rate mortgage before rates move?").text
    assert "interest rates" in mortgage and "3.9%" in mortgage and "expected to rise" not in mortgage
    assert p.try_answer("which uae company will have the best returns?") is None      # advice, not a forecast: the model declines it


@_in_2026
def test_ordinary_questions_are_not_treated_as_predictions():
    import predictions as p
    for q in ["what was inflation in 2025?", "what is the inflation rate?", "will inflation affect my savings?", "what is the base rate?",
              "how much can my landlord raise my rent in dubai?", "what is the vat registration threshold?", "how did the economy grow in 2025?",
              "what is the notice period for resigning?", "is the dirham pegged to the dollar?", "what is eibor?"]:
        assert p.try_answer(q) is None, q


def test_every_number_we_quote_is_in_the_knowledge_base():
    import re
    import predictions as p
    from knowledge_loader import load_knowledge_base
    text = " ".join(e["answer"] for e in load_knowledge_base() if e["topic"].startswith("UAE Statistics"))
    for key, forecast in p.OFFICIAL_FORECASTS.items():
        for year, value in forecast["values"].items():
            assert re.search(r"(?<![\d.])" + re.escape(f"{value:g}" if value != int(value) else f"{value:.1f}") + r"(?!\d)", text), (key, year, value)
    for _topic, _pattern, fact in p.DECLINED_TOPICS:
        for number in re.findall(r"\d[\d,]*(?:\.\d+)?", fact):
            if number in ("2026", "17", "24"):        # dates in the sentence
                continue
            assert number in text, f"{number!r} in {fact[:50]!r} is not in the knowledge base"


# ------------------------------------------------------------------------------ through the web endpoint

def test_endpoint_answers_both_without_calling_the_model():
    import app as web
    web.SESSIONS.clear()
    web.DOCS.clear()
    calls = []
    bot = SimpleNamespace(history=[], documents=None, doc_budget=1000, last_chart=None, last_payment_button=None,
                          last_invoice_button=None, last_quote_button=None, last_schedule_payments_button=None,
                          last_chase_payment_button=None, last_refund_button=None, last_talk_to_team_button=None,
                          last_set_reminder_button=None, last_register_business_button=None,
                          reset=lambda: None, ask=lambda q: calls.append(q) or "from the model")
    web.SESSIONS["s"] = bot
    client = web.app.test_client()
    r = client.post("/api/chat", json={"session_id": "s", "message": "when will I reach 500,000 saving 1,500 a month at 5%?"})
    assert r.status_code == 200 and "209 months" in r.json["answer"] and r.json["chart"]["chart_type"] == "line" and not calls
    client.post("/api/upload", data={"session_id": "s", "file": (io.BytesIO(monthly_csv().encode()), "monthly.csv")}, content_type="multipart/form-data")
    f = client.post("/api/chat", json={"session_id": "s", "message": "forecast revenue for the next 3 months"})
    assert f.status_code == 200 and f.json["chart"]["datasets"][1]["style"] == "forecast" and not calls
    assert client.post("/api/chat", json={"session_id": "s", "message": "who is the ruler of dubai?"}).json["answer"] == "from the model"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001 - report every failure, keep going
                failures += 1
                print("FAIL", name, "-", type(exc).__name__, exc)
    sys.exit(1 if failures else 0)
