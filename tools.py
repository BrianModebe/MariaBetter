"""
Tools the RAG chatbot can call via Claude's tool use (function calling).

Each tool has:
  - a JSON schema (TOOLS list) describing it to the Claude API
  - a plain Python function that executes it
  - an entry in TOOL_FUNCTIONS mapping name -> function, used by the
    chatbot's tool-execution loop.

Add new calculators here (mortgage affordability, gratuity, etc. -- see
Phase 4 of the roadmap) the same way: schema + function + registry entry.

render_chart and the nine show_*_button tools (show_payment_button,
show_invoice_button, show_quote_button, show_schedule_payments_button,
show_chase_payment_button, show_refund_button, show_talk_to_team_button,
show_set_reminder_button, show_register_business_button) are handled a bit
specially by all three chatbot backends: their return values are also
stashed on the chatbot instance (self.last_chart / self.last_payment_button /
self.last_invoice_button / self.last_quote_button /
self.last_schedule_payments_button / self.last_chase_payment_button /
self.last_refund_button / self.last_talk_to_team_button /
self.last_set_reminder_button / self.last_register_business_button) so
app.py can send them to the browser to render for real, in addition to
feeding back into the model's context like any other tool result. See
static/index.html's Chart.js rendering and static/maria.html's
business-action button rendering.
"""

from typing import Dict, List

from live_rates import get_exchange_rate


def compound_interest_calculator(
    principal: float,
    monthly_contribution: float,
    annual_rate_pct: float,
    years: float,
) -> Dict:
    """Project savings growth with monthly contributions and compounding."""
    # Local models (via Ollama) don't enforce the schema's numeric types as
    # strictly as Claude's tool use does, and sometimes pass numbers as
    # strings -- coerce defensively so both backends work.
    principal = float(principal)
    monthly_contribution = float(monthly_contribution)
    annual_rate_pct = float(annual_rate_pct)
    years = float(years)

    monthly_rate = (annual_rate_pct / 100) / 12
    months = int(round(years * 12))

    balance = principal
    total_contributed = principal
    yearly_breakdown = []
    for month in range(1, months + 1):
        balance += monthly_contribution
        total_contributed += monthly_contribution
        balance *= (1 + monthly_rate)
        if month % 12 == 0:
            yearly_breakdown.append({
                "year": month // 12,
                "total_contributed": round(total_contributed, 2),
                "balance": round(balance, 2),
            })

    return {
        "years": years,
        "total_contributed": round(total_contributed, 2),
        "investment_growth": round(balance - total_contributed, 2),
        "ending_balance": round(balance, 2),
        # One entry per full year elapsed -- pass this straight through as
        # labels/values if the user wants a chart of the growth over time.
        "yearly_breakdown": yearly_breakdown,
    }


def show_payment_button(amount: float = None, description: str = None, client_name: str = None) -> Dict:
    """Signal the frontend to render a 'Create payment link' button. No real
    SimpleBit payment integration exists yet (see maria.html's paymentButton
    handling) -- this just carries the label context through; the button
    itself shows a clearly-marked placeholder when clicked, not a real link."""
    result: Dict = {"shown": True}
    if amount is not None:
        try:
            result["amount"] = float(amount)
        except (TypeError, ValueError):
            pass
    if description:
        result["description"] = str(description)[:120]  # it's a button label, not a paragraph
    if client_name:
        result["client_name"] = str(client_name)[:60]
    return result


def show_invoice_button(amount: float = None, description: str = None, client_name: str = None) -> Dict:
    """Signal the frontend to render a 'Generate invoice' button. Same
    no-real-backend situation as show_payment_button -- distinct tool because
    a formal invoice (client name, line item) is a different request from a
    quick payment link, even though the model may reasonably call both."""
    result: Dict = {"shown": True}
    if amount is not None:
        try:
            result["amount"] = float(amount)
        except (TypeError, ValueError):
            pass
    if description:
        result["description"] = str(description)[:120]
    if client_name:
        result["client_name"] = str(client_name)[:60]
    return result


