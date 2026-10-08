"""
Live UAE Dirham exchange rates, fetched directly from the Central Bank of
the UAE's own published rate table (not a third-party aggregator or search
snippet) -- see the Central Bank exchange rates page. Cached in memory so
repeated questions in a session don't refetch: the CBUAE only republishes
once per UAE business day, around 6pm local time.

Used as a tool (see tools.py) so all three chatbot backends get this for
free through the shared TOOLS/call_tool mechanism.
"""

import re
import time
from typing import Dict

import requests

CBUAE_URL = "https://centralbank.ae/umbraco/Surface/Exchange/GetExchangeRateAllCurrency?lang=en"
CACHE_TTL_SECONDS = 60 * 60  # CBUAE itself only updates once a day -- no need to refetch more often

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UAEFinanceProBot/1.0)"}

_ROW_RE = re.compile(
    r'<td class="font-r fs-small text-navy-custom">\s*([^<]+?)\s*</td>\s*'
    r'<td class="font-r fs-small text-navy-custom value">\s*([\d.]+)\s*</td>',
    re.S,
)
_UPDATED_RE = re.compile(r"Last updated:\s*([^<]+?)\s*</p>", re.S)

# Common codes/aliases users type instead of the CBUAE's official currency name
# (cross-checked against the actual names the CBUAE publishes -- a few of these
# are non-obvious, e.g. "philippine piso" not "peso", "hongkong dollar" as one word).
_ALIASES = {
    "usd": "us dollar", "dollar": "us dollar", "dollars": "us dollar", "us dollars": "us dollar",
    "eur": "euro", "euros": "euro",
    "gbp": "gb pound", "pound": "gb pound", "pounds": "gb pound", "sterling": "gb pound", "british pound": "gb pound",
    "inr": "indian rupee", "rupee": "indian rupee", "rupees": "indian rupee", "indian rupees": "indian rupee",
    "pkr": "pakistan rupee", "pakistani rupee": "pakistan rupee",
    "php": "philippine piso", "peso": "philippine piso", "pesos": "philippine piso", "philippine peso": "philippine piso",
    "cny": "chinese yuan", "yuan": "chinese yuan", "rmb": "chinese yuan",
    "jpy": "japanese yen", "yen": "japanese yen",
    "chf": "swiss franc", "franc": "swiss franc",
    "cad": "canadian dollar",
    "aud": "australian dollar",
    "nzd": "newzealand dollar", "new zealand dollar": "newzealand dollar",
    "hkd": "hongkong dollar", "hong kong dollar": "hongkong dollar",
    "sar": "saudi riyal", "riyal": "saudi riyal",
    "qar": "qatari riyal",
    "omr": "omani rial", "rial": "omani rial",
    "kwd": "kuwaiti dinar",
    "try": "turkish lira", "lira": "turkish lira",
    "egp": "egypt pound", "egyptian pound": "egypt pound",
    "bdt": "bangladesh taka", "taka": "bangladesh taka",
    "npr": "nepalese rupee", "nepali rupee": "nepalese rupee",
    "lkr": "sri lanka rupee", "sri lankan rupee": "sri lanka rupee",
    "rub": "russia rouble", "russian rouble": "russia rouble", "ruble": "russia rouble",
}

# A few of the CBUAE's own names read awkwardly title-cased verbatim
# (e.g. "Gb Pound") -- clean those up for display; everything else is fine
# as name.title().
_DISPLAY_NAMES = {
    "gb pound": "British Pound",
    "hongkong dollar": "Hong Kong Dollar",
    "newzealand dollar": "New Zealand Dollar",
    "egypt pound": "Egyptian Pound",
    "philippine piso": "Philippine Peso",
    "russia rouble": "Russian Rouble",
    "chinese yuan - offshore": "Chinese Yuan (Offshore)",
}

_cache: Dict = {"rates": None, "last_updated": None, "fetched_at": 0.0}


def _fetch() -> None:
    resp = requests.get(CBUAE_URL, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    html = resp.text

    rates = {name.strip().lower(): float(value) for name, value in _ROW_RE.findall(html)}
    if not rates:
        raise ValueError("CBUAE page loaded but no currency rows were found -- the page layout may have changed.")

    updated_match = _UPDATED_RE.search(html)
    _cache["rates"] = rates
    _cache["last_updated"] = updated_match.group(1).strip() if updated_match else "unknown"
    _cache["fetched_at"] = time.time()


def _ensure_fresh() -> None:
    if _cache["rates"] is None or (time.time() - _cache["fetched_at"]) > CACHE_TTL_SECONDS:
        _fetch()


def get_exchange_rate(currency: str) -> Dict:
    """AED value of one unit of a foreign currency, as published today by
    the Central Bank of the UAE. Tool entry point -- see tools.py."""
    try:
        _ensure_fresh()
    except Exception as exc:
        return {"error": f"Could not reach the Central Bank of the UAE's exchange rate page: {exc}"}

    rates = _cache["rates"] or {}
    key = _ALIASES.get(currency.strip().lower(), currency.strip().lower())

    if key not in rates:
        matches = [name for name in rates if key in name or name in key]
        if len(matches) == 1:
            key = matches[0]
        else:
            return {
                "error": (
                    f"'{currency}' isn't a currency name/code recognized from the Central Bank's "
                    "list. Try the full currency name (e.g. 'Indian Rupee') or a common code (e.g. 'INR')."
                )
            }

    return {
        "currency": _DISPLAY_NAMES.get(key, key.title()),
        "aed_per_unit": rates[key],
        "source": "Central Bank of the UAE",
        "last_updated": _cache["last_updated"],
    }
