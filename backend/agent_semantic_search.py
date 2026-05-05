"""
Semantische Suche — In-Memory-TF-IDF; optional Embeddings (sentence-transformers).
"""
from __future__ import annotations

import logging
import math
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _l2_normalize(vec: dict[str, float]) -> dict[str, float]:
    s = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / s for k, v in vec.items()}


def _tf_idf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    if not tokens:
        return {}
    tf: dict[str, int] = {}
    for w in tokens:
        tf[w] = tf.get(w, 0) + 1
    mx = max(tf.values()) or 1
    raw = {w: (c / mx) * idf.get(w, 1.0) for w, c in tf.items()}
    return _l2_normalize(raw)


def _cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    return float(sum(a[k] * b[k] for k in set(a) & set(b)))


def _build_idf(tokenized_docs: list[list[str]]) -> dict[str, float]:
    n = len(tokenized_docs) or 1
    df: dict[str, int] = {}
    for toks in tokenized_docs:
        for w in set(toks):
            df[w] = df.get(w, 0) + 1
    return {w: math.log((n + 1) / (c + 1)) + 1.0 for w, c in df.items()}


class SemanticSearchIndex:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self._chunks: list[dict[str, Any]] = []
        self._tokenized: list[list[str]] = []
        self._idf: dict[str, float] = {}
        self._tfidf_vecs: list[dict[str, float]] = []
        self._st_model: Any = None
        self._st_matrix: Any = None

    def clear(self) -> None:
        self._chunks.clear()
        self._tokenized.clear()
        self._idf.clear()
        self._tfidf_vecs.clear()
        self._st_model = None
        self._st_matrix = None

    def index_project(
        self,
        globs: tuple[str, ...] = ("**/*.py", "**/*.md"),
        max_chunks: int = 500,
        chunk_size: int = 1200,
    ) -> dict[str, Any]:
        self.clear()
        n = 0
        for g in globs:
            for p in self.project_root.glob(g):
                if not p.is_file() or ".git" in p.parts:
                    continue
                if n >= max_chunks:
                    break
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                rel = str(p.relative_to(self.project_root)).replace("\\", "/")
                for i in range(0, len(text), chunk_size):
                    chunk = text[i : i + chunk_size].strip()
                    if len(chunk) < 40:
                        continue
                    toks = _TOKEN.findall(chunk.lower())
                    self._chunks.append({"path": rel, "offset": i, "text": chunk})
                    self._tokenized.append(toks)
                    n += 1
                    if n >= max_chunks:
                        break
        self._rebuild_tfidf()
        return {"chunks": len(self._chunks)}

    def _rebuild_tfidf(self) -> None:
        self._idf = _build_idf(self._tokenized)
        self._tfidf_vecs = [_tf_idf_vector(t, self._idf) for t in self._tokenized]

    @staticmethod
    def semantic_similarity_score(text_a: str, text_b: str) -> float:
        ta = _TOKEN.findall((text_a or "").lower())
        tb = _TOKEN.findall((text_b or "").lower())
        idf = _build_idf([ta, tb])
        va = _tf_idf_vector(ta, idf)
        vb = _tf_idf_vector(tb, idf)
        return round(_cosine_sparse(va, vb), 6)

    def _st_disabled(self) -> bool:
        return os.getenv("RAINER_AGENT_DISABLE_ST", "").strip().lower() in ("1", "true", "yes", "on")

    def _try_build_st(self) -> bool:
        if self._st_disabled() or not self._chunks:
            return False
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
            texts = [c["text"] for c in self._chunks]
            self._st_matrix = self._st_model.encode(texts, convert_to_numpy=True)
            return True
        except Exception as e:
            logger.debug("sentence-transformers unavailable: %s", e)
            self._st_model = None
            self._st_matrix = None
            return False

    def _search_tfidf(self, query: str, top_k: int) -> list[dict[str, Any]]:
        qt = _TOKEN.findall(query.lower())
        qv = _tf_idf_vector(qt, self._idf)
        scored: list[tuple[float, int]] = []
        for i, dv in enumerate(self._tfidf_vecs):
            scored.append((_cosine_sparse(qv, dv), i))
        scored.sort(key=lambda x: -x[0])
        out: list[dict[str, Any]] = []
        for sc, idx in scored[:top_k]:
            c = self._chunks[idx]
            out.append(
                {
                    "path": c["path"],
                    "offset": c["offset"],
                    "score": round(sc, 6),
                    "snippet": c["text"][:220],
                }
            )
        return out

    def search(self, query: str, top_k: int = 8) -> list[dict[str, Any]]:
        top_k = max(1, top_k)
        if not self._chunks:
            return []
        if not self._st_disabled() and self._st_matrix is None:
            self._try_build_st()
        if self._st_matrix is not None and self._st_model is not None:
            import numpy as np

            q = self._st_model.encode(query, convert_to_numpy=True)
            mat = self._st_matrix
            denom = np.linalg.norm(mat, axis=1) * (np.linalg.norm(q) + 1e-9)
            sims = (mat @ q) / (denom + 1e-9)
            order = np.argsort(-sims)[:top_k]
            out: list[dict[str, Any]] = []
            for idx in order:
                i = int(idx)
                c = self._chunks[i]
                out.append(
                    {
                        "path": c["path"],
                        "offset": c["offset"],
                        "score": round(float(sims[i]), 6),
                        "snippet": c["text"][:220],
                    }
                )
            return out
        if not self._tfidf_vecs:
            self._rebuild_tfidf()
        return self._search_tfidf(query, top_k)

    def cross_project_search(
        self,
        roots: list[Path | str],
        query: str,
        top_k: int = 6,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for r in roots:
            sub = SemanticSearchIndex(r)
            sub.index_project()
            for hit in sub.search(query, top_k=top_k):
                hit = dict(hit)
                hit["project"] = str(Path(r).resolve())
                merged.append(hit)
        merged.sort(key=lambda x: -float(x.get("score", 0.0)))
        return merged[:top_k]

    def health(self) -> dict[str, Any]:
        return {"module": "agent_semantic_search", "class": "SemanticSearchIndex", "ok": True}

    def describe(self) -> str:
        return "SemanticSearchIndex"


def get_instance(project_root: Path | str | None = None) -> SemanticSearchIndex:
    return SemanticSearchIndex(project_root)


__all__ = ["SemanticSearchIndex", "get_instance"]