def show_quote_button(amount: float = None, description: str = None, client_name: str = None) -> Dict:
    """Signal the frontend to render a 'Generate quote' button. Same
    no-real-backend situation as show_payment_button -- distinct from
    show_invoice_button: a quote is a price PROPOSAL for prospective work,
    sent before anything is agreed or done, not a bill for completed work."""
    result: Dict = {"shown": True}
    if amount is not None:
        try:
            result["amount"] = float(amount)
        except (TypeError, ValueError):
            pass
    if description:
        result["description"] = str(description)[:120]
    if client_name:
        result["client_name"] = str(client_name)[:60]
    return result


def show_schedule_payments_button(
    amount: float = None,
    description: str = None,
    client_name: str = None,
    installments: int = None,
    frequency: str = None,
) -> Dict:
    """Signal the frontend to render a 'Schedule payments' button, for
    setting up a recurring/installment plan rather than a one-off amount.
    Same no-real-backend situation as the other show_*_button tools."""
    result: Dict = {"shown": True}
    if amount is not None:
        try:
            result["amount"] = float(amount)
        except (TypeError, ValueError):
            pass
    if description:
        result["description"] = str(description)[:120]
    if client_name:
        result["client_name"] = str(client_name)[:60]
    if installments is not None:
        try:
            result["installments"] = int(installments)
        except (TypeError, ValueError):
            pass
    if frequency:
        result["frequency"] = str(frequency)[:30]
    return result


def show_chase_payment_button(amount: float = None, description: str = None, client_name: str = None, days_overdue: int = None) -> Dict:
    """Signal the frontend to render a 'Send reminder' button, for nudging a
    client about money they already owe (an existing unpaid request), not
    a fresh ask. Same no-real-backend situation as the other buttons."""
    result: Dict = {"shown": True}
    if amount is not None:
        try:
            result["amount"] = float(amount)
        except (TypeError, ValueError):
            pass
    if description:
        result["description"] = str(description)[:120]
    if client_name:
        result["client_name"] = str(client_name)[:60]
    if days_overdue is not None:
        try:
            result["days_overdue"] = int(days_overdue)
        except (TypeError, ValueError):
            pass
    return result


def show_refund_button(amount: float = None, description: str = None, client_name: str = None) -> Dict:
    """Signal the frontend to render a 'Send refund' button -- the only one
    of the six show_*_button tools where money flows the other way (back to
    the client). Same no-real-backend situation as the others."""
    result: Dict = {"shown": True}
    if amount is not None:
        try:
            result["amount"] = float(amount)
        except (TypeError, ValueError):
            pass
    if description:
        result["description"] = str(description)[:120]
    if client_name:
        result["client_name"] = str(client_name)[:60]
    return result


def show_talk_to_team_button(business_name: str = None, reason: str = None) -> Dict:
    """Signal the frontend to render a 'Talk to team' button -- distinct from
    the other six show_*_button tools, which simulate a SimpleBit merchant
    action. This one is for when the user wants to actually onboard/sign up
    a business as a new SimpleBit merchant, which Maria genuinely cannot do
    herself; the button hands them off to a human instead of pretending to
    onboard anyone. Same no-real-backend situation as the others -- clicking
    it shows a clearly-marked placeholder, not a real handoff, yet."""
    result: Dict = {"shown": True}
    if business_name:
        result["business_name"] = str(business_name)[:60]
    if reason:
        result["reason"] = str(reason)[:120]
    return result


def show_set_reminder_button(note: str = None, client_name: str = None, when: str = None) -> Dict:
    """Signal the frontend to render a 'Set reminder' button -- a general
    follow-up task for the MERCHANT to be nudged about later, distinct from
    show_chase_payment_button: that one is client-facing (a message sent TO a
    client about money they already owe); this one is private and isn't
    about outstanding money at all -- 'remind me to follow up with Sara next
    week', 'set a reminder to check if the client replied', 'remind me to
    call Rasheed about the deal'. No real link to fake here (unlike the
    payment/invoice/quote/chase buttons) -- there's no backend to actually
    schedule a notification, so clicking it shows a clearly-marked
    placeholder rather than a real reminder."""
    result: Dict = {"shown": True}
    if note:
        result["note"] = str(note)[:160]
    if client_name:
        result["client_name"] = str(client_name)[:60]
    if when:
        result["when"] = str(when)[:60]
    return result


