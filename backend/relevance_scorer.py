# -*- coding: utf-8 -*-
"""Heuristische Relevanz-Scores für learned rules (Phase 15)."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Gewichtung (30 + 35 + 15 + 20 = 100 %)
W_KEYWORD = 0.30
W_SUCCESS = 0.35
W_RECENCY = 0.15
W_FREQUENCY = 0.20

DEFAULT_SUCCESS_RATE = 0.5


def _rule_id(rule: dict) -> str:
    fp = str(rule.get("fingerprint") or "").strip()
    if fp:
        return fp
    return str(rule.get("id") or rule.get("rule_id") or "")


def _extract_keywords_from_rule(rule: dict) -> List[str]:
    text = str(rule.get("value") or rule.get("text") or "")
    parts = re.split(r"[\s,;.!?()\[\]{}\"'\\/]+", text.lower())
    return [p for p in parts if len(p) >= 3]


def _context_text(context: dict) -> str:
    if not isinstance(context, dict):
        return ""
    chunks = []
    for key in ("text", "query", "message", "task", "input", "content"):
        v = context.get(key)
        if v is not None:
            chunks.append(str(v))
    kw = context.get("keywords")
    if isinstance(kw, (list, tuple)):
        chunks.extend(str(x) for x in kw)
    return " ".join(chunks).lower()


def _keyword_match_score(rule: dict, context: dict) -> Tuple[float, int]:
    ctx = _context_text(context)
    if not ctx.strip():
        kws = _extract_keywords_from_rule(rule)
        return (0.0, 0) if kws else (0.5, 0)
    kws = _extract_keywords_from_rule(rule)
    if not kws:
        return 0.0, 0
    hits = sum(1 for k in kws if k in ctx)
    ratio = hits / max(len(kws), 1)
    return min(1.0, ratio), hits


def _parse_iso_ts(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _recency_factor(rule: dict) -> float:
    now = datetime.now(timezone.utc)
    candidates = []
    for key in ("stored_at", "last_used", "last_matched_at", "updated_at"):
        dt = _parse_iso_ts(rule.get(key))
        if dt:
            candidates.append(dt)
    if not candidates:
        return 0.5
    newest = max(candidates)
    delta_days = max(0.0, (now - newest).total_seconds() / 86400.0)
    # Neuere Regeln → näher an 1.0; nach ~365 Tage ~ 0.37
    return float(math.exp(-delta_days / 180.0))


def _success_rate(rule: dict) -> float:
    hist = rule.get("history")
    if isinstance(hist, dict):
        total = int(hist.get("total_count") or 0)
        succ = int(hist.get("success_count") or 0)
        if total > 0:
            return max(0.0, min(1.0, succ / total))
    return DEFAULT_SUCCESS_RATE


def _frequency_factor(rule: dict) -> float:
    n = int(rule.get("usage_count") or 0)
    # log-ähnliche Sättigung
    return max(0.0, min(1.0, math.log1p(n) / math.log1p(50)))


class RelevanceScorer:
    """ML-light Heuristiken für Regel-Relevanz."""

    def __init__(
        self,
        w_keyword: float = W_KEYWORD,
        w_success: float = W_SUCCESS,
        w_recency: float = W_RECENCY,
        w_frequency: float = W_FREQUENCY,
    ):
        s = w_keyword + w_success + w_recency + w_frequency
        if s <= 0:
            raise ValueError("weights")
        self.w_keyword = w_keyword / s
        self.w_success = w_success / s
        self.w_recency = w_recency / s
        self.w_frequency = w_frequency / s

    def calculate_heuristics(self, rule: dict, context: dict) -> Dict[str, Any]:
        if not isinstance(rule, dict):
            rule = {}
        if not isinstance(context, dict):
            context = {}
        km, hits = _keyword_match_score(rule, context)
        rec = _recency_factor(rule)
        sr = _success_rate(rule)
        fq = _frequency_factor(rule)
        conf = (
            self.w_keyword * km
            + self.w_success * sr
            + self.w_recency * rec
            + self.w_frequency * fq
        )
        return {
            "keyword_match": round(km, 6),
            "keyword_hits": hits,
            "recency_factor": round(rec, 6),
            "success_rate": round(sr, 6),
            "frequency_factor": round(fq, 6),
            "confidence_score": round(min(1.0, max(0.0, conf)), 6),
        }

    def score_rule(self, rule: dict, context: dict) -> float:
        h = self.calculate_heuristics(rule, context)
        return float(h["confidence_score"])

    def score_batch(self, rules: List[dict], context: dict) -> Dict[str, float]:
        out: Dict[str, float] = {}
        if not isinstance(rules, list):
            return out
        for r in rules:
            if not isinstance(r, dict):
                continue
            rid = _rule_id(r)
            if not rid:
                continue
            out[rid] = self.score_rule(r, context)
        return out
