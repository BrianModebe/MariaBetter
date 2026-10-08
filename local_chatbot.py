"""
LocalRAGChatbot: the same retrieval-augmented pipeline as RAGChatbot
(rag_chatbot.py), but generation runs on a local model through Ollama
instead of the Claude API.

Pipeline:
    user query -> Retriever (TF-IDF over the knowledge base, unchanged)
               -> top-k passages
               -> local Ollama model (system prompt + passages + history),
                  with the calculator available as a tool
               -> answer, with sources cited from the retrieved passages

Requires Ollama (https://ollama.com) running locally with the
uae-finance-bot model built (see Modelfile -- `ollama create uae-finance-bot
-f Modelfile`), or any other tool-calling capable model pulled, e.g.:

    ollama pull llama3.2

No API key, no per-query cost, and queries never leave the machine. Answer
quality, speed, and tool-calling reliability depend on the model and your
hardware -- expect this to be slower and less consistent than the Claude
version, especially without a dedicated GPU. uae-finance-bot is llama3.2
with a lower temperature for more consistent behavior -- it does NOT fix
the underlying 3B model's tool-calling judgment, which is a capability
ceiling, not a parameter-tuning problem. That's why this class decides in
code when the tools are offered at all (see GATE_TOOLS below).
"""

import json
import re
from typing import Dict, List, Optional

import ollama

import calc_chart
import chart_library
from documents import LOCAL_BUDGET_CHARS
from calc_chart import CHART_REQUEST as _CHART_REQUEST
from retriever import Retriever
from tools import TOOLS, TOOL_FUNCTIONS, call_tool
from prompts import SYSTEM_PROMPT_TEMPLATE, _format_passages, widen_query_for_citation, CITATION_REQUEST, ARABIC_TEXT_RE


def _extract_leaked_tool_call(text: str) -> Optional[Dict]:
    """Smaller local models sometimes narrate a tool call as JSON text
    (e.g. 'Here's the chart: {"name": "render_chart", "parameters": {...}}')
    instead of using Ollama's structured tool_calls field. Salvage that
    instead of showing the user raw JSON: find the first balanced {...}
    object in the text and, if it parses and names a real tool, return it."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                except (json.JSONDecodeError, ValueError):
                    return None
                if isinstance(obj, dict) and obj.get("name") in TOOL_FUNCTIONS:
                    return obj
                return None
    return None


_FUNCTION_CALL_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in TOOL_FUNCTIONS) + r")\s*\((.*?)\)", re.S
)
_KV_RE = re.compile(r'["\']?(\w+)["\']?\s*[:=]\s*(?:"([^"]*)"|\'([^\']*)\'|(-?\d+(?:\.\d+)?))')


def _extract_leaked_function_call(text: str) -> Optional[Dict]:
    """A second narration style, distinct from _extract_leaked_tool_call's
    JSON-object form ('{"name": "render_chart", ...}'): a bare function-call
    expression like `show_payment_button({amount: 7000, client_name:
    "Rasheed", description: "Football deal"})` or `show_payment_button(
    amount=500, description="...")` printed as chat text/code instead of a
    real tool_calls entry. Live-confirmed and consistently reproducible for
    certain phrasings (see memory: local-model-status.md, 2026-09-30 update)
    -- _extract_leaked_tool_call doesn't catch this because there's no
    '"name"' key at all, just a bare identifier followed by '('. Pull the
    tool name and a best-effort key/value parse out of the parentheses;
    tolerant of JS-object, Python-kwarg, and JSON-quoted-key styles since the
    model isn't consistent about which one it uses. Returns the same
    {"name", "parameters"} shape as _extract_leaked_tool_call so both can
    feed the same salvage path in _run_tool_loop."""
    m = _FUNCTION_CALL_RE.search(text)
    if not m:
        return None
    name, arg_text = m.group(1), m.group(2)
    parameters = {}
    for km in _KV_RE.finditer(arg_text):
        key = km.group(1)
        value = km.group(2)
        if value is None:
            value = km.group(3)
        if value is None:
            value = km.group(4)
        parameters[key] = value
    return {"name": name, "parameters": parameters}


def _looks_like_broken_tool_call(text: str) -> bool:
    """A cheap heuristic for the case _extract_leaked_tool_call can't
    salvage: the model started narrating a tool-call JSON blob (contains
    '"name"' and an opening brace) but it never closed into valid JSON --
    usually truncated by the token limit mid-generation, or a repetition
    loop. Showing that raw to the user is worse than a clean apology."""
    return '"name"' in text and "{" in text


_TOOL_NAME_RE = re.compile(r"\b(" + "|".join(re.escape(n) for n in TOOL_FUNCTIONS) + r")\b")


def _mentions_tool_name_bare(text: str) -> bool:
    """A third narration variant, distinct from both leak extractors above:
    the model names a real tool in plain prose with no call syntax at all --
    no parens, no JSON -- e.g. "Here's a payment link button for you to send
    to Khalid: show_chase_payment_button" and then nothing. Live-confirmed
    (a real request that hit this exact case). Neither
    _extract_leaked_tool_call nor _extract_leaked_function_call can salvage
    it -- there's no argument structure to parse, so no button can be built
    -- so just flag it as broken; the caller routes it through the same
    clean-apology fallback as the other leak patterns rather than showing
    the bare function name to the user."""
    m = _TOOL_NAME_RE.search(text)
    if not m:
        return False
    return text[m.end():m.end() + 1] != "("


def _to_ollama_tools(anthropic_tools: List[Dict]) -> List[Dict]:
    """Convert tools.py's Anthropic-style tool schemas to Ollama's
    OpenAI-style {"type": "function", "function": {...}} format, so the
    schema and the Python implementation stay defined in one place."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in anthropic_tools
    ]


