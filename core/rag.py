"""Recuperador RAG sobre corpus/*.md. MVP: TF-IDF. Mejora sugerida: embeddings + FAISS/Chroma."""

import glob, os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class Retriever:
    def __init__(self, folder=os.path.join(os.path.dirname(__file__), "..", "corpus")):
        self.chunks = []
        for f in sorted(glob.glob(os.path.join(folder, "*.md"))):
            for para in open(f, encoding="utf-8").read().split("\n\n"):
                if len(para.strip()) > 40:
                    self.chunks.append((os.path.basename(f), para.strip()))
        self.vec = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2))
        self.M = self.vec.fit_transform([c[1] for c in self.chunks])

    def search(self, q, k=3):
        s = cosine_similarity(self.vec.transform([q]), self.M)[0]
        return [
            {
                "source": self.chunks[i][0],
                "text": self.chunks[i][1],
                "score": round(float(s[i]), 3),
            }
            for i in s.argsort()[::-1][:k]
            if s[i] > 0
        ]
