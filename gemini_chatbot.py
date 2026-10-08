"""
GeminiRAGChatbot: the same retrieval-augmented pipeline as RAGChatbot
(rag_chatbot.py), but generation runs on Google's Gemini API instead of
Claude.

Pipeline:
    user query -> Retriever (TF-IDF over the knowledge base, unchanged)
               -> top-k passages
               -> Gemini API call (system instruction + passages +
                  conversation history), with the calculator/chart tools
                  available as function declarations
               -> answer, with sources cited from the retrieved passages

Requires a GEMINI_API_KEY environment variable (see .env.example) and the
google-genai package (`pip install google-genai`, listed in
requirements.txt). Get a key at https://aistudio.google.com/apikey -- never
paste a real key into chat; put it directly in .env.

NOT verified end to end against a live Gemini account: this was written
without a usable API key on hand. The request/response shapes below follow
the google-genai SDK's documented function-calling flow (Client,
GenerateContentConfig, FunctionDeclaration/Schema, Part.from_function_response),
but SDK details drift between versions. If the first real run raises an
error, paste the traceback back so this can be fixed against the actual
installed SDK version.
"""

import os
from typing import Dict, List, Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

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

# Google's fast, cheap current-generation model -- a reasonable default for a
# short-answer RAG assistant. Override with GeminiRAGChatbot(model="...") or
# a GEMINI_MODEL env var if a newer/cheaper model is preferred. (gemini-2.5-flash
# was retired for new users in 2026 -- confirmed live against the API on
# 2026-09-28; if this 404s again, the error message names the current model.)
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")


def _to_gemini_schema(schema: Dict) -> types.Schema:
    """tools.py's TOOLS use JSON-Schema-style input_schema (lowercase "type"
    strings, written for Claude/Ollama); Gemini's FunctionDeclaration wants
    types.Schema objects built from its Type enum -- convert recursively."""
    kind = str(schema.get("type", "string")).upper()
    type_enum = getattr(types.Type, kind, types.Type.STRING)
    kwargs: Dict = {"type": type_enum}
    if schema.get("description"):
        kwargs["description"] = schema["description"]
    if "enum" in schema:
        kwargs["enum"] = schema["enum"]
    if kind == "OBJECT" and "properties" in schema:
        kwargs["properties"] = {name: _to_gemini_schema(sub) for name, sub in schema["properties"].items()}
        if schema.get("required"):
            kwargs["required"] = schema["required"]
    if kind == "ARRAY" and "items" in schema:
        kwargs["items"] = _to_gemini_schema(schema["items"])
    return types.Schema(**kwargs)


def _to_gemini_tools(anthropic_tools: List[Dict]) -> List[types.Tool]:
    """One Tool holding all function declarations, as the Gemini API expects
    (a list of separate single-function Tools is also accepted, but this is
    the documented shape)."""
    return [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=_to_gemini_schema(t["input_schema"]),
            )
            for t in anthropic_tools
        ])
    ]


GEMINI_TOOLS = _to_gemini_tools(TOOLS)

_BLOCKED_MESSAGE = (
    "Sorry, I couldn't generate a response to that -- Gemini returned nothing, which usually means its safety "
    "filters blocked the reply. Try rephrasing the question."
)


class GeminiUnavailable(RuntimeError):
    """A Gemini-side failure worded for the chat UI (rate limit / overload), raised
    instead of the SDK's raw error so app.py can show something readable. Confirmed
    live: the free tier enforces at least two separate 429 quotas on this model --
    a per-minute one (5 requests) and a per-day one (20 requests) -- with the same
    RESOURCE_EXHAUSTED status either way, distinguishable only by the quotaId
    buried in the error body. Conflating them gave a wrong "try again in a moment"
    message for a quota that won't clear for hours."""


def _quota_violation(exc: genai_errors.APIError) -> Optional[Dict]:
    """The QuotaFailure violation (quotaId, quotaValue, ...) inside a 429's error
    body, if the SDK gave us one -- exc.details is the raw decoded JSON response."""
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return None
    for item in details.get("error", {}).get("details", []):
        violations = item.get("violations")
        if violations:
            return violations[0]
    return None


def _retry_delay_seconds(exc: genai_errors.APIError) -> Optional[str]:
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return None
    for item in details.get("error", {}).get("details", []):
        if "retryDelay" in item:
            return item["retryDelay"]
    return None


def _friendly_gemini_error(exc: genai_errors.APIError) -> GeminiUnavailable:
    status = getattr(exc, "status", None) or getattr(exc, "code", None)
    if status in (429, "RESOURCE_EXHAUSTED"):
        violation = _quota_violation(exc) or {}
        quota_id = violation.get("quotaId", "")
        limit = violation.get("quotaValue")
        model = (violation.get("quotaDimensions") or {}).get("model", "this model")
        if "PerDay" in quota_id:
            plan = f"{limit} requests a day" if limit else "a small number of requests a day"
            return GeminiUnavailable(
                f"Gemini's free tier has used up its daily quota for {model} ({plan}). It resets after a fixed "
                "daily window (not a short wait) -- try again tomorrow, or switch to another backend for now."
            )
        if "PerMinute" in quota_id or not quota_id:
            plan = f"{limit} requests a minute" if limit else "only a few requests a minute"
            wait = _retry_delay_seconds(exc)
            when = f"in about {wait}" if wait else "in a moment"
            return GeminiUnavailable(
                f"Gemini's rate limit was hit (the free tier allows {plan} for {model}). Try again {when}, or "
                "switch to another backend for now."
            )
        return GeminiUnavailable(f"Gemini's usage quota was hit ({quota_id or 'RESOURCE_EXHAUSTED'}). Try again "
                                 "later, or switch to another backend for now.")
    if status in (503, "UNAVAILABLE"):
        return GeminiUnavailable("Gemini is temporarily overloaded on Google's side. Try again in a moment.")
    return GeminiUnavailable(f"Gemini request failed: {exc}")


