"""
Checks for live_rates.py. Run:  python test_live_rates.py   (or pytest)

Mocks requests.get with a captured sample of the CBUAE page's actual HTML
shape (see live_rates.py's module docstring) so these never hit the real
network -- the live end-to-end fetch/parse was already verified manually
against the real Central Bank page.
"""

from unittest.mock import patch

import live_rates
from live_rates import get_exchange_rate

# A trimmed sample in the CBUAE page's real shape: 3 <td> per row (an empty
# icon cell, the currency name, then the value in a "...value" class), plus
# the "Last updated" line -- matching what the real page actually returns.
_SAMPLE_HTML = """
<p class="font-r text-navy-custom fs-6">
    Last updated:

Friday 25 September 2026 06:05:15 PM                </p>
<table>
<tbody>
<tr><td class="font-r fs-small text-navy-custom"></td><td class="font-r fs-small text-navy-custom">US Dollar</td><td class="font-r fs-small text-navy-custom value">3.6725</td></tr>
<tr><td class="font-r fs-small text-navy-custom"></td><td class="font-r fs-small text-navy-custom">GB Pound</td><td class="font-r fs-small text-navy-custom value">4.866062</td></tr>
<tr><td class="font-r fs-small text-navy-custom"></td><td class="font-r fs-small text-navy-custom">Indian Rupee</td><td class="font-r fs-small text-navy-custom value">0.038328</td></tr>
</tbody>
</table>
"""


def _reset_cache():
    live_rates._cache = {"rates": None, "last_updated": None, "fetched_at": 0.0}


def _mock_response(text=_SAMPLE_HTML, raise_on_get=None):
    mock_get = patch("live_rates.requests.get")
    m = mock_get.start()
    if raise_on_get:
        m.side_effect = raise_on_get
    else:
        m.return_value.text = text
        m.return_value.raise_for_status.return_value = None
    return mock_get, m


def test_parses_currency_rows_and_last_updated():
    _reset_cache()
    mock_get, m = _mock_response()
    try:
        live_rates._fetch()
    finally:
        mock_get.stop()
    assert live_rates._cache["rates"]["us dollar"] == 3.6725
    assert live_rates._cache["rates"]["gb pound"] == 4.866062
    assert live_rates._cache["last_updated"] == "Friday 25 September 2026 06:05:15 PM"


def test_get_exchange_rate_resolves_common_aliases():
    _reset_cache()
    mock_get, m = _mock_response()
    try:
        usd = get_exchange_rate("USD")
        gbp = get_exchange_rate("gbp")
        inr = get_exchange_rate("Indian Rupees")
    finally:
        mock_get.stop()
    assert usd["aed_per_unit"] == 3.6725
    assert gbp["currency"] == "British Pound"  # the display-name cleanup, not raw "Gb Pound"
    assert inr["aed_per_unit"] == 0.038328
    assert all(r["source"] == "Central Bank of the UAE" for r in (usd, gbp, inr))
    assert all(r["last_updated"] for r in (usd, gbp, inr))


def test_get_exchange_rate_unknown_currency_returns_error():
    _reset_cache()
    mock_get, m = _mock_response()
    try:
        result = get_exchange_rate("dogecoin")
    finally:
        mock_get.stop()
    assert "error" in result


def test_cache_is_reused_within_ttl():
    _reset_cache()
    mock_get, m = _mock_response()
    try:
        get_exchange_rate("USD")
        get_exchange_rate("USD")
        get_exchange_rate("GBP")
    finally:
        mock_get.stop()
    assert m.call_count == 1, f"expected one fetch for three in-TTL lookups, got {m.call_count}"


def test_expired_cache_triggers_a_refetch():
    _reset_cache()
    mock_get, m = _mock_response()
    try:
        get_exchange_rate("USD")
        live_rates._cache["fetched_at"] -= live_rates.CACHE_TTL_SECONDS + 1
        get_exchange_rate("USD")
    finally:
        mock_get.stop()
    assert m.call_count == 2, f"expected a refetch after TTL expiry, got {m.call_count} calls"


def test_network_failure_returns_a_clean_error_not_an_exception():
    _reset_cache()
    mock_get, m = _mock_response(raise_on_get=ConnectionError("no route to host"))
    try:
        result = get_exchange_rate("USD")
    finally:
        mock_get.stop()
    assert "error" in result


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except AssertionError as exc:
                failures += 1
                print("FAIL", name, "-", exc)
    raise SystemExit(1 if failures else 0)
