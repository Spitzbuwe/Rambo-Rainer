# -*- coding: utf-8 -*-
"""Heuristik vs. ML-Vorhersage (Phase 23, optional)."""

from __future__ import annotations

import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from ml_model import default_model_path, load_relevance_model, predict_relevance_ml, rule_to_feature_vector
from relevance_scorer import RelevanceScorer


def main() -> None:
    data_dir = os.path.join(_BACKEND, "data")
    os.makedirs(data_dir, exist_ok=True)
    path = default_model_path(data_dir)
    scorer = RelevanceScorer()
    model, scaler = load_relevance_model(path, log=print)

    test_rules = [
        {
            "name": "high-success",
            "value": "alpha beta gamma",
            "history": {"success_count": 50, "total_count": 55},
            "usage_count": 55,
            "stored_at": "2026-04-17T12:00:00Z",
        },
        {
            "name": "low-success",
            "value": "foo bar",
            "history": {"success_count": 1, "total_count": 20},
            "usage_count": 10,
            "stored_at": "2025-01-01T12:00:00Z",
        },
        {
            "name": "new-rule",
            "value": "test rule phrase",
            "usage_count": 0,
            "stored_at": "2026-04-18T12:00:00Z",
        },
    ]
    ctx = {"text": "alpha beta test phrase"}

    print("=" * 60)
    print("SCORING: Heuristik vs. ML")
    print("=" * 60)
    for raw in test_rules:
        name = raw["name"]
        rule = {k: v for k, v in raw.items() if k != "name"}
        h = scorer.calculate_heuristics(rule, ctx)
        heur = float(h["confidence_score"])
        feats = rule_to_feature_vector(rule, ctx)
        ml_raw = predict_relevance_ml(feats, model, scaler)
        print(f"\n{name}:")
        print(f"  Heuristik: {heur:.4f}")
        if ml_raw is not None:
            print(f"  ML:        {float(ml_raw):.4f}")
            print(f"  Differenz: {abs(heur - float(ml_raw)):.4f}")
        else:
            print("  ML:        (kein Modell)")


if __name__ == "__main__":
    main()
