"""
RAGChatbot: retrieval-augmented finance & finance-adjacent-law chatbot for
users across all seven emirates.

Pipeline (see the "UAE Finance Pro Chatbot" roadmap doc):
    user query -> Retriever (TF-IDF over the knowledge base)
               -> top-k passages
               -> Claude API call (system prompt + passages + conversation
                  history), with the calculator available as a tool
               -> answer, with sources cited from the retrieved passages

Requires an ANTHROPIC_API_KEY environment variable (see .env.example).
"""

import os
import re
from typing import List, Dict, Optional

from anthropic import Anthropic

from documents import CLAUDE_BUDGET_CHARS
from retriever import Retriever
from tools import TOOLS, call_tool
from prompts import (
    SYSTEM_PROMPT_TEMPLATE,
    _format_passages,
    widen_query_for_citation,
    ARABIC_TEXT_RE,
    TRANSLATE_FOR_RETRIEVAL_PROMPT,
    BLEND_ADDENDUM,
)

# A server-side tool: Anthropic executes the search and feeds results back to
# Claude within the same API call (no call_tool involvement, no extra turn in
# our loop) -- see https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search-tool.
# max_uses caps how many searches Claude can run for a single question, so a
# misjudged query can't run up an unbounded number of billed searches.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}

# Claude-only: local Ollama models have no search capability, and Gemini's
# equivalent (Google Search grounding) is a different mechanism -- this stays
# out of the shared prompts.py template and is appended only here.
WEB_SEARCH_ADDENDUM = """

You also have a web_search tool, only for genuinely time-varying market data \
that isn't and can't be in a static knowledge base: the current gold price, \
a UAE-listed share/stock price (DFM, ADX, or Nasdaq Dubai), or current real \
estate asking/rental prices. Don't use it for anything else -- not general \
UAE finance or legal questions the knowledge base doesn't cover (say \
plainly you don't have that, per the ground rules above), and not as a \
back door around the rule that you don't forecast future values -- only \
report what a source says the price is right now. When you answer using \
web_search, ALWAYS state where the number came from and when (e.g. "AED \
512/gram, per <source>, as of <date>") -- this overrides the default \
no-citation-unless-asked rule, because a live price without a timestamp is \
misleading, not merely undercited. If the search doesn't turn up a clear, \
recent number, say so instead of guessing or combining unrelated figures.
"""

# The prompt rule above wasn't enough on its own: offered the tool on every
# question, Claude sometimes wrote its answer, then ran an unneeded search
# "to double-check" a knowledge-base fact, then wrote the answer again (sometimes
# with an apology) -- and since all text blocks in a turn are joined, the user saw
# the duplicate. So the tool is only offered when the message looks like a
# live-price question (English or Arabic), or once it has already been used in
# this chat (the history then holds search blocks, which need the tool defined).
_LIVE_PRICE_RE = re.compile(
    r"\b(gold|silver|bullion|dfm|adx|nasdaq|stocks?|shares?|ticker|emaar|aldar|adnoc|"
    r"prices?|rents?|rental|asking|per\s+sq|trading\s+at)\b"
    r"|سعر|أسعار|اسعار|ذهب|الذهب|فضة|سهم|أسهم|اسهم|إيجار|ايجار|الإيجار",
    re.I,
)