def show_register_business_button(business_type: str = None, authority: str = None, emirate: str = None) -> Dict:
    """Signal the frontend to render a 'Register business' button -- for
    actually STARTING a new UAE company's registration/licensing process
    (mainland, free zone, or offshore), distinct from
    show_talk_to_team_button, which is about onboarding a business as a
    SimpleBit merchant, not about UAE company formation itself. Registering
    a company is a multi-step legal process (document submission, approvals,
    sometimes in-person steps) that Maria genuinely cannot complete via a
    link, so -- like show_talk_to_team_button and show_set_reminder_button --
    there's no fake payment-style link here; clicking it shows a clearly-
    marked placeholder rather than a real registration."""
    result: Dict = {"shown": True}
    if business_type:
        result["business_type"] = str(business_type)[:60]
    if authority:
        result["authority"] = str(authority)[:100]
    if emirate:
        result["emirate"] = str(emirate)[:40]
    return result


CHART_TYPES = ("bar", "stacked_bar", "line", "pie", "radar")


def render_chart(
    chart_type: str,
    title: str,
    labels: List[str],
    series_1_label: str,
    series_1_values: List[float],
    series_2_label: str = None,
    series_2_values: List[float] = None,
) -> Dict:
    """Validate chart data and reshape it into {chart_type, title, labels,
    datasets: [{label, values}, ...]} for the frontend to draw.

    The input is deliberately flat (up to 2 series as separate label/values
    pairs, not a nested array-of-objects) because local models are much less
    reliable at filling in nested tool arguments correctly than Claude is --
    the reshaping into a clean nested structure happens here instead.

    Cosmetic presentation choices (e.g. whether a bar chart renders
    horizontally when there are many/long labels) are decided by the
    frontend from the data shape, not by the model -- see static/index.html
    -- so the model only has to pick the chart's semantic shape."""
    if chart_type not in CHART_TYPES:
        return {"error": f"Unsupported chart_type '{chart_type}' -- use one of {', '.join(CHART_TYPES)}."}
    if not labels:
        return {"error": "labels must be non-empty."}
    if chart_type == "stacked_bar" and not (series_2_label and series_2_values):
        return {"error": "stacked_bar needs series_2_label/series_2_values too -- a stack needs at least 2 parts. Use 'bar' for a single measure."}

    datasets = []
    for label, values in ((series_1_label, series_1_values), (series_2_label, series_2_values)):
        if not label or not values:
            continue
        if len(values) != len(labels):
            return {
                "error": (
                    f"series '{label}' has {len(values)} values but there are "
                    f"{len(labels)} labels -- these must match."
                )
            }
        # Same defensive coercion as compound_interest_calculator: a local
        # model may pass numbers as strings -- but a non-number (text, null)
        # is an error the model should hear about, not a crash.
        numbers = []
        for v in values:
            try:
                numbers.append(float(v))
            except (TypeError, ValueError):
                return {
                    "error": (
                        f"series '{label}' must contain only numbers, but got {v!r}. Only chart real "
                        "numbers from the reference passages or the user's message; if you don't have "
                        "the data, say so instead of charting."
                    )
                }
        datasets.append({"label": label, "values": numbers})

    if not datasets:
        return {"error": "series_1_label and series_1_values are required."}

    return {
        "chart_type": chart_type,
        "title": title,
        "labels": [str(l) for l in labels],
        "datasets": datasets,
    }


