"""
Checks for chart_library.py / chart_specs_stats.py. Run:  python test_chart_library.py   (or pytest)

1. Every number in every ready-made chart really appears in the knowledge-base
   entries it cites -- so a typo can't put a wrong figure on a chart. (The one exception
   is a pie's "all other" slice, which is 100 minus the named slices; the test checks that
   arithmetic instead.)
2. Requests that should get a chart get the right one, and requests about data
   we don't have get none (so they fall through to the model, which declines).
"""

import re

import chart_library
from chart_library import CHARTS, find_chart, _kb_entry


def _forms(value):
    """The ways a knowledge-base answer might write a number: 375,000 / 1 million / 8.0 / 2,047.9 ..."""
    value = abs(value)  # a fall is written "fell 34.3%", the chart stores -34.3
    forms = {f"{value:g}", f"{value:.1f}", f"{value:.2f}", f"{value:,.1f}", f"{value:,.2f}"}
    if value == int(value):
        forms.add(f"{int(value):,}")
    if value >= 1_000_000:
        forms.add(f"{value / 1_000_000:g} million")
    return forms


def _in_text(value, text):
    # not part of a longer number (375,000 / 8.05), but a trailing comma or full stop is just punctuation
    return any(re.search(r"(?<![\d,.])" + re.escape(f) + r"(?!\d)(?!,\d)(?!\.\d)", text) for f in _forms(value))


def _kb_text(spec):
    return " ".join(_kb_entry(q)["answer"] for q in spec["kb"])


def test_numbers_come_from_the_knowledge_base():
    for spec in CHARTS:
        text = _kb_text(spec)
        for key in ("series_1_values", "series_2_values"):
            values = spec["chart"].get(key) or []
            for i, value in enumerate(values):
                if value == 0:
                    continue  # "0%" is stated in prose ("0% if you're within 10%"); checked below
                if spec.get("remainder") and key == "series_1_values" and i == len(values) - 1:
                    continue  # the "all other" slice is derived, see test_pie_slices
                assert _in_text(value, text), f"{spec['id']}: value {value} not found in {spec['kb']}"
    # the zero-valued points: corporate tax 0% band and Dubai's 0% cap
    assert "0% on taxable income up to AED 375,000" in _kb_entry("What is UAE corporate tax and who has to pay it?")["answer"]
    assert "0% if you're within 10%" in _kb_entry("How much can my landlord raise my rent in Dubai?")["answer"]


def test_pie_slices():
    for spec in CHARTS:
        values = spec["chart"]["series_1_values"]
        if spec.get("sums_to"):
            assert abs(sum(values) - spec["sums_to"]) < 0.11, f"{spec['id']}: slices add up to {sum(values)}"
        if spec.get("remainder"):
            assert spec.get("sums_to") == 100, f"{spec['id']}: a remainder slice needs sums_to=100"
            assert values[-1] > 0, f"{spec['id']}: the remainder slice is not positive"
        if spec["chart"]["chart_type"] == "pie":
            assert all(v >= 0 for v in values), f"{spec['id']}: negative pie slice"


def test_every_summary_number_is_in_the_kb():
    for spec in CHARTS:
        text = _kb_text(spec)
        for num in re.findall(r"\d[\d,]*(?:\.\d+)?", spec["summary"]):
            num = num.rstrip(",")
            assert num in text or f"{num} million" in text or num == "0", f"{spec['id']}: {num!r} in summary but not in the KB text"


def test_labels_and_values_line_up():
    for spec in CHARTS:
        c = spec["chart"]
        assert len(c["labels"]) == len(c["series_1_values"]), spec["id"]
        if c.get("series_2_values"):
            assert len(c["labels"]) == len(c["series_2_values"]), spec["id"]
        assert find_chart is not None


def test_ids_are_unique():
    ids = [c["id"] for c in CHARTS]
    assert len(ids) == len(set(ids))