OLLAMA_TOOLS = _to_ollama_tools(TOOLS)

STUCK_MESSAGE = (
    "Sorry, I got stuck generating that response cleanly. Try rephrasing the question, "
    "or switch to the Claude backend for more reliable answers on requests like this."
)

NO_DATA_MESSAGE = (
    "I couldn't draw that chart -- my knowledge base doesn't have reliable data behind it, and I'd only "
    "be guessing. I can chart things like UAE tax rates and thresholds, notice periods, rent caps, "
    "population by emirate, GDP growth or sectors, inflation, foreign trade, banks by emirate, EIBOR "
    "rates, or an investment projection; or switch to the Claude backend for more."
)

# Live-tested: asked the same Arabic question twice, got the correct VAT rate (5%)
# once and a flatly wrong one ("5% to 13%") the other time -- not a one-off glitch,
# genuine inconsistency from this 3B model's weaker multilingual grounding. For a
# finance app, an unreliable number is worse than no number, so Arabic is declined
# here rather than attempted -- unlike the tool-calling capability gaps elsewhere in
# this file, this isn't something GATE_TOOLS-style code can route around; it's the
# model's own answer that's unreliable, in either language. (ARABIC_TEXT_RE itself
# lives in prompts.py -- shared with rag_chatbot.py/gemini_chatbot.py, which
# translate an Arabic query for retrieval instead of declining it outright.)
ARABIC_UNRELIABLE_MESSAGE = (
    "عذرًا، هذا النموذج المحلي (الأصغر حجمًا) غير موثوق بما يكفي للإجابة بالعربية -- قد يخطئ في الأرقام. "
    "الرجاء التبديل إلى Claude أو Gemini للأسئلة بالعربية.\n\n"
    "Sorry -- this local model isn't reliable enough in Arabic yet (it can get the numbers wrong). "
    "Please switch to the Claude or Gemini backend for Arabic questions."
)

# When a chart request's tool call comes out garbled, the best-matching knowledge-base
# passage decides what happens next. Requests for data we hold as a ready-made chart never
# get here (chart_library.py handles them), so anything that does is probably not chartable
# from the knowledge base: retry as plain text only when a passage matches very closely
# (the answer is then in the passages), otherwise decline instead of letting the model invent
# things ("the average salary is...", lists of banks). Measured TF-IDF scores: requests the
# passages really answer 0.45-0.66; requests they don't 0.17-0.41.
RETRY_MIN_SCORE = 0.45

