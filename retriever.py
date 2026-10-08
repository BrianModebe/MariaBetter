"""
Retriever: given a user query, return the top-k most relevant knowledge-base
entries (not just the single best match, like the old FinanceChatbot did).

Uses TF-IDF + cosine similarity (scikit-learn) for now -- no external
embedding API required, so this works offline with zero new dependencies
and zero cost. If/when the knowledge base grows large (hundreds+ entries)
or matching quality plateaus, swap this for real embeddings (e.g. Voyage AI
embeddings via the Anthropic-recommended provider, or `chromadb`) behind the
same `Retriever.retrieve()` interface -- nothing else in the pipeline needs
to change.
"""

from dataclasses import dataclass
from typing import List, Dict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from knowledge_loader import load_knowledge_base


@dataclass
class Passage:
    entry: Dict
    score: float


class Retriever:
    def __init__(self, knowledge_base: List[Dict] = None):
        self.kb = knowledge_base if knowledge_base is not None else load_knowledge_base()
        self._build_index()

    def _build_index(self) -> None:
        self._documents = [
            " ".join([e["question"]] + e.get("alt", []) + [e["answer"]])
            for e in self.kb
        ]
        self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self._matrix = self._vectorizer.fit_transform(self._documents)

    def retrieve(self, query: str, k: int = 3, min_score: float = 0.05) -> List[Passage]:
        query_vec = self._vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self._matrix)[0]

        ranked_idx = similarities.argsort()[::-1][:k]
        return [
            Passage(entry=self.kb[i], score=float(similarities[i]))
            for i in ranked_idx
            if similarities[i] >= min_score
        ]