class RAGChatbot:
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-5", top_k: int = 3):
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
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
        # Files the user has uploaded to this chat (a documents.DocumentStore, set by
        # app.py). Relevant excerpts are appended to the system prompt.
        self.documents = None
        self.doc_budget = CLAUDE_BUDGET_CHARS
        # The plain text of the last ask() call, so a bare "what's your source?"
        # follow-up can be widened to retrieve the same passage again -- see
        # prompts.py's widen_query_for_citation.
        self._last_query: Optional[str] = None
        # See _LIVE_PRICE_RE: whether web_search is offered this turn, and whether
        # this chat has ever used it (sticky, so old search blocks in history stay valid).
        self._offer_web_search = False
        self._used_web_search = False

    def _run_tool_loop(self, system_prompt: str) -> str:
        # Claude sometimes writes the real answer in the SAME turn as a tool_use block
        # (e.g. states the calculator's numbers, then also calls render_chart) -- collect
        # text from every turn, not just the final one, or that answer gets silently
        # dropped. Confirmed live: "invest 800/month at 8% for 6 years" answered with the
        # real numbers in the same turn it called render_chart, and the old code showed
        # only the next turn's closing disclaimer, never the numbers.
        collected_text: List[str] = []
        while True:
            response = self.client.messages.create(
                model=self.model,
                # 500 was cutting real replies off mid-sentence -- a tool-call's JSON
                # (e.g. render_chart with several data points) shares this same budget
                # with the answer text, and the system prompt has grown several ground
                # rules (citation formatting, the BLEND_ADDENDUM flag, ...) since 500
                # was set, all of which add to a compliant reply's own length too.
                # Confirmed live: even 1200 still cut off a genuinely multi-part
                # comparison question (Ejari/Tawtheeq + Dubai/Abu Dhabi rent rules)
                # mid-word -- a short reply is still short at 2048, this only raises
                # the ceiling for cases that actually need the room.
                max_tokens=2048,
                system=system_prompt,
                tools=TOOLS + ([WEB_SEARCH_TOOL] if self._offer_web_search else []),
                messages=self.history,
            )
            if any(b.type == "server_tool_use" for b in response.content):
                self._used_web_search = True
            collected_text.extend(b.text for b in response.content if b.type == "text")

            if response.stop_reason != "tool_use":
                answer = "\n\n".join(t.strip() for t in collected_text if t.strip())
                self.history.append({"role": "assistant", "content": response.content})
                return answer

            self.history.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = call_tool(block.name, block.input)
                if block.name == "render_chart" and "error" not in result:
                    self.last_chart = result
                elif block.name == "show_payment_button" and "error" not in result:
                    self.last_payment_button = result
                elif block.name == "show_invoice_button" and "error" not in result:
                    self.last_invoice_button = result
                elif block.name == "show_quote_button" and "error" not in result:
                    self.last_quote_button = result
                elif block.name == "show_schedule_payments_button" and "error" not in result:
                    self.last_schedule_payments_button = result
                elif block.name == "show_chase_payment_button" and "error" not in result:
                    self.last_chase_payment_button = result
                elif block.name == "show_refund_button" and "error" not in result:
                    self.last_refund_button = result
                elif block.name == "show_talk_to_team_button" and "error" not in result:
                    self.last_talk_to_team_button = result
                elif block.name == "show_set_reminder_button" and "error" not in result:
                    self.last_set_reminder_button = result
                elif block.name == "show_register_business_button" and "error" not in result:
                    self.last_register_business_button = result
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

            self.history.append({"role": "user", "content": tool_results})

    def _retrieval_text(self, query: str) -> str:
        """What to actually search the (English-only) knowledge base with. The
        KB's questions/alt-phrasings/answers are all English, and TF-IDF is
        purely lexical -- an Arabic query shares no vocabulary with it and
        retrieves nothing (confirmed live: 3 passages for a question in
        English, 0 for the same question in Arabic). Translate just for this
        lookup; the original query is still what goes to the model and the user."""
        if not ARABIC_TEXT_RE.search(query):
            return query
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                system=TRANSLATE_FOR_RETRIEVAL_PROMPT,
                messages=[{"role": "user", "content": query}],
            )
            translated = "".join(b.text for b in resp.content if b.type == "text").strip()
            return translated or query
        except Exception:
            return query  # retrieval just finds nothing -- better than failing the whole turn

    def ask(self, query: str) -> str:
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
        retrieval_query = widen_query_for_citation(query, self._last_query)
        self._last_query = query
        retrieval_query = self._retrieval_text(retrieval_query)
        passages = self.retriever.retrieve(retrieval_query, k=self.top_k)
        self._offer_web_search = self._used_web_search or bool(_LIVE_PRICE_RE.search(query))
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(passages=_format_passages(passages)) + BLEND_ADDENDUM
        if self._offer_web_search:
            system_prompt += WEB_SEARCH_ADDENDUM
        if self.documents:
            system_prompt += self.documents.prompt_section(query, self.doc_budget)

        self.history.append({"role": "user", "content": query})
        return self._run_tool_loop(system_prompt)

    def reset(self) -> None:
        self.history = []
        self._last_query = None
        self._used_web_search = False
