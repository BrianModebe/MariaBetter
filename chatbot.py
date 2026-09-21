"""
FinanceChatbot: a lightweight, retrieval-based chatbot for general
finance education Q&A.

How it works
------------
Each knowledge-base entry's question + alternative phrasings are joined
into one "document". All documents are vectorized with TF-IDF
(scikit-learn), and a user's query is matched against them using cosine
similarity. The best-matching entry's answer is returned if the
similarity score clears a confidence threshold; otherwise the bot
admits it doesn't have a good answer.

This is intentionally simple (no external API calls, no internet
access needed) so it runs anywhere Python + scikit-learn is available.
"""

from dataclasses import dataclass
from typing import List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from knowledge_base import KNOWLEDGE_BASE


@dataclass
class Match:
    question: str
    answer: str
    topic: str
    score: float


class FinanceChatbot:
    def __init__(self, knowledge_base: Optional[List[dict]] = None, confidence_threshold: float = 0.20):
        self.kb = knowledge_base if knowledge_base is not None else KNOWLEDGE_BASE
        self.confidence_threshold = confidence_threshold
        self._build_index()

    def _build_index(self) -> None:
        # Build one searchable text blob per KB entry: canonical question +
        # alt phrasings, so alternate ways of asking still match well.
        self._documents = [
            " ".join([entry["question"]] + entry.get("alt", []))
            for entry in self.kb
        ]
        self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self._matrix = self._vectorizer.fit_transform(self._documents)

    def topics(self) -> List[str]:
        seen = []
        for entry in self.kb:
            if entry["topic"] not in seen:
                seen.append(entry["topic"])
        return seen

    def list_questions(self, topic: Optional[str] = None) -> List[str]:
        return [
            entry["question"]
            for entry in self.kb
            if topic is None or entry["topic"].lower() == topic.lower()
        ]

    def ask(self, query: str) -> Match:
        query_vec = self._vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self._matrix)[0]
        best_idx = similarities.argmax()
        best_score = float(similarities[best_idx])
        entry = self.kb[best_idx]

        if best_score < self.confidence_threshold:
            return Match(
                question=query,
                answer=(
                    "I don't have a confident answer for that yet. Try rephrasing, "
                    "or type 'topics' to see what I can help with."
                ),
                topic="Unknown",
                score=best_score,
            )

        return Match(
            question=entry["question"],
            answer=entry["answer"],
            topic=entry["topic"],
            score=best_score,
        )
