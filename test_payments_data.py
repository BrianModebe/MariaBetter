"""Tests for payments_data.py -- the mock payments store behind static/app.html."""

from datetime import datetime

import payments_data as pd


def test_status_counts_sum_to_all():
    r = pd.list_payments()
    assert r["counts"]["all"] == 20
    assert sum(r["counts"][s] for s in pd.STATUSES) == r["counts"]["all"]


def test_no_timeline_timestamp_is_in_the_future():
    now = datetime.now()
    for p in pd._build_payments():
        for step in p["timeline"]:
            assert step["time"] <= now, f"{p['id']} step {step['event']!r} is in the future"


def test_timeline_is_chronological():
    for p in pd._build_payments():
        times = [step["time"] for step in p["timeline"]]
        assert times == sorted(times), f"{p['id']} timeline is out of order"


def test_status_filter_only_returns_that_status():
    r = pd.list_payments(status="failed")
    assert len(r["payments"]) == r["counts"]["failed"]
    assert all(p["status"] == "failed" for p in r["payments"])


def test_status_filter_counts_stay_stable_regardless_of_filter():
    all_counts = pd.list_payments()["counts"]
    filtered_counts = pd.list_payments(status="paid")["counts"]
    assert all_counts == filtered_counts


def test_search_matches_customer_name_case_insensitively():
    r = pd.list_payments(q="sarah")
    assert len(r["payments"]) >= 1
    assert all("sarah" in p["customer"].lower() for p in r["payments"])


def test_search_with_no_matches_returns_empty_list_not_error():
    r = pd.list_payments(q="nobody-has-this-name-xyz")
    assert r["payments"] == []


def test_get_payment_returns_full_detail_with_timeline():
    detail = pd.get_payment("PAY-0001")
    assert detail is not None
    assert detail["customer"] == "Sarah K."
    assert detail["status"] == "failed"
    assert len(detail["timeline"]) >= 1
    assert detail["timeline"][-1]["action"] == "Send resume link"


def test_get_payment_unknown_id_returns_none():
    assert pd.get_payment("PAY-9999") is None


def test_home_summary_has_no_negative_or_contradictory_values():
    h = pd.home_summary()
    assert h["collected_today"] >= 0
    assert len(h["last_7_days"]) == 7
    assert all(v >= 0 for v in h["last_7_days"])
    # collected_today > 0 must not be paired with the "nothing yet" copy
    if h["collected_today"] > 0:
        assert "Nothing yet" not in h["collected_comparison"]
    if h["chasing"] is not None:
        assert h["chasing"]["count"] > 0
        assert h["chasing"]["total"] > 0