MATCHES = [
    ("can i get a chart of uae corporate tax rates by income band?", "corporate_tax_bands"),
    ("can you draw a chart comparing the vat registration threshold with the freelancer corporate tax threshold", "uae_tax_thresholds"),
    ("graph the vat registration threshold", "vat_registration_thresholds"),
    ("chart uae tax thresholds", "uae_tax_thresholds"),
    ("pie chart of the 50/30/20 rule", "budget_50_30_20"),
    ("visualize rent increase caps", "dubai_rent_increase_cap"),
    ("chart the rera rent increase cap in dubai", "dubai_rent_increase_cap"),
    ("graph gratuity by years of service", "gratuity_days_per_year"),
    ("chart the notice period for resigning", "notice_periods"),
    ("what's the notice period range for resigning in the uae? graph it", "notice_periods"),
    ("graph the probation notice periods", "notice_periods"),
    ("chart the fastest growing sectors in the uae in 2025", "sector_growth_2025"),
    ("graph uae gdp growth by sector", "sector_growth_2025"),
    ("chart the biggest contributors to non-oil gdp", "non_oil_gdp_contribution_2025"),
    ("graph the uae economy by sector", "non_oil_gdp_contribution_2025"),
    ("chart the number of banks in each emirate", "banks_by_emirate"),
    ("pie chart of banks by emirate", "banks_by_emirate"),
    ("graph the share of banking assets by emirate", "bank_assets_by_emirate"),
    ("chart eibor rates", "eibor_by_tenor"),
    ("graph the eibor curve", "eibor_by_tenor"),
    # population: all seven emirates, plus the pies
    ("graph the population of each emirate", "population_by_emirate"),
    ("chart which emirate has the most people", "population_by_emirate"),
    ("compare the population of ajman, fujairah, ras al khaimah and umm al quwain", "population_by_emirate"),
    ("pie chart of abu dhabi population by region", "abu_dhabi_population_by_region"),
    ("chart abu dhabi's population by gender", "abu_dhabi_population_by_gender"),
    ("pie chart of men and women in fujairah", "fujairah_population_by_gender"),
    ("pie chart of emiratis vs expats in sharjah", "sharjah_population_by_nationality"),
    ("chart dubai's daytime population versus residents", "dubai_resident_vs_daytime_population"),
    # banks
    ("pie chart of islamic and conventional banks in the uae", "bank_types_islamic_conventional"),
    ("chart national vs foreign banks", "bank_ownership_national_foreign"),
    # macro
    ("chart uae gdp growth", "real_gdp_growth_2023_2027"),
    ("graph the uae economy forecast for 2026 and 2027", "real_gdp_growth_2023_2027"),
    ("chart gdp growth by sector in the first quarter of 2026", "q1_2026_sector_growth"),
    ("pie chart of oil vs non-oil share of gdp", "non_oil_share_q1_2026"),
    ("chart uae inflation", "uae_inflation_2023_2027"),
    ("graph the uae budget surplus", "fiscal_surplus"),
    ("chart uae government debt", "government_debt"),
    ("graph the uae pmi", "uae_pmi_2026"),
    ("chart the uae money supply m1 m2 m3", "money_supply_march_2026"),
    ("graph uae oil production", "oil_production_change"),
    # trade
    ("pie chart of uae foreign trade", "trade_composition_2025"),
    ("chart the uae's exports and imports", "trade_composition_2025"),
    ("pie chart of the destinations of uae exports", "export_destinations_2025"),
    ("chart what the uae exports", "export_products_2025"),
    ("pie chart of the uae's import partners", "import_partners_2025"),
    ("chart the uae's imports by product", "import_products_2025"),
]

NO_CHART = [
    "graph the average salary in each emirate",
    "can i get a chart of the banks that offer business accounts in sharjah",
    "chart the average rent in dubai",
    "chart the banks that offer business accounts in dubai",
    "chart the fees banks charge in each emirate",
    "graph the emirati population by gender",
    "graph the population growth of umm al quwain",
    "chart the unemployment rate in each emirate",
    "chart uae inflation by month",
    "chart dubai inflation by category",
    "plot gdp by emirate",
    "graph tenancy security deposits",
    "can i get a chart showing how uae share distribution works along with an explanation of it",
    "chart uae stock prices",
    "graph it",
    "chart my monthly budget",
    "graph my personal debt",
    "chart the vat and customs duty rates",
    "graph the salary of a nurse",
    "chart islamic banks' share of assets",
]


def test_requests_get_the_right_chart():
    for query, want in MATCHES:
        hit = find_chart(query)
        assert hit is not None, f"no chart for {query!r}"
        got = next(c["id"] for c in CHARTS if c["chart"]["title"] == hit.chart["title"])
        assert got == want, f"{query!r}: got {got}, wanted {want}"


def test_data_we_dont_have_gets_no_chart():
    for query in NO_CHART:
        hit = find_chart(query)
        assert hit is None, f"unexpected chart for {query!r}: {hit.chart['title']!r}"


def test_the_requested_chart_type_is_used_where_it_makes_sense():
    assert find_chart("pie chart of the number of banks in each emirate").chart["chart_type"] == "pie"
    assert find_chart("chart the number of banks in each emirate").chart["chart_type"] == "bar"
    assert find_chart("bar chart of the destinations of uae exports").chart["chart_type"] == "bar"
    assert find_chart("pie chart of the destinations of uae exports").chart["chart_type"] == "pie"
    # data that isn't a share of a whole is never turned into a pie
    assert find_chart("pie chart of the population of each emirate").chart["chart_type"] == "bar"
    assert find_chart("pie chart of uae gdp growth").chart["chart_type"] == "bar"


def test_citations_are_available_but_not_shown_by_default():
    rent = find_chart("chart the rera rent increase cap in dubai")
    assert "Decree No. 43 of 2013" not in rent.text and "dubailand.gov.ae" not in rent.text  # not shown unless asked
    assert "Decree No. 43 of 2013" in rent.citation and "dubailand.gov.ae" in rent.citation and "as of 2026-09" in rent.citation
    assert find_chart("pie chart of the 50/30/20 rule").text.endswith("not a strict law.")  # summary text unaffected
    assert find_chart("pie chart of the 50/30/20 rule").citation == ""  # general-knowledge entry: no source to cite
    imports = find_chart("pie chart of the uae's import partners")
    assert "[Source:" not in imports.text
    assert imports.citation == "[Source: centralbank.ae, as of 2026-09]"


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
