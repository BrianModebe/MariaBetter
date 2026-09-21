# Finance Education Chatbot

A lightweight, retrieval-based chatbot that answers general personal-finance
and investing questions (budgeting, compound interest, stocks/bonds/ETFs,
credit, retirement accounts, and more). No API keys or internet access
required — it runs entirely offline using TF-IDF + cosine similarity
(scikit-learn) to match your question against a curated knowledge base.

## Setup

```bash
pip install -r requirements.txt
python main.py
```

## Usage

```
Finance Education Chatbot — type 'help' for commands, 'quit' to exit.

> what is compound interest?

[Saving & Interest] Compound interest is interest calculated on both the
original amount (principal) and the interest that has already
accumulated...

> topics
  - Budgeting
  - Saving & Interest
  - Investing
  - Credit & Debt
  - Retirement & Taxes
  - Insurance & Risk
  - Financial Statements

> calc
-- Compound Interest / Savings Growth Calculator --
Starting amount ($): 1000
Monthly contribution ($): 200
Expected annual return (%): 7
Number of years: 10
...
```

## Project structure

```
finance_chatbot/
├── knowledge_base.py   # Q&A entries (question, alt phrasings, answer, topic)
├── chatbot.py           # FinanceChatbot class (TF-IDF matching)
├── main.py              # CLI entry point
├── requirements.txt
└── README.md
```

## Extending it

- Add more Q&A pairs to `KNOWLEDGE_BASE` in `knowledge_base.py` — the index
  rebuilds automatically, no other code changes needed.
- Lower/raise `confidence_threshold` in `FinanceChatbot.__init__` to make
  matching more lenient or stricter.
- Swap in a real-time market data API (e.g. for live stock quotes) by adding
  a new module and a new command in `main.py` — the current bot deliberately
  sticks to static educational content so it needs no API key to run.

## Disclaimer

This chatbot provides general financial education only — it is not
personalized financial, investment, or tax advice.
