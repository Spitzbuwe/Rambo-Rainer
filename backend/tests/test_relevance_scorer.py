# -*- coding: utf-8 -*-
"""Unit-Tests RelevanceScorer (Phase 15)."""

from __future__ import annotations

import pytest

from relevance_scorer import (
    DEFAULT_SUCCESS_RATE,
    RelevanceScorer,
    W_FREQUENCY,
    W_KEYWORD,
    W_RECENCY,
    W_SUCCESS,
)


def _rule(**kw):
    base = {
        "fingerprint": "fp1",
        "value": "default rule text",
        "stored_at": "2026-06-01T00:00:00Z",
        "usage_count": 5,
        "history": {"success_count": 5, "total_count": 10},
    }
    base.update(kw)
    return base


def test_score_rule_perfect_keyword_match_near_one():
    s = RelevanceScorer()
    r = _rule(value="python flask api", fingerprint="a")
    ctx = {"text": "python flask api tutorial"}
    sc = s.score_rule(r, ctx)
    assert sc >= 0.70


def test_score_rule_no_match_low():
    s = RelevanceScorer()
    r = _rule(value="zzzqqqxxx unique", fingerprint="b")
    ctx = {"text": "something completely different"}
    sc = s.score_rule(r, ctx)
    assert sc < 0.45


def test_recency_newer_higher():
    s = RelevanceScorer()
    old = _rule(stored_at="2020-01-01T00:00:00Z", value="x", fingerprint="o")
    new = _rule(stored_at="2026-12-01T00:00:00Z", value="x", fingerprint="n")
    ctx = {}
    assert s.score_rule(new, ctx) > s.score_rule(old, ctx)


def test_success_rate_ordering():
    s = RelevanceScorer()
    hi = _rule(history={"success_count": 10, "total_count": 10}, value="same", fingerprint="h1")
    mid = _rule(history={"success_count": 5, "total_count": 10}, value="same", fingerprint="h2")
    lo = _rule(history={"success_count": 0, "total_count": 10}, value="same", fingerprint="h3")
    ctx = {"text": "same"}
    assert s.score_rule(hi, ctx) > s.score_rule(mid, ctx) > s.score_rule(lo, ctx)


def test_frequency_higher_usage():
    s = RelevanceScorer()
    hi = _rule(usage_count=40, value="term", fingerprint="f1")
    lo = _rule(usage_count=0, value="term", fingerprint="f2")
    ctx = {"text": "term"}
    assert s.score_rule(hi, ctx) > s.score_rule(lo, ctx)


def test_keyword_multiple_tokens():
    s = RelevanceScorer()
    r = _rule(value="alpha beta gamma delta", fingerprint="m")
    ctx = {"keywords": ["alpha", "gamma"]}
    h = s.calculate_heuristics(r, ctx)
    assert h["keyword_hits"] >= 2
    assert h["keyword_match"] > 0.4


def test_score_batch_sorting():
    s = RelevanceScorer()
    rules = [
        _rule(value="foo", fingerprint="low", history={"success_count": 0, "total_count": 10}),
        _rule(value="foo bar excellent", fingerprint="high", history={"success_count": 10, "total_count": 10}),
    ]
    ctx = {"text": "foo bar excellent"}
    batch = s.score_batch(rules, ctx)
    assert batch["high"] > batch["low"]


def test_weights_sum_normalized():
    raw = W_KEYWORD + W_SUCCESS + W_RECENCY + W_FREQUENCY
    assert abs(raw - 1.0) < 1e-9
    s = RelevanceScorer()
    assert abs(s.w_keyword + s.w_success + s.w_recency + s.w_frequency - 1.0) < 1e-9


def test_fallback_no_history_uses_half():
    s = RelevanceScorer()
    r = _rule()
    del r["history"]
    h = s.calculate_heuristics(r, {})
    assert h["success_rate"] == DEFAULT_SUCCESS_RATE


def test_empty_context_and_rules():
    s = RelevanceScorer()
    assert s.score_batch([], {}) == {}
    assert s.score_rule(_rule(), {}) >= 0.0
