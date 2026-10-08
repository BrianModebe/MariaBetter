"""
Loads and normalizes every knowledge-base source into one flat list of
entries, so the RAG retriever doesn't care where content came from.

Sources combined:
  1. knowledge_base.py -> KNOWLEDGE_BASE   (legacy generic entries: budgeting,
     saving, investing basics, credit/debt, insurance, financial statements.
     These concepts are universal and still valid for UAE users.)
  2. knowledge/*.json                      (UAE-wide clusters -- finance plus
     finance-adjacent law -- covering all seven emirates, not just Dubai.
     Existing: income_taxation.json, employment.json, tenancy_real_estate.json,
     uae_statistics.json, banking_credit.json, retirement_pensions.json,
     investing_uae.json, business_freezones.json, immigration_visas.json.)

Every entry, regardless of source, is normalized to:
    {
        "topic":  str,            # cluster / category label
        "question": str,          # canonical question
        "alt": [str, ...],        # alternate phrasings (may be empty)
        "answer": str,
        "source": str | None,     # URL the fact was pulled from (UAE entries)
        "legal_ref": str | None,  # statute/decree/article citation, when the
                                  # fact rests on a specific UAE law -- e.g.
                                  # "Federal Decree-Law No. 33 of 2021, Art. 9".
                                  # Only set when verified against an official
                                  # source; leave null rather than guess a
                                  # citation number.
        "as_of": str | None,      # "YYYY-MM" the fact was last verified
    }
"""

import json
from pathlib import Path
from typing import List, Dict

from knowledge_base import KNOWLEDGE_BASE

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def _normalize(entry: Dict) -> Dict:
    return {
        "topic": entry["topic"],
        "question": entry["question"],
        "alt": entry.get("alt", []),
        "answer": entry["answer"],
        "source": entry.get("source"),
        "legal_ref": entry.get("legal_ref"),
        "as_of": entry.get("as_of"),
    }


def load_knowledge_base() -> List[Dict]:
    entries = [_normalize(e) for e in KNOWLEDGE_BASE]

    if KNOWLEDGE_DIR.exists():
        for path in sorted(KNOWLEDGE_DIR.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                cluster_entries = json.load(f)
            entries.extend(_normalize(e) for e in cluster_entries)

    return entries


if __name__ == "__main__":
    kb = load_knowledge_base()
    print(f"Loaded {len(kb)} knowledge-base entries.")
    topics = sorted({e["topic"] for e in kb})
    for t in topics:
        count = sum(1 for e in kb if e["topic"] == t)
        print(f"  - {t}: {count}")