# Appended to the system prompt for the one retry after a garbled tool call: the
# model gets no tools, so it has to answer in words instead of trying the chart
# call it just failed at.
_NO_CHART_NOTE = (
    "\n\nThe chart tool is unavailable for this reply. Do not draw, list, or describe a chart, and do "
    "not use tables or code blocks. Answer the question in plain text using ONLY facts stated in the "
    "reference passages -- never add figures, statistics, sources, or organizations from memory -- and "
    "say in one short line that you could not draw the chart this time. If the passages don't contain "
    "the data, say you don't have it and stop."
)

# The 3B model can't be trusted to decide *whether* a question needs a tool:
# handed the tools on a plain factual question ("what's the VAT threshold?"),
# it often calls render_chart anyway, gets a label/value error, and then
# answers from memory. So the code decides when the tools are offered at all;
# the model only chooses which tool and fills in the arguments. Set
# GATE_TOOLS = False to offer them on every turn, as the Claude backend does.
GATE_TOOLS = True
_CALC_REQUEST = re.compile(
    r"\b(invest\w*|compound\w*|interest|savings?|saving|save|grow\w*|returns?|projections?)\b|%|percent", re.I
)


# "invest 800 a month at 8% for 6 years, chart it" is a calculator chart (calc_chart.py),
# not one of the ready-made ones in chart_library.py -- so don't look for a match there.
_PROJECTION_REQUEST = re.compile(
    r"(?=.*\d)(?=.*\b(invest\w*|compound\w*|savings?|save|projection|monthly|per month|a month)\b)", re.I | re.S
)

# Doesn't need to name every currency -- get_exchange_rate's own alias map handles
# that; this just needs to recognize "this is a currency question" so the tool gets
# offered at all. No number required ("what's the exchange rate for USD?" has none).
_CURRENCY_REQUEST = re.compile(
    r"\b(exchange rate|forex|fx rate)\b|"
    r"\bconvert\w*\b.{0,25}\b(aed|dirhams?|usd|eur|gbp|inr|pkr)\b|"
    r"\b(aed|dirhams?)\b.{0,25}\b(usd|eur|gbp|inr|pkr|dollars?|euros?|pounds?|rupees?|riyals?|dinars?)\b|"
    r"\b(usd|eur|gbp|inr|pkr|dollars?|euros?|pounds?|rupees?|riyals?|dinars?)\b.{0,25}\b(aed|dirhams?)\b",
    re.I,
)

# Just recognizes "this looks like a real payment/invoicing request" so
# the nine show_*_button tools get offered at all -- the tools' own
# descriptions (and, for the hosted backends, the model's better judgment)
# still decide whether to actually call any of them. Deliberately narrower
# than a bare "charge"/"pay" match: those words show up constantly in
# ordinary tax/fee questions this bot already answers ("what does VAT
# charge"), which would misfire here.
_PAYMENT_REQUEST = re.compile(
    r"\b(invoice|billing|payment\s*link|payment\s+request|collect\s+(a\s+)?payment|request\s+payment|"
    r"charge\s+(my|a|the|this)\s+(client|customer)|bill\s+(my|a|the|this)\s+(client|customer)|"
    r"get\s+paid|pay\s+me\b|owes?\s+me|"
    r"quote\s+(a|my|the|this)\s+(client|customer)|send\s+(a\s+)?quote|"
    r"(price\s+)?estimate\s+(for|to)\s+(a\s+)?(client|customer)|"
    r"schedule\s+payments?|instal(l)?ments?|recurring\s+payment|payment\s+plan|"
    r"refund|overdue|chase\s+(this\s+|a\s+|the\s+)?payment|"
    r"remind\s+(my|a|the|this)\s+(client|customer)|"
    r"follow\s+up\s+(with|on)\s+(my|a|the|this)?\s*(client|customer|payment|invoice)|"
    r"how\s+do\s+i\s+(collect|get\s+paid)|collect\s+(the\s+|this\s+|a\s+)?(debt|money)\b|"
    r"onboard|sign\s+(up|(me|us|them)\s+up)|become\s+a\s+(simplebit\s+)?merchant|"
    r"start\s+(the\s+)?(onboarding|verification)|new\s+merchant|"
    r"remind\s+me\b|set\s+a\s+reminder|follow\s+up\s+with\s+\w+|"
    r"register\s+(a|my|this|the)?\s*(company|business|consultancy|firm|llc|startup)|"
    r"set\s+up\s+(a|my)\s+company|incorporate\s+(a|my)?\s*(company|business)?|"
    r"(get|start)\s+(my|this|the)?\s*(company|business)\s+(licensed|registered)|"
    r"start\s+(the\s+)?(registration|incorporation))\b", re.I
)