class GeminiRAGChatbot:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL, top_k: int = 3):
        self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
        self.model = model
        self.top_k = top_k
        self.retriever = Retriever()
        self.history: List[types.Content] = []
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

    def _run_tool_loop(self, system_prompt: str) -> str:
        # Gemini, like Claude, sometimes writes the real answer in the SAME turn as a
        # function_call (e.g. states the calculator's numbers, then also calls
        # render_chart) -- collect text from every turn, not just the final one, or
        # that answer gets silently dropped. See rag_chatbot.py's identical fix, found
        # live against the real Claude API on this exact question shape.
        collected_text: List[str] = []
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=GEMINI_TOOLS,
            # Raised from 500 -- that was cutting real replies off mid-sentence, since
            # a tool call's JSON and the system prompt's own growing ground rules
            # (citation formatting, BLEND_ADDENDUM's flag, ...) share this same budget
            # with the answer text. See rag_chatbot.py's identical change -- 1200 still
            # wasn't enough there for a genuinely multi-part question, confirmed live.
            max_output_tokens=2048,
            # gemini-3.8-flash is a "thinking" model: by default it spends part of
            # max_output_tokens on a hidden reasoning pass before the visible answer,
            # which was silently truncating real answers to a few words once the
            # system prompt was long (confirmed live: 367 of a 500-token budget went
            # to thinking on a real request). The system prompt already asks for a
            # short, direct answer, so thinking adds latency and cost without buying
            # much here -- disable it and keep the whole budget for the answer.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        while True:
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.history,
                    config=config,
                )
            except genai_errors.APIError as exc:
                raise _friendly_gemini_error(exc) from exc
            candidate = response.candidates[0] if response.candidates else None
            parts = candidate.content.parts if candidate and candidate.content else None
            if not parts:
                return _BLOCKED_MESSAGE

            calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
            collected_text.extend(p.text for p in parts if getattr(p, "text", None))

            if not calls:
                answer = "\n\n".join(t.strip() for t in collected_text if t.strip())
                self.history.append(candidate.content)
                return answer

            self.history.append(candidate.content)

            result_parts = []
            for call in calls:
                result = call_tool(call.name, dict(call.args or {}))
                if call.name == "render_chart" and isinstance(result, dict) and "error" not in result:
                    self.last_chart = result
                elif call.name == "show_payment_button" and isinstance(result, dict) and "error" not in result:
                    self.last_payment_button = result
                elif call.name == "show_invoice_button" and isinstance(result, dict) and "error" not in result:
                    self.last_invoice_button = result
                elif call.name == "show_quote_button" and isinstance(result, dict) and "error" not in result:
                    self.last_quote_button = result
                elif call.name == "show_schedule_payments_button" and isinstance(result, dict) and "error" not in result:
                    self.last_schedule_payments_button = result
                elif call.name == "show_chase_payment_button" and isinstance(result, dict) and "error" not in result:
                    self.last_chase_payment_button = result
                elif call.name == "show_refund_button" and isinstance(result, dict) and "error" not in result:
                    self.last_refund_button = result
                elif call.name == "show_talk_to_team_button" and isinstance(result, dict) and "error" not in result:
                    self.last_talk_to_team_button = result
                elif call.name == "show_set_reminder_button" and isinstance(result, dict) and "error" not in result:
                    self.last_set_reminder_button = result
                elif call.name == "show_register_business_button" and isinstance(result, dict) and "error" not in result:
                    self.last_register_business_button = result
                result_parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))
            self.history.append(types.Content(role="user", parts=result_parts))

    def _retrieval_text(self, query: str) -> str:
        """What to actually search the (English-only) knowledge base with -- see
        rag_chatbot.py's identical method for why this is needed (TF-IDF finds
        nothing for an Arabic query against an English-authored KB)."""
        if not ARABIC_TEXT_RE.search(query):
            return query
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=query)])],
                config=types.GenerateContentConfig(
                    system_instruction=TRANSLATE_FOR_RETRIEVAL_PROMPT,
                    max_output_tokens=200,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            candidate = resp.candidates[0] if resp.candidates else None
            parts = candidate.content.parts if candidate and candidate.content else None
            translated = "".join(p.text for p in parts if getattr(p, "text", None)).strip() if parts else ""
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
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(passages=_format_passages(passages)) + BLEND_ADDENDUM
        if self.documents:
            system_prompt += self.documents.prompt_section(query, self.doc_budget)

        self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=query)]))
        return self._run_tool_loop(system_prompt)

    def reset(self) -> None:
        self.history = []
        self._last_query = None
