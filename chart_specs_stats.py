"""
Ready-made chart specs for the statistics in knowledge/uae_statistics.json (population,
GDP and macro indicators, trade, banking). Imported by chart_library.py, which explains
how the specs are matched to a request and how they're tested.

Spec keys beyond the basic ones (see chart_library.py):
  remainder  the LAST value is "everything else", computed here as 100 minus the others
             (so it isn't in the knowledge base; the test checks the arithmetic instead)
  sums_to    the values must add up to this (the test checks it)
  pie_ok     the same data can also be shown as a pie when the request says "pie"
"""


def _rest(*named):
    """The remaining share of a whole (in %), after the named slices."""
    return round(100 - sum(named), 1)


STATS_CHARTS = [
    # ---- population ------------------------------------------------------------------------
    {
        "id": "population_by_emirate",
        "kb": ["What is the population of each emirate?"],
        "require": [
            r"population|residents|inhabitants|people",
            r"emirates?|dubai|abu dhabi|sharjah|ajman|fujairah|ras al khaimah|umm al quwain|each|compar\w*|biggest|largest|most|smallest|least",
        ],
        "exclude": [
            r"\b(nationals?|nationalit\w*|emirati\w*|expat\w*|gender|men|women|males?|females?|age|growth|grew|density|regions?|al ain|dhafra|"
            r"daytime|day-time|commuters?|visitors?|temporar\w*|citizens?)\b"
        ],
        "keywords": "population by emirate all seven emirates dubai abu dhabi sharjah ajman ras al khaimah fujairah umm al quwain most populous people live",
        "chart": {
            "chart_type": "bar",
            "title": "Population by emirate (millions; latest official figure, years differ)",
            "labels": [
                "Dubai (end of 2025)", "Abu Dhabi (2024)", "Sharjah (2025)", "Ajman (2017)",
                "Ras Al Khaimah (approx.)", "Fujairah (mid-2025)", "Umm Al Quwain (2005)",
            ],
            "series_1_label": "Population (millions)",
            "series_1_values": [4.58, 4.14, 2.14, 0.5, 0.4, 0.33, 0.05],
        },
        "summary": (
            "Latest official population figures, in millions: Dubai 4.58 (end of 2025), Abu Dhabi 4.14 (2024), Sharjah 2.14 (2025 census), "
            "Ajman 0.5 (2017 census), Ras Al Khaimah about 0.4, Fujairah 0.33 (mid-2025) and Umm Al Quwain 0.05 (2005 census, out of date). "
            "Each emirate publishes its own count for its own year, so the bars aren't strictly comparable."
        ),
    },
    {
        "id": "abu_dhabi_population_by_region",
        "kb": ["What is the population of Abu Dhabi?"],
        "require": [r"population|residents|people", r"abu dhabi|al ain|dhafra", r"regions?|al ain|dhafra|split|breakdown|distribution|share|proportion|pie"],
        "exclude": [r"\b(gender|men|women|males?|females?)\b"],
        "keywords": "abu dhabi population by region abu dhabi region al ain al dhafra share pie",
        "sums_to": 100,
        "chart": {
            "chart_type": "pie",
            "title": "Abu Dhabi's population by region, 2024 (%)",
            "labels": ["Abu Dhabi Region", "Al Ain Region", "Al Dhafra Region"],
            "series_1_label": "% of the emirate's population",
            "series_1_values": [68, 24, 8],
        },
        "summary": (
            "About 68% of Abu Dhabi's people live in the Abu Dhabi Region, 24% in the Al Ain Region and 8% in Al Dhafra "
            "(2024, Statistics Centre - Abu Dhabi)."
        ),
    },
    {
        "id": "abu_dhabi_population_by_gender",
        "kb": ["What is the population of Abu Dhabi?"],
        "require": [r"abu dhabi", r"\b(gender|men|women|males?|females?|sex)\b"],
        "keywords": "abu dhabi population by gender men women male female share pie",
        "sums_to": 100,
        "chart": {
            "chart_type": "pie",
            "title": "Abu Dhabi's population by gender, 2024 (%)",
            "labels": ["Men", "Women"],
            "series_1_label": "% of the emirate's population",
            "series_1_values": [67, 33],
        },
        "summary": "About 67% of Abu Dhabi's population are men and 33% women (2024, Statistics Centre - Abu Dhabi).",
    },
    {
        "id": "fujairah_population_by_gender",
        "kb": ["What is the population of Fujairah?"],
        "require": [r"fujairah", r"\b(gender|men|women|males?|females?|sex)\b"],
        "keywords": "fujairah population by gender men women male female pie",
        "chart": {
            "chart_type": "pie",
            "title": "Fujairah's population by gender, mid-2025",
            "labels": ["Men", "Women"],
            "series_1_label": "People",
            "series_1_values": [214313, 114182],
        },
        "summary": (
            "Fujairah's population at mid-2025 was 214,313 men and 114,182 women, according to the Fujairah Statistics Centre "
            "(as reported by Gulf News)."
        ),
    },
    {
        "id": "sharjah_population_by_nationality",
        "kb": ["What is the population of Sharjah?"],
        "require": [r"sharjah", r"\b(nationalit\w*|emirati\w*|citizens?|expat\w*|nationals?|foreigners?|locals?)\b"],
        "keywords": "sharjah population by nationality emiratis non-uae nationals expats share pie",
        "sums_to": 100,
        "chart": {
            "chart_type": "pie",
            "title": "Sharjah's population by nationality, 2025 census (%)",
            "labels": ["Emiratis", "Non-UAE nationals"],
            "series_1_label": "% of the emirate's population",
            "series_1_values": [11, 89],
        },
        "summary": (
            "In the Sharjah Census 2025, non-UAE nationals were 89% of the population (1.9 million people) and Emiratis 11% "
            "(234,431)."
        ),
    },
    {
        "id": "dubai_resident_vs_daytime_population",
        "kb": ["What is the population of Dubai?"],
        "require": [r"dubai", r"daytime|day-time|commuters?|visitors?|temporar\w*|during the day", r"population|people|residents"],
        "keywords": "dubai daytime population residents temporarily present commuters visitors pie",
        "chart": {
            "chart_type": "pie",
            "title": "Who is in Dubai during the day (millions of people)",
            "labels": ["Residents", "Temporarily present (work, tourism, study, shopping)"],
            "series_1_label": "Millions of people",
            "series_1_values": [4.58, 1.81],
        },
        "summary": (
            "Dubai has 4.58 million residents, and about 1.81 million more people are temporarily present during the day for work, "
            "tourism, study or shopping, bringing the daytime population to about 6.39 million (Dubai Data and Statistics Establishment)."
        ),
    },
    # ---- banks -----------------------------------------------------------------------------
    {
        "id": "bank_types_islamic_conventional",
        "kb": ["How many banks are there in the UAE?"],
        "require": [r"banks?", r"islamic|conventional"],
        "exclude": [r"\b(assets|deposits|loans?|credit|rates?|accounts?|fees?|profit|returns?)\b"],
        "keywords": "number of islamic banks and conventional banks in the uae pie",
        "chart": {
            "chart_type": "pie",
            "title": "UAE banks: conventional and Islamic (Q2 2026)",
            "labels": ["Conventional banks", "Islamic banks"],
            "series_1_label": "Number of banks",
            "series_1_values": [52, 10],
        },
        "summary": (
            "Of the 62 banks operating in the UAE, 52 are conventional (including wholesale banks) and 10 are Islamic "
            "(Central Bank, Q2 2026)."
        ),
    },
    {
        "id": "bank_ownership_national_foreign",
        "kb": ["How many banks are there in the UAE?"],
        "require": [r"banks?", r"\b(national|foreign|domestic|local|overseas)\b"],
        "exclude": [r"\b(assets|deposits|loans?|credit|rates?|accounts?|fees?|islamic|conventional)\b"],
        "keywords": "number of national banks and foreign banks in the uae pie",
        "chart": {
            "chart_type": "pie",
            "title": "UAE banks: national and foreign (Q2 2026)",
            "labels": ["National banks", "Foreign banks (incl. wholesale)"],
            "series_1_label": "Number of banks",
            "series_1_values": [24, 38],
        },
        "summary": (
            "Of the 62 banks operating in the UAE, 24 are national banks and 38 are foreign banks, including wholesale banks "
            "(Central Bank, Q2 2026)."
        ),
    },
    # ---- macro: growth, prices, public finances --------------------------------------------
    {
        "id": "real_gdp_growth_2023_2027",
        "kb": ["What is the outlook for UAE economic growth in 2026?"],
        "require": [r"\bgdp\b|economy|economic", r"growth|grow\w*|expan\w*|forecast\w*|outlook|projections?"],
        "exclude": [r"\b(sectors?|industr\w*|emirates?|dubai|abu dhabi|sharjah|quarter\w*|q[1-4]|months?|first|trade|banks?|banking|inflation)\b"],
        "keywords": "uae real gdp growth 2023 2024 2025 2026 2027 forecast non-hydrocarbon overall economy outlook",
        "chart": {
            "chart_type": "bar",
            "title": "UAE real GDP growth (%), 2026-27 are Central Bank forecasts",
            "labels": ["2023", "2024", "2025", "2026 (forecast)", "2027 (forecast)"],
            "series_1_label": "Overall GDP growth (%)",
            "series_1_values": [4.3, 6.6, 6.2, 1.7, 9.8],
            "series_2_label": "Non-hydrocarbon GDP growth (%)",
            "series_2_values": [7.0, 8.6, 6.8, 1.9, 4.5],
        },
        "summary": (
            "UAE real GDP grew 4.3% in 2023, 6.6% in 2024 and 6.2% in 2025; the Central Bank forecasts 1.7% for 2026 and 9.8% for 2027. "
            "Non-oil (non-hydrocarbon) GDP grew 7.0%, 8.6% and 6.8% in those years, with 1.9% and 4.5% forecast. Forecasts are revised "
            "each quarter (Central Bank, June 2026)."
        ),
    },
    {
        "id": "q1_2026_sector_growth",
        "kb": ["How fast did the UAE economy grow in the first quarter of 2026?"],
        "require": [r"sectors?|industr\w*", r"grow\w*|fastest|expan\w*", r"\bq1\b|first quarter|2026"],
        "prefer": [r"\bq1\b|first quarter|2026"],
        "keywords": "uae sector growth first quarter 2026 finance insurance construction health information communication real estate trade",
        "chart": {
            "chart_type": "bar",
            "title": "UAE GDP growth by sector, Q1 2026 (%)",
            "labels": [
                "Financial and insurance", "Construction", "Human health and social work", "Information and communication",
                "Professional, scientific, technical and admin", "Real estate", "Public administration", "Wholesale and retail trade",
            ],
            "series_1_label": "Growth on a year earlier (%)",
            "series_1_values": [17.3, 8.1, 7.7, 5.9, 4.9, 4.8, 4.5, 2.6],
        },
        "summary": (
            "In Q1 2026 UAE GDP by sector: financial and insurance grew 17.3%, construction 8.1%, human health and social work 7.7%, "
            "information and communication 5.9%, professional, scientific, technical and administrative services 4.9%, real estate 4.8%, "
            "public administration 4.5% and wholesale and retail trade 2.6% (FCSC)."
        ),
    },
    {
        "id": "non_oil_share_q1_2026",
        "kb": ["How fast did the UAE economy grow in the first quarter of 2026?"],
        "require": [
            r"\b(oil|hydrocarbons?)\b",
            r"share|split|contribut\w*|proportion|pie|breakdown|composition|vs|versus|diversif\w*|mix|portion",
            r"\bgdp\b|economy",
        ],
        "exclude": [r"\b(biggest|largest|top|sectors?|industr\w*|production|output|barrels?)\b"],
        "keywords": "share of non-oil activities in uae gdp oil and gas versus non-oil diversification pie",
        "remainder": True,
        "sums_to": 100,
        "chart": {
            "chart_type": "pie",
            "title": "Non-oil share of UAE GDP, Q1 2026 (%)",
            "labels": ["Non-oil activities", "Oil and gas (the rest of GDP)"],
            "series_1_label": "% of GDP",
            "series_1_values": [79.4, _rest(79.4)],
        },
        "summary": "Non-oil activities made up 79.4% of UAE GDP in the first quarter of 2026, up from 78.0% in 2025; oil and gas make up the rest (FCSC).",
    },
    {
        "id": "uae_inflation_2023_2027",
        "kb": ["What is the inflation rate in the UAE?"],
        "require": [r"inflation|\bcpi\b|consumer prices?"],
        "exclude": [r"\b(months?|monthly|emirates?|dubai|abu dhabi|categor\w*|housing|food|sectors?|weekly)\b"],
        "keywords": "uae inflation rate 2023 2024 2025 2026 2027 forecast cpi consumer prices",
        "chart": {
            "chart_type": "bar",
            "title": "UAE inflation (%), 2026-27 are Central Bank forecasts",
            "labels": ["2023", "2024", "2025", "2026 (forecast)", "2027 (forecast)"],
            "series_1_label": "Inflation (%)",
            "series_1_values": [1.6, 1.7, 1.3, 2.3, 1.9],
        },
        "summary": (
            "UAE inflation was 1.6% in 2023, 1.7% in 2024 and 1.3% in 2025 (rounded; FCSC puts 2025 at 1.25%), with the Central Bank "
            "forecasting 2.3% for 2026 and 1.9% for 2027."
        ),
    },
    {
        "id": "fiscal_surplus",
        "kb": ["What is the UAE's fiscal position: budget surplus and government debt?"],
        "require": [r"\b(surplus|deficit|fiscal)\b|budget (surplus|deficit|balance)|government (finances|balance|revenue|spending)|public finances?"],
        "exclude": [r"\bdebt\b"],
        "keywords": "uae general government budget surplus fiscal balance percent of gdp 2024 2025",
        "chart": {
            "chart_type": "bar",
            "title": "UAE general government budget surplus (% of GDP)",
            "labels": ["2024", "2025"],
            "series_1_label": "Surplus (% of GDP)",
            "series_1_values": [6.2, 3.7],
        },
        "summary": "The UAE's general government budget surplus was 3.7% of GDP in 2025, down from 6.2% in 2024 as spending rose (Central Bank, June 2026).",
    },
    {
        "id": "government_debt",
        "kb": ["What is the UAE's fiscal position: budget surplus and government debt?"],
        "require": [r"\bdebt\b", r"\b(government|uae|public|federal|national|sovereign)\b"],
        "exclude": [r"\b(credit card|personal|consumer|household|student|good|bad|snowball|avalanche|mortgage)\b"],
        "keywords": "uae government gross debt percent of gdp 2024 2025 2026 imf projection",
        "chart": {
            "chart_type": "bar",
            "title": "UAE government gross debt (% of GDP)",
            "labels": ["2024", "2025", "2026 (IMF projection)"],
            "series_1_label": "Gross debt (% of GDP)",
            "series_1_values": [34.9, 34.3, 31.4],
        },
        "summary": "UAE government gross debt was 34.9% of GDP in 2024 and 34.3% in 2025, and the IMF projects 31.4% for 2026 (Central Bank, June 2026).",
    },
    {
        "id": "uae_pmi_2026",
        "kb": ["How strong is UAE business activity and employment (PMI, jobs, wages)?"],
        "require": [r"\bpmi\b|purchasing managers"],
        "keywords": "uae pmi dubai pmi purchasing managers index march april 2026 expansion",
        "chart": {
            "chart_type": "bar",
            "title": "Purchasing Managers' Index, 2026 (above 50 = expansion)",
            "labels": ["March 2026", "April 2026"],
            "series_1_label": "UAE PMI",
            "series_1_values": [52.9, 52.1],
            "series_2_label": "Dubai PMI",
            "series_2_values": [53.2, 51.6],
        },
        "summary": (
            "The UAE PMI eased to 52.1 in April 2026 from 52.9 in March, and Dubai's to 51.6 from 53.2; readings above 50 mean activity is "
            "still expanding (Central Bank, June 2026)."
        ),
    },
    {
        "id": "money_supply_march_2026",
        "kb": ["How much money is in the UAE economy (M1, M2, M3) and how has the dirham moved?"],
        "require": [r"money supply|\bm[123]\b|monetary aggregates?"],
        "keywords": "uae money supply m1 m2 m3 monetary aggregates end of march 2026",
        "chart": {
            "chart_type": "bar",
            "title": "UAE money supply, end of March 2026 (AED billion)",
            "labels": ["M1", "M2", "M3"],
            "series_1_label": "AED billion",
            "series_1_values": [1073, 2869, 3407],
        },
        "summary": "At the end of March 2026 UAE money supply was AED 1,073 billion (M1), AED 2,869 billion (M2) and AED 3,407 billion (M3) (Central Bank, June 2026).",
    },
    {
        "id": "oil_production_change",
        "kb": ["What is happening to UAE oil production in 2026?"],
        "require": [r"\b(oil|crude)\b", r"production|output|barrels?"],
        "keywords": "uae oil production change year on year q3 q4 2025 march april 2026 regional maritime disruption",
        "chart": {
            "chart_type": "bar",
            "title": "UAE oil production, change on a year earlier (%)",
            "labels": ["Q3 2025", "Q4 2025", "March 2026", "April 2026"],
            "series_1_label": "Change on a year earlier (%)",
            "series_1_values": [10.5, 16.6, -34.3, -30.4],
        },
        "summary": (
            "UAE oil production rose 10.5% year on year in Q3 2025 and 16.6% in Q4 2025, then fell 34.3% in March 2026 and 30.4% in April 2026 "
            "because of temporary regional maritime-route disruptions (Central Bank, June 2026)."
        ),
    },
    # ---- macro: trade ----------------------------------------------------------------------
    {
        "id": "trade_composition_2025",
        "kb": ["How much does the UAE trade with the rest of the world?"],
        "require": [r"\b(foreign trade|non-?oil trade|trade|exports?|imports?)\b"],
        "exclude": [
            r"\b(destinations?|markets?|partners?|countr\w*|customers?|buyers?|suppliers?|products?|goods|categor\w*|commodit\w*|gold|"
            r"jewell?ery|aluminium|telecom\w*|diamonds?|vehicles?|cars?|tax|taxes|customs|duty|duties|vat)\b"
        ],
        "keywords": "uae non-oil foreign trade 2025 exports re-exports imports composition breakdown pie",
        "chart": {
            "chart_type": "pie",
            "title": "UAE non-oil foreign trade of goods, 2025 (AED billion)",
            "labels": ["Non-oil exports", "Re-exports", "Imports"],
            "series_1_label": "AED billion",
            "series_1_values": [801.1, 719.6, 2047.9],
        },
        "summary": (
            "In 2025 the UAE's non-oil foreign trade of goods totalled AED 3,568 billion: imports AED 2,047.9 billion, non-oil exports "
            "AED 801.1 billion and re-exports AED 719.6 billion (Central Bank, June 2026, preliminary FCSC data)."
        ),
    },
    {
        "id": "export_destinations_2025",
        "kb": ["Which countries and products dominate UAE non-oil trade?"],
        "require": [r"\b(exports?|trade)\b", r"destinations?|markets?|partners?|countr\w*|customers?|buyers?"],
        "exclude": [r"\b(imports?|re-?exports?)\b"],
        "keywords": "uae non-oil export destinations switzerland india hong kong markets trade partners pie",
        "remainder": True,
        "sums_to": 100,
        "chart": {
            "chart_type": "pie",
            "title": "Destinations of UAE non-oil exports, 2025 (% of total)",
            "labels": ["Switzerland", "India", "Hong Kong SAR", "All other markets"],
            "series_1_label": "% of non-oil exports",
            "series_1_values": [21.5, 12.4, 11.6, _rest(21.5, 12.4, 11.6)],
        },
        "summary": (
            "The top destinations for UAE non-oil exports in 2025 were Switzerland (21.5% of the total), India (12.4%) and Hong Kong (11.6%); "
            "all other markets make up the rest (Central Bank, June 2026, preliminary FCSC data)."
        ),
    },
    {
        "id": "export_products_2025",
        "kb": ["Which countries and products dominate UAE non-oil trade?"],
        "require": [r"\b(exports?|trade)\b", r"products?|goods|categor\w*|commodit\w*|gold|jewell?ery|aluminium|what"],
        "exclude": [r"\b(imports?|re-?exports?|destinations?|markets?|partners?|countr\w*)\b"],
        "keywords": "uae non-oil exports by product gold jewellery aluminium share pie",
        "remainder": True,
        "sums_to": 100,
        "chart": {
            "chart_type": "pie",
            "title": "What the UAE exports (non-oil), 2025 (% of total)",
            "labels": ["Gold", "Jewellery", "Aluminium", "All other products"],
            "series_1_label": "% of non-oil exports",
            "series_1_values": [59.3, 4.9, 3.5, _rest(59.3, 4.9, 3.5)],
        },
        "summary": (
            "Gold made up 59.3% of UAE non-oil exports in 2025, jewellery 4.9% and aluminium 3.5%; all other products make up the rest "
            "(Central Bank, June 2026, preliminary FCSC data)."
        ),
    },
    {
        "id": "import_partners_2025",
        "kb": ["Which countries and products dominate UAE non-oil trade?"],
        "require": [r"\bimports?\b", r"partners?|countr\w*|suppliers?|sources?|from"],
        "exclude": [r"\bexports?\b|\b(products?|goods|categor\w*|commodit\w*)\b"],
        "keywords": "uae imports by country china india united states suppliers import partners pie",
        "remainder": True,
        "sums_to": 100,
        "chart": {
            "chart_type": "pie",
            "title": "Where the UAE's imports come from, 2025 (% of total)",
            "labels": ["China", "India", "United States", "All other suppliers"],
            "series_1_label": "% of imports",
            "series_1_values": [18.9, 6.7, 5.5, _rest(18.9, 6.7, 5.5)],
        },
        "summary": (
            "China supplied 18.9% of the UAE's imports in 2025, India 6.7% and the US 5.5%; all other suppliers make up the rest "
            "(Central Bank, June 2026, preliminary FCSC data)."
        ),
    },
    {
        "id": "import_products_2025",
        "kb": ["Which countries and products dominate UAE non-oil trade?"],
        "require": [r"\bimports?\b", r"products?|goods|categor\w*|commodit\w*|gold|telecom\w*|vehicles?|cars?|what"],
        "exclude": [r"\bexports?\b|\b(partners?|countr\w*|suppliers?)\b"],
        "keywords": "uae imports by product gold telecommunications equipment motor vehicles import categories pie",
        "remainder": True,
        "sums_to": 100,
        "chart": {
            "chart_type": "pie",
            "title": "What the UAE imports, 2025 (% of total)",
            "labels": ["Gold", "Telecommunications equipment", "Motor vehicles", "All other products"],
            "series_1_label": "% of imports",
            "series_1_values": [29.2, 10.1, 5.9, _rest(29.2, 10.1, 5.9)],
        },
        "summary": (
            "Gold was 29.2% of the UAE's imports in 2025, telecommunications equipment 10.1% and motor vehicles 5.9%; all other products "
            "make up the rest (Central Bank, June 2026, preliminary FCSC data)."
        ),
    },
]