TOOLS = [
    {
        "name": "compound_interest_calculator",
        "description": (
            "Project how savings or investments grow over time with monthly "
            "contributions and compound interest. Use this whenever the user "
            "asks a 'what if I save/invest X per month at Y% for Z years' "
            "style question, instead of estimating the math yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "description": "Starting amount already saved/invested, in AED (or the user's stated currency). Use 0 if none.",
                },
                "monthly_contribution": {
                    "type": "number",
                    "description": "Amount added every month.",
                },
                "annual_rate_pct": {
                    "type": "number",
                    "description": "Expected annual return, as a percentage (e.g. 7 for 7%).",
                },
                "years": {
                    "type": "number",
                    "description": "Number of years to project.",
                },
            },
            "required": ["principal", "monthly_contribution", "annual_rate_pct", "years"],
        },
    },
    {
        "name": "render_chart",
        "description": (
            "Draw a chart for the user, shown alongside your text answer, and pick "
            "whichever chart_type actually fits the data -- don't default to the same "
            "one every time:\n"
            "- line: a trend over time -- e.g. chart the yearly_breakdown from "
            "compound_interest_calculator (labels=years).\n"
            "- bar: comparing ONE measure across a few categories -- e.g. rent-increase "
            "cap % by emirate.\n"
            "- stacked_bar: showing what a total is made of, per category or year -- e.g. "
            "Total Contributed + Investment Growth stacked to show the ending balance per "
            "year (needs series_2).\n"
            "- pie: a share-of-whole breakdown at a single point in time -- e.g. the "
            "50/30/20 budget rule.\n"
            "- radar: comparing 2 entities across SEVERAL different metrics at once, one "
            "axis per metric -- e.g. Dubai vs Abu Dhabi across rent cap %, notice period "
            "(days), and registration fee. Only use this when the metrics are on a "
            "roughly comparable scale (don't put a percentage and a days-count on the "
            "same radar without normalizing them first).\n"
            "Use this for anything the user would rather see plotted than read as a "
            "paragraph of numbers. Don't use it for a single number or a yes/no fact -- "
            "only for genuinely chartable data (a series over time, or several "
            "comparable categories). "
            "IMPORTANT: every category/slice/time-point/axis goes in 'labels', with ONE "
            "matching number per label in series_1_values -- e.g. a 3-slice pie chart "
            "(Needs/Wants/Savings) is labels=[\"Needs\",\"Wants\",\"Savings\"], "
            "series_1_values=[50,30,20], NOT three separate series. Only use "
            "series_2_* when you have a genuinely second measurement for the *same* "
            "labels (e.g. 'Balance' and 'Total Contributed' for the same years, or a "
            "second entity's values on the same radar axes) -- there is no series_3."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "stacked_bar", "line", "pie", "radar"],
                    "description": "See the tool description above for when to use each.",
                },
                "title": {"type": "string", "description": "Short chart title."},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Every category/slice/time-point, e.g. [\"Needs\",\"Wants\",\"Savings\"] for a 3-slice pie chart, or [\"Dubai\",\"Abu Dhabi\"] for a 2-bar comparison. One chart can have as many labels as needed -- add more labels, not more series, for more categories.",
                },
                "series_1_label": {
                    "type": "string",
                    "description": "Name of the data series, e.g. 'Balance' or '% of income'.",
                },
                "series_1_values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Exactly one number per entry in 'labels', same order and same length, e.g. [50, 30, 20] for [\"Needs\", \"Wants\", \"Savings\"].",
                },
                "series_2_label": {
                    "type": "string",
                    "description": "Only for a genuine second measurement of the same labels, e.g. 'Total Contributed' alongside series_1 'Balance' for the same years. Omit entirely otherwise -- do not invent series_3.",
                },
                "series_2_values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "One number per entry in 'labels', matching series_2_label. Omit entirely if there's only one series.",
                },
            },
            "required": ["chart_type", "title", "labels", "series_1_label", "series_1_values"],
        },
    },
    {
        "name": "get_exchange_rate",
        "description": (
            "Get today's official AED exchange rate for a foreign currency, as published by the "
            "Central Bank of the UAE. Use this for ANY currency conversion or 'how much is X in "
            "AED/dirhams' question -- never estimate or recall an exchange rate from memory, rates "
            "move daily and a remembered number is often stale or wrong."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "currency": {
                    "type": "string",
                    "description": "The foreign currency, as a name or common code, e.g. 'US Dollar', 'USD', 'Indian Rupee', 'INR'.",
                },
            },
            "required": ["currency"],
        },
    },
    {
        "name": "show_payment_button",
        "description": (
            "Show a 'Create payment link' button in the chat, ONLY when the user is genuinely trying "
            "to collect a real payment right now -- e.g. they say they need to charge a specific "
            "client/customer, or ask how to request payment for work/goods/services they've provided. "
            "This is for a quick payment link, not a formal invoice document -- use show_invoice_button "
            "instead (or as well) when they specifically want an invoice. Do NOT call this for ordinary "
            "tax/fee/pricing QUESTIONS that merely mention money -- 'what does VAT charge on services', "
            "'how much does a trade licence cost', 'what fees does a bank charge' are informational, not "
            "a request to collect a payment, even though they use similar words. When genuinely unsure, "
            "don't call it -- a missing button is a minor inconvenience; an unwanted one on an unrelated "
            "question looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The AED amount to collect, if the user stated or clearly implied one. Omit if not given.",
                },
                "description": {
                    "type": "string",
                    "description": "A short label for what the payment is for, e.g. 'Design work invoice'. Omit if unclear.",
                },
                "client_name": {
                    "type": "string",
                    "description": "The client/customer being charged, if mentioned. Omit if not given.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "show_invoice_button",
        "description": (
            "Show a 'Generate invoice' button when the user wants a formal invoice document for a "
            "client/customer -- e.g. they ask to invoice, bill, or send an invoice to someone, "
            "especially when they name the client or give itemized/formal billing details. Distinct "
            "from show_payment_button (a quick payment link, no document) -- call BOTH if the request "
            "genuinely covers both (a real invoice often carries its own payment link), but don't call "
            "either for ordinary tax/fee/pricing QUESTIONS that merely mention money -- those are "
            "informational, not a billing request, even though the words overlap. When genuinely "
            "unsure, don't call it -- a missing button is a minor inconvenience; an unwanted one on an "
            "unrelated question looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The AED amount to invoice, if the user stated or clearly implied one. Omit if not given.",
                },
                "description": {
                    "type": "string",
                    "description": "A short label for what the invoice is for, e.g. 'Design work'. Omit if unclear.",
                },
                "client_name": {
                    "type": "string",
                    "description": "The client/customer's name, if mentioned. Omit if not given.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "show_quote_button",
        "description": (
            "Show a 'Generate quote' button when the user wants a price estimate/proposal for "
            "PROSPECTIVE work -- work that hasn't been agreed or done yet, sent to help a client "
            "decide whether to go ahead. e.g. 'I want to quote a client for a website redesign', "
            "'send an estimate for this project'. Distinct from show_invoice_button (billing work "
            "already completed) and show_payment_button (collecting money right now) -- those are for "
            "AFTER the work is agreed/done, this is BEFORE. Don't call it for ordinary tax/fee/pricing "
            "QUESTIONS that merely mention money -- those are informational, not a quote request, even "
            "though the words overlap. When genuinely unsure, don't call it -- a missing button is a "
            "minor inconvenience; an unwanted one on an unrelated question looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The AED amount being quoted, if the user stated or clearly implied one. Omit if not given.",
                },
                "description": {
                    "type": "string",
                    "description": "A short label for what the quote is for, e.g. 'Website redesign'. Omit if unclear.",
                },
                "client_name": {
                    "type": "string",
                    "description": "The prospective client/customer's name, if mentioned. Omit if not given.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "show_schedule_payments_button",
        "description": (
            "Show a 'Schedule payments' button when the user wants to collect an amount across "
            "several payments over time -- installments, a payment plan, or recurring billing -- "
            "rather than one lump sum. e.g. 'split this into 3 monthly payments', 'set up a recurring "
            "AED 500 a month from this client'. Can reasonably be called alongside show_invoice_button "
            "(an invoice broken into installments) -- don't call it for a simple one-off payment "
            "(use show_payment_button for that) or for ordinary tax/fee/pricing QUESTIONS that merely "
            "mention money. When genuinely unsure, don't call it -- a missing button is a minor "
            "inconvenience; an unwanted one on an unrelated question looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The TOTAL AED amount to be collected across all installments, if stated or clearly implied. Omit if not given.",
                },
                "description": {
                    "type": "string",
                    "description": "A short label for what the plan is for, e.g. 'Website retainer'. Omit if unclear.",
                },
                "client_name": {
                    "type": "string",
                    "description": "The client/customer's name, if mentioned. Omit if not given.",
                },
                "installments": {
                    "type": "integer",
                    "description": "How many payments the total is split across, if stated or clearly implied (e.g. 3, 6, 12). Omit if not given.",
                },
                "frequency": {
                    "type": "string",
                    "description": "How often payments recur, e.g. 'monthly', 'weekly', 'biweekly'. Omit if not given.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "show_chase_payment_button",
        "description": (
            "Show a 'Send reminder' button when the user wants to follow up on money a client "
            "ALREADY owes -- an existing unpaid invoice or payment request -- not a fresh ask. e.g. "
            "'my client still hasn't paid', 'I need to follow up with Sara about her overdue invoice', "
            "'can you chase this payment'. Distinct from show_payment_button/show_invoice_button, which "
            "are for creating a NEW request -- this is for nudging on one that's already outstanding. "
            "Don't call it for ordinary tax/fee/pricing QUESTIONS that merely mention money. When "
            "genuinely unsure, don't call it -- a missing button is a minor inconvenience; an unwanted "
            "one on an unrelated question looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The outstanding AED amount, if stated or clearly implied. Omit if not given.",
                },
                "description": {
                    "type": "string",
                    "description": "A short label for what the payment is for, e.g. 'Website invoice'. Omit if unclear.",
                },
                "client_name": {
                    "type": "string",
                    "description": "The client/customer who owes the money, if mentioned. Omit if not given.",
                },
                "days_overdue": {
                    "type": "integer",
                    "description": "How many days overdue the payment is, if stated or clearly implied. Omit if not given.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "show_refund_button",
        "description": (
            "Show a 'Send refund' button when the user wants to give money BACK to a client -- the "
            "only one of these business-action tools where money flows the other way. e.g. 'I need to "
            "refund Ahmed AED 500', 'the client wants their money back', 'I overcharged someone and "
            "need to return it'. Don't call it for ordinary tax/fee/pricing QUESTIONS that merely "
            "mention money. When genuinely unsure, don't call it -- a missing button is a minor "
            "inconvenience; an unwanted one on an unrelated question looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The AED amount to refund, if stated or clearly implied. Omit if not given.",
                },
                "description": {
                    "type": "string",
                    "description": "A short label for the reason, e.g. 'Cancelled order'. Omit if unclear.",
                },
                "client_name": {
                    "type": "string",
                    "description": "The client/customer being refunded, if mentioned. Omit if not given.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "show_talk_to_team_button",
        "description": (
            "Show a 'Talk to team' button when the user wants to actually onboard/sign up a business "
            "as a new SimpleBit merchant -- e.g. 'onboard my friend's cafe', 'sign this business up for "
            "SimpleBit', 'can you start the verification process', 'get them set up as a merchant'. Maria "
            "cannot onboard anyone herself, so pair this with an honest explanation (using what you know "
            "about onboarding requirements) rather than pretending to do it. Do NOT call this for a plain "
            "informational question about what onboarding requires or how long it takes ('what documents "
            "do I need to sign up', 'how long does approval take') -- only when they're asking to actually "
            "start the process or be connected with someone. When genuinely unsure, don't call it -- a "
            "missing button is a minor inconvenience; an unwanted one on an unrelated question looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "business_name": {
                    "type": "string",
                    "description": "The business being onboarded, if mentioned. Omit if not given.",
                },
                "reason": {
                    "type": "string",
                    "description": "A short label for what they need, e.g. 'Sign up as a merchant'. Omit if unclear.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "show_set_reminder_button",
        "description": (
            "Show a 'Set reminder' button for a general follow-up task -- distinct from "
            "show_chase_payment_button: that one is a message SENT TO a client about money they already "
            "owe; this one is private, for the merchant themselves, and ISN'T about outstanding money at "
            "all. e.g. 'remind me to follow up with Sara next week', 'set a reminder to check if the "
            "client replied', 'remind me to call Rasheed about the deal', 'I want a reminder to check on "
            "this quote in a few days'. If money already owed is the reason for the follow-up, prefer "
            "show_chase_payment_button instead (or as well, if genuinely both apply). Don't call this for "
            "ordinary tax/fee/pricing QUESTIONS. When genuinely unsure, don't call it -- a missing button "
            "is a minor inconvenience; an unwanted one on an unrelated question looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "A short label for what to be reminded about, e.g. 'Follow up on the rebrand quote'. Omit if unclear.",
                },
                "client_name": {
                    "type": "string",
                    "description": "Who the reminder relates to, if mentioned. Omit if not given.",
                },
                "when": {
                    "type": "string",
                    "description": "When to be reminded, as free text (e.g. 'next Tuesday', 'in 3 days'), if stated. Omit if not given.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "show_register_business_button",
        "description": (
            "Show a 'Register business' button when the user wants to actually START registering/"
            "incorporating a new UAE company -- e.g. 'I want to set up a company in JAFZA', 'how do I "
            "register my consultancy on the mainland', 'let's get this business licensed'. Distinct from "
            "show_talk_to_team_button, which is about signing a business up as a SimpleBit MERCHANT, not "
            "about UAE company formation -- use this one for the actual registration/licensing process "
            "itself. Maria cannot register a company herself, so pair this with an honest answer (using "
            "what you know about the relevant authority) rather than pretending to register anyone. Do "
            "NOT call this for a plain informational question about registration offices, fees, or "
            "process ('which authority registers a mainland LLC', 'what does a JAFZA license cost') -- "
            "only when they're asking to actually start registering. When genuinely unsure, don't call "
            "it -- a missing button is a minor inconvenience; an unwanted one on an unrelated question "
            "looks broken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "business_type": {
                    "type": "string",
                    "description": "What kind of business, if mentioned, e.g. 'Consultancy', 'Restaurant', 'Trading company'. Omit if not given.",
                },
                "authority": {
                    "type": "string",
                    "description": "The specific registering authority/zone this would go through, if established in the conversation, e.g. 'JAFZA', 'Dubai DET (mainland)', 'RAKEZ'. Omit if not given.",
                },
                "emirate": {
                    "type": "string",
                    "description": "Which emirate, if relevant and not already obvious from authority. Omit if not given.",
                },
            },
            "required": [],
        },
    },
]

TOOL_FUNCTIONS = {
    "compound_interest_calculator": compound_interest_calculator,
    "render_chart": render_chart,
    "get_exchange_rate": get_exchange_rate,
    "show_payment_button": show_payment_button,
    "show_invoice_button": show_invoice_button,
    "show_quote_button": show_quote_button,
    "show_schedule_payments_button": show_schedule_payments_button,
    "show_chase_payment_button": show_chase_payment_button,
    "show_refund_button": show_refund_button,
    "show_talk_to_team_button": show_talk_to_team_button,
    "show_set_reminder_button": show_set_reminder_button,
    "show_register_business_button": show_register_business_button,
}


def call_tool(name: str, kwargs: Dict) -> Dict:
    """Look up and safely call a tool by name, turning any exception (unknown
    tool, or wrong/missing/extra arguments) into an {"error": ...} dict
    instead of raising. Tool arguments come from a model's output, which
    isn't always well-formed -- especially from smaller local models -- and
    an uncaught exception here would otherwise crash the whole request."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"Unknown tool '{name}'"}
    try:
        return func(**kwargs)
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:  # e.g. a non-numeric value where a number was expected
        return {"error": f"{name} failed: {exc}"}
