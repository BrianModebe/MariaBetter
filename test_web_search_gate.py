"""web_search is only offered to Claude for live-price questions -- offered on every
question, it sometimes ran an unneeded search after already answering from the
knowledge base, and the duplicated text (plus an apology) reached the user."""

import pytest

from rag_chatbot import _LIVE_PRICE_RE


@pytest.mark.parametrize("query", [
    "What is the gold price in Dubai today?",
    "How much is Emaar stock right now?",
    "What are apartment rents in JVC at the moment?",
    "What's the current share price of ADNOC Gas?",
    "كم سعر الذهب اليوم؟",
    "ما هو سعر سهم إعمار؟",
])
def test_live_price_questions_get_web_search(query):
    assert _LIVE_PRICE_RE.search(query)


@pytest.mark.parametrize("query", [
    "Is Dubai Investment Park a free zone?",
    "Is RAK Maritime City the same as RAKEZ?",
    "Which government body registers a mainland company in Dubai?",
    "Do I need a MOIAT license for manufacturing?",
    "What authority licenses private schools in Dubai?",
    "I want to register a trading company in JAFZA",
])
def test_knowledge_base_questions_do_not(query):
    assert not _LIVE_PRICE_RE.search(query)