def _wants_tools(query: str, previous_turn_used_tools: bool) -> bool:
    """True when this message is a chart request, a currency conversion, a
    payment-collection request, a growth/savings calculation (needs a number
    in it -- "what is compound interest?" is just an explanation), or a
    numeric follow-up to a turn that already used a tool ("now for 10 years")."""
    has_number = bool(re.search(r"\d", query))
    if _CHART_REQUEST.search(query):
        return True
    if _CURRENCY_REQUEST.search(query):
        return True
    if _PAYMENT_REQUEST.search(query):
        return True
    if has_number and _CALC_REQUEST.search(query):
        return True
    return has_number and previous_turn_used_tools


class LocalRAGChatbot:
    def __init__(self, model: str = "uae-finance-bot", top_k: int = 3, host: Optional[str] = None):
        self.client = ollama.Client(host=host) if host else ollama.Client()
        self.model = model
        self.top_k = top_k
        self.retriever = Retriever()
        self.history: List[Dict] = []
        # Chart data from the most recent ask(), if render_chart was called
        # this turn -- see tools.py's module docstring.
        self.last_chart: Optional[Dict] = None
        # Same idea, for the nine show_*_button tools.
        self.last_payment_button: Optional[Dict] = None
        self.last_invoice_button: Optional[Dict] = None
        self.last_quote_button: Optional[Dict] = None
        self.last_schedule_payments_button: Optional[Dict] = None
        self.last_chase_payment_button: Optional[Dict] = None
        self.last_refund_button: Optional[Dict] = None
        self.last_talk_to_team_button: Optional[Dict] = None
        self.last_set_reminder_button: Optional[Dict] = None
        self.last_register_business_button: Optional[Dict] = None
        self._last_turn_used_tools = False
        # Calculator run from the current / previous turn, as (args, result),
        # so a chart can be built from its numbers -- see calc_chart.py.
        self._turn_calc = None
        self._turn_chart_type = None
        self._recent_calc = None
        self._top_score = 0.0  # similarity of the best knowledge-base passage for the current question
        # Files the user has uploaded to this chat (a documents.DocumentStore, set by
        # app.py). The local model's context window is small, so it gets a small budget.
        self.documents = None
        self.doc_budget = LOCAL_BUDGET_CHARS
        # The plain text of the last ask() call, so a bare "what's your source?"
        # follow-up can be widened to retrieve the same passage again -- see
        # prompts.py's widen_query_for_citation.
        self._last_query: Optional[str] = None

    def _note_tool(self, name: str, args: Dict, result) -> None:
        """Bookkeeping after each tool call: stash a rendered chart for the
        web UI, and remember a successful calculator run and the chart type
        the model picked, for _finish_calc_chart."""
        if not isinstance(result, dict) or "error" in result:
            return
        if name == "render_chart":
            self.last_chart = result
            self._turn_chart_type = result.get("chart_type")
        elif name == "compound_interest_calculator":
            self._turn_calc = (args, result)
        elif name == "show_payment_button":
            self.last_payment_button = result
        elif name == "show_invoice_button":
            self.last_invoice_button = result
        elif name == "show_quote_button":
            self.last_quote_button = result
        elif name == "show_schedule_payments_button":
            self.last_schedule_payments_button = result
        elif name == "show_chase_payment_button":
            self.last_chase_payment_button = result
        elif name == "show_refund_button":
            self.last_refund_button = result
        elif name == "show_talk_to_team_button":
            self.last_talk_to_team_button = result
        elif name == "show_set_reminder_button":
            self.last_set_reminder_button = result
        elif name == "show_register_business_button":
            self.last_register_business_button = result

    def _recover_from_broken_call(self, system_prompt: str, messages: List[Dict], use_tools: bool) -> str:
        if not use_tools:
            return STUCK_MESSAGE
        if self._top_score < RETRY_MIN_SCORE:
            return NO_DATA_MESSAGE
        return self._answer_without_tools(system_prompt, messages) or STUCK_MESSAGE

    def _answer_without_tools(self, system_prompt: str, messages: List[Dict]) -> Optional[str]:
        """After a garbled tool call, ask once more with no tools so the user
        gets a real text answer instead of an apology. None if that fails too."""
        retry = [{"role": "system", "content": system_prompt + _NO_CHART_NOTE}] + messages[1:]
        try:
            response = self.client.chat(model=self.model, messages=retry, options={"num_predict": 800})
        except Exception:
            return None
        text = (response["message"].get("content") or "").strip()
        looks_like_table = "|" in text and "---" in text
        if (not text or _looks_like_broken_tool_call(text) or "```" in text
                or looks_like_table or _extract_leaked_function_call(text)
                or _mentions_tool_name_bare(text)):
            return None
        return text

    def _run_tool_loop(self, system_prompt: str, use_tools: bool = True) -> str:
        messages = [{"role": "system", "content": system_prompt}] + self.history
        salvage_attempts = 0

        while True:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                tools=OLLAMA_TOOLS if use_tools else None,
                # Raised from 500, which was cutting real replies off mid-sentence (the
                # system prompt's ground rules have grown since 500 was set, and share
                # this budget with the answer text). Kept more conservative than the
                # hosted backends' 1200, though -- this runs on local hardware, and a
                # bigger ceiling means a genuinely longer wait if generation runs into
                # a repetition loop, not just a longer legitimate reply.
                options={"num_predict": 800},
            )
            msg = response["message"]
            tool_calls = msg.get("tool_calls")

            if not tool_calls:
                answer = (msg.get("content") or "").strip()

                leaked = None
                if use_tools and salvage_attempts < 2:
                    leaked = _extract_leaked_tool_call(answer) or _extract_leaked_function_call(answer)
                if leaked:
                    salvage_attempts += 1
                    name = leaked["name"]
                    args = leaked.get("parameters") or leaked.get("arguments") or {}
                    result = call_tool(name, args)
                    self._note_tool(name, args, result)
                    tool_msg = {"role": "tool", "name": name, "content": str(result)}
                    messages.append({"role": "assistant", "content": answer})
                    messages.append(tool_msg)
                    self.history.append({"role": "assistant", "content": answer})
                    self.history.append(tool_msg)
                    continue

                # Belt and braces: salvage_attempts may already be exhausted (the
                # model can repeat the narrated-call tic turn after turn -- live-
                # observed 3 times running for one message), in which case the
                # button this text describes was already captured on an earlier
                # loop iteration, but the raw code would otherwise still reach the
                # user in THIS turn's text. Route it through the same clean-apology
                # fallback as the JSON-leak case rather than showing it. Also
                # covers the bare-mention variant (_mentions_tool_name_bare) --
                # unlike the two leak extractors above there's no argument
                # structure to salvage from that one, so straight to the
                # clean-retry fallback rather than looping back with fake args.
                if (_looks_like_broken_tool_call(answer) or _extract_leaked_function_call(answer)
                        or _mentions_tool_name_bare(answer)):
                    answer = self._recover_from_broken_call(system_prompt, messages, use_tools)

                self.history.append({"role": "assistant", "content": answer})
                return answer

            messages.append(msg)
            self.history.append(msg)

            self._last_turn_used_tools = True
            for call in tool_calls:
                name = call["function"]["name"]
                args = call["function"]["arguments"]
                result = call_tool(name, args)
                self._note_tool(name, args, result)
                tool_msg = {"role": "tool", "name": name, "content": str(result)}
                messages.append(tool_msg)
                self.history.append(tool_msg)

    def _finish_calc_chart(self, query: str, calc, model_type: Optional[str]) -> Optional[str]:
        """Build the chart and summary from the calculator's own numbers (see
        calc_chart.py). Sets last_chart and returns the summary, or None if
        there's nothing to chart."""
        built = calc_chart.build(calc[0], calc[1], query, model_type)
        if built is None:
            return None
        self.last_chart, text = built
        self._recent_calc = calc
        return text

    def _chart_request_text(self, query: str) -> str:
        """What to match against the chart library. A bare follow-up like "graph
        it" carries no subject, so prepend the user's previous question."""
        if calc_chart.is_followup_chart_request(query):
            for message in reversed(self.history):
                if message.get("role") == "user":
                    return f"{message['content']} {query}"
        return query

    def ask(self, query: str) -> str:
        if ARABIC_TEXT_RE.search(query):
            return ARABIC_UNRELIABLE_MESSAGE

        self.last_chart = None
        self.last_payment_button = None
        self.last_invoice_button = None
        self.last_quote_button = None
        self.last_schedule_payments_button = None
        self.last_chase_payment_button = None
        self.last_refund_button = None
        self.last_talk_to_team_button = None
        self.last_set_reminder_button = None
        self.last_register_business_button = None
        self._turn_calc = None
        self._turn_chart_type = None
        # Only a calculation from the immediately preceding turn can be charted
        # by a bare "graph it" follow-up.
        previous_calc, self._recent_calc = self._recent_calc, None
        previous_query, self._last_query = self._last_query, query
        # "what's the source for that CHART?" contains a chart word, so without this
        # check it would trip the two fast paths below (built for "make it a pie
        # chart" style follow-ups) and just redraw the same chart instead of citing
        # it -- a real collision, found live. A citation request always goes to the
        # model instead, which can compose the citation from the widened retrieval.
        wants_citation = CITATION_REQUEST.search(query) is not None

        if not wants_citation and previous_calc and calc_chart.is_followup_chart_request(query):
            text = self._finish_calc_chart(query, previous_calc, None)
            if text:
                self.history.append({"role": "user", "content": query})
                self.history.append({"role": "assistant", "content": text})
                self._last_turn_used_tools = True
                return text

        # A chart of numbers we already hold (tax bands, thresholds, rent caps, ...):
        # the code draws it, no model call. See chart_library.py.
        if not wants_citation and _CHART_REQUEST.search(query) and not _PROJECTION_REQUEST.search(query):
            hit = chart_library.find_chart(self._chart_request_text(query))
            if hit:
                self.last_chart = hit.chart
                self.history.append({"role": "user", "content": query})
                self.history.append({"role": "assistant", "content": hit.text})
                self._last_turn_used_tools = False
                return hit.text

        retrieval_query = widen_query_for_citation(query, previous_query)
        passages = self.retriever.retrieve(retrieval_query, k=self.top_k)
        self._top_score = passages[0].score if passages else 0.0
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(passages=_format_passages(passages))
        if self.documents:
            system_prompt += self.documents.prompt_section(query, self.doc_budget)

        use_tools = _wants_tools(query, self._last_turn_used_tools) if GATE_TOOLS else True
        self._last_turn_used_tools = False  # set again if this turn calls a tool

        self.history.append({"role": "user", "content": query})
        answer = self._run_tool_loop(system_prompt, use_tools)

        if self._turn_calc:
            self._recent_calc = self._turn_calc
            if _CHART_REQUEST.search(query):
                # The model can't be trusted to chart (or even summarize) the
                # calculator's output, so replace its text with ours.
                text = self._finish_calc_chart(query, self._turn_calc, self._turn_chart_type)
                if text:
                    self.history[-1] = {"role": "assistant", "content": text}
                    answer = text
        return answer

    def reset(self) -> None:
        self.history = []
        self._last_turn_used_tools = False
        self._turn_calc = None
        self._turn_chart_type = None
        self._recent_calc = None
        self._last_query = None
