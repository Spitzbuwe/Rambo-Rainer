# -*- coding: utf-8 -*-
"""Tests für Phase 23 (PyTorch Relevanz-Modell)."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from ml_model import (
    RelevanceNet,
    load_relevance_model,
    predict_relevance_ml,
    prepare_training_data,
    rule_to_feature_vector,
    train_relevance_model,
)


def test_model_forward_pass():
    model = RelevanceNet()
    x = torch.randn(1, 4)
    y = model(x)
    assert y.shape == (1, 1)
    assert 0.0 <= y.item() <= 1.0


def test_prepare_training_data():
    rules = [
        {
            "keyword_matches": 5,
            "success_count": 10,
            "days_since_last_use": 5,
            "total_uses": 20,
        },
        {
            "keyword_matches": 2,
            "success_count": 0,
            "days_since_last_use": 30,
            "total_uses": 1,
        },
    ]
    features, labels = prepare_training_data(rules)
    assert features.shape == (2, 4)
    assert labels.shape == (2,)
    assert labels[0] == 1.0
    assert labels[1] == 0.0


def test_prepare_training_data_with_explicit_label():
    rows = [
        {"keyword_matches": 1, "success_count": 0, "days_since_last_use": 1, "total_uses": 1, "label": 1.0},
        {"keyword_matches": 2, "success_count": 0, "days_since_last_use": 2, "total_uses": 2, "label": 0.0},
    ]
    _, labels = prepare_training_data(rows)
    assert labels[0] == 1.0
    assert labels[1] == 0.0


def test_train_and_predict(tmp_path):
    rules = [
        {"keyword_matches": 5, "success_count": 10, "days_since_last_use": 5, "total_uses": 20},
        {"keyword_matches": 3, "success_count": 8, "days_since_last_use": 10, "total_uses": 15},
        {"keyword_matches": 1, "success_count": 0, "days_since_last_use": 100, "total_uses": 2},
    ]
    model_path = str(tmp_path / "test_model.pt")
    model, scaler = train_relevance_model(rules, epochs=25, model_path=model_path, verbose=False)
    assert model is not None
    assert scaler is not None
    test_features = [4.0, 8.0, 7.0, 18.0]
    score = predict_relevance_ml(test_features, model, scaler)
    assert score is not None
    assert 0.0 <= score <= 1.0


def test_save_load_roundtrip(tmp_path):
    rules = [
        {"keyword_matches": 5, "success_count": 10, "days_since_last_use": 5, "total_uses": 20},
        {"keyword_matches": 2, "success_count": 0, "days_since_last_use": 30, "total_uses": 5},
    ]
    model_path = str(tmp_path / "m.pt")
    train_relevance_model(rules, epochs=15, model_path=model_path, verbose=False)
    loaded_model, loaded_scaler = load_relevance_model(model_path, log=None)
    assert loaded_model is not None
    assert loaded_scaler is not None
    s = predict_relevance_ml([5.0, 10.0, 5.0, 20.0], loaded_model, loaded_scaler)
    assert s is not None and 0.0 <= s <= 1.0


def test_missing_model_file():
    model, scaler = load_relevance_model("/nonexistent/path/relevance.pt", log=None)
    assert model is None
    assert scaler is None


def test_insufficient_training_data():
    rules = [{"keyword_matches": 1, "success_count": 1, "days_since_last_use": 1, "total_uses": 1}]
    model, scaler = train_relevance_model(rules, epochs=5, model_path=None, verbose=False)
    assert model is None
    assert scaler is None


def test_rule_to_feature_vector_minimal():
    r = {
        "value": "hello world test",
        "usage_count": 3,
        "stored_at": "2026-01-01T00:00:00Z",
    }
    v = rule_to_feature_vector(r, {})
    assert len(v) == 4
    assert all(isinstance(x, float) for x in v)
