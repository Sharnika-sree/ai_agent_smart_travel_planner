"""
Lightweight Local RAG Knowledge Retrieval System.
Uses TF-IDF Vectorization and Cosine Similarity over local travel policy documents.
Provides strict grounding for visa policies and entry rules with traceable source citations.
"""

import os
from pathlib import Path
from typing import List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config import KNOWLEDGE_DIR

class LocalRAG:
    def __init__(self, knowledge_dir: Path = KNOWLEDGE_DIR):
        self.knowledge_dir = knowledge_dir
        self.chunks: List[Dict[str, Any]] = []
        self.vectorizer: TfidfVectorizer = None
        self.tfidf_matrix = None
        self._index_documents()

    def _index_documents(self):
        """
        Reads all text files in the knowledge directory, splits them into logical
        chunks (sections/paragraphs), and builds a TF-IDF matrix.
        """
        self.chunks = []
        if not self.knowledge_dir.exists():
            return

        for filepath in self.knowledge_dir.glob("*.txt"):
            doc_name = filepath.name
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Split by double newline into cohesive sections
                raw_paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                for idx, para in enumerate(raw_paragraphs):
                    if len(para) < 25:
                        continue
                    self.chunks.append({
                        "doc_name": doc_name,
                        "chunk_id": f"{doc_name}-chunk-{idx}",
                        "text": para
                    })
            except Exception as e:
                print(f"Error indexing {filepath}: {e}")

        if self.chunks:
            corpus = [c["text"] for c in self.chunks]
            self.vectorizer = TfidfVectorizer(stop_words="english")
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def retrieve(self, query: str, top_k: int = 3, threshold: float = 0.05) -> List[Dict[str, Any]]:
        """
        Retrieves top-k most relevant chunks matching the query.
        Returns list of dicts with text, doc_name, chunk_id, and similarity score.
        """
        if not self.chunks or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # Rank indices
        ranked_indices = scores.argsort()[::-1]

        results = []
        for idx in ranked_indices[:top_k]:
            score = float(scores[idx])
            if score >= threshold:
                item = dict(self.chunks[idx])
                item["score"] = round(score, 4)
                item["source"] = f"Knowledge Base Document: {item['doc_name']}"
                results.append(item)

        # If strict threshold filtered everything out, return top 1 with lower threshold if score > 0
        if not results and ranked_indices.size > 0 and scores[ranked_indices[0]] > 0:
            best_idx = ranked_indices[0]
            item = dict(self.chunks[best_idx])
            item["score"] = round(float(scores[best_idx]), 4)
            item["source"] = f"Knowledge Base Document: {item['doc_name']}"
            results.append(item)

        return results

    def get_visa_summary(self, destination: str, passport_country: str = "India") -> Dict[str, Any]:
        """
        High-level retrieval helper specifically for visa inquiries.
        Returns retrieved chunks, formatted summary, source list, and mandatory disclaimer.
        Prioritizes documents specifically matching the destination.
        """
        dest_clean = destination.strip().lower()
        
        # Check if we have an exact or close document match for this destination
        matching_chunks = [
            c for c in self.chunks 
            if dest_clean in c["doc_name"].lower() or any(w in c["doc_name"].lower() for w in dest_clean.split())
        ]

        if matching_chunks:
            # Use chunks from the destination-specific document
            chunks = matching_chunks[:3]
        else:
            query = f"{destination} visa entry requirements arrival card {passport_country} passport"
            chunks = self.retrieve(query, top_k=3)
            if not chunks:
                chunks = self.retrieve(f"{destination} entry travel", top_k=2)

        sources = list(dict.fromkeys([c["doc_name"] for c in chunks]))
        
        disclaimer = (
            "IMPORTANT VISA NOTICE: Visa rules, exemptions, and entry procedures can change "
            "frequently without notice. Always verify your eligibility with the official embassy "
            "or immigration portal of your destination country prior to booking or traveling."
        )

        if not chunks:
            summary = (
                f"No specific local travel policy document was found in the knowledge base for {destination}. "
                f"Please consult the official embassy or consulate of {destination}."
            )
            return {
                "summary": summary,
                "chunks": [],
                "sources": [],
                "disclaimer": disclaimer,
                "has_grounded_data": False
            }

        text_content = "\n\n".join([f"[{c['doc_name']}]:\n{c['text']}" for c in chunks])
        return {
            "summary": text_content,
            "chunks": chunks,
            "sources": sources,
            "disclaimer": disclaimer,
            "has_grounded_data": True
        }

# Global singleton instance
rag_system = LocalRAG()

def query_rag(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    return rag_system.retrieve(query, top_k=top_k)

def get_visa_info(destination: str, passport_country: str = "India") -> Dict[str, Any]:
    return rag_system.get_visa_summary(destination, passport_country)
