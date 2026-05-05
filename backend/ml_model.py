# -*- coding: utf-8 -*-
"""PyTorch Relevanz-Modell (Phase 23): trainierbar, optional statt reiner Heuristik."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler

from relevance_scorer import _keyword_match_score, _parse_iso_ts, _success_rate

LogFn = Callable[[str], None]


class RelevanceNet(nn.Module):
    """Kleines MLP: 4 Features → Score in [0, 1]."""

    def __init__(self, input_size: int = 4) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def _days_since_last_use(rule: dict) -> float:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    candidates = []
    for key in ("stored_at", "last_used", "last_matched_at", "updated_at"):
        dt = _parse_iso_ts(rule.get(key))
        if dt:
            candidates.append(dt)
    if not candidates:
        return 365.0
    newest = max(candidates)
    return max(0.0, (now - newest).total_seconds() / 86400.0)


def rule_to_feature_vector(rule: dict, context: dict) -> List[float]:
    """4 Merkmale konsistent zu Training (keyword-Treffer, Erfolg, Alter, Nutzung)."""
    if not isinstance(rule, dict):
        rule = {}
    if not isinstance(context, dict):
        context = {}
    _, hits = _keyword_match_score(rule, context)
    hist = rule.get("history") if isinstance(rule.get("history"), dict) else {}
    succ = float(int(hist.get("success_count") or 0))
    if succ <= 0:
        sr = _success_rate(rule)
        if sr > 0:
            succ = max(1.0, round(sr * 25.0, 3))
    days = float(_days_since_last_use(rule))
    uses = float(max(1, int(rule.get("usage_count") or 0)))
    return [float(hits), succ, days, uses]


def rules_to_training_rows(rules: List[dict], context: dict) -> List[Dict[str, float]]:
    """Rohregeln → Zeilen mit Features + implizitem Label (success_count/usage)."""
    rows: List[Dict[str, float]] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        feats = rule_to_feature_vector(r, context)
        hist = r.get("history") if isinstance(r.get("history"), dict) else {}
        succ = int(hist.get("success_count") or 0)
        uses = int(r.get("usage_count") or 0)
        label = 1.0 if succ > 0 or uses > 0 else 0.0
        rows.append(
            {
                "keyword_matches": feats[0],
                "success_count": feats[1],
                "days_since_last_use": feats[2],
                "total_uses": feats[3],
                "label": label,
            }
        )
    return rows


def prepare_training_data(rules_data: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
    features: List[List[float]] = []
    labels: List[float] = []
    for rule in rules_data:
        f = [
            float(rule.get("keyword_matches", 0)),
            float(rule.get("success_count", 0)),
            float(rule.get("days_since_last_use", 365)),
            float(rule.get("total_uses", 1) or 1),
        ]
        features.append(f)
        if "label" in rule:
            labels.append(float(rule["label"]))
        else:
            labels.append(1.0 if float(rule.get("success_count", 0)) > 0 else 0.0)
    return np.array(features, dtype=np.float32), np.array(labels, dtype=np.float32)


def _scaler_to_dict(scaler: MinMaxScaler) -> Dict[str, List[float]]:
    return {
        "data_min": scaler.data_min_.tolist(),
        "data_max": scaler.data_max_.tolist(),
    }


def _scaler_from_dict(d: Dict[str, List[float]]) -> MinMaxScaler:
    s = MinMaxScaler()
    dm = np.array(d["data_min"], dtype=np.float64)
    dmx = np.array(d["data_max"], dtype=np.float64)
    s.fit(np.vstack([dm, dmx]))
    return s


def train_relevance_model(
    rules_data: List[Dict[str, Any]],
    epochs: int = 50,
    model_path: Optional[str] = None,
    verbose: bool = True,
    log: Optional[LogFn] = None,
) -> Tuple[Optional[RelevanceNet], Optional[MinMaxScaler]]:
    def _log(msg: str) -> None:
        if verbose and log:
            log(msg)
        elif verbose:
            print(msg)

    if not rules_data or len(rules_data) < 2:
        _log("[ML] Zu wenig Trainingsdaten (min. 2 Einträge).")
        return None, None

    features, labels = prepare_training_data(rules_data)
    if len(np.unique(labels)) < 2:
        _log("[ML] Hinweis: nur eine Label-Klasse — Training trotzdem (schwache Diskriminanz).")

    scaler = MinMaxScaler()
    features_scaled = scaler.fit_transform(features)
    features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
    labels_tensor = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)

    model = RelevanceNet(input_size=4)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.BCELoss()

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        outputs = model(features_tensor)
        loss = criterion(outputs, labels_tensor)
        if not math.isfinite(loss.item()):
            _log("[ML] Abbruch: Loss nicht endlich.")
            return None, None
        loss.backward()
        optimizer.step()
        if verbose and (epoch + 1) % max(1, epochs // 5) == 0:
            _log(f"[ML] Epoch {epoch + 1}/{epochs}, Loss: {loss.item():.4f}")

    model.eval()
    if model_path:
        p = Path(model_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state": model.state_dict(),
                "scaler": _scaler_to_dict(scaler),
                "training_samples": len(rules_data),
            },
            p,
        )
        _log(f"[ML] Modell gespeichert: {p}")

    return model, scaler


def load_relevance_model(
    model_path: str,
    log: Optional[LogFn] = None,
) -> Tuple[Optional[RelevanceNet], Optional[MinMaxScaler]]:
    def _log(msg: str) -> None:
        if log:
            log(msg)

    if not Path(model_path).is_file():
        _log(f"[ML] Kein Modell unter {model_path}")
        return None, None
    try:
        ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
        model = RelevanceNet()
        model.load_state_dict(ckpt["model_state"])
        model.eval()
        scaler = _scaler_from_dict(ckpt["scaler"])
        n = ckpt.get("training_samples", "?")
        _log(f"[ML] Modell geladen (Samples: {n})")
        return model, scaler
    except Exception as exc:
        _log(f"[ML] Laden fehlgeschlagen: {exc}")
        return None, None


def predict_relevance_ml(
    rule_features: List[float],
    model: Optional[RelevanceNet],
    scaler: Optional[MinMaxScaler],
) -> Optional[float]:
    if model is None or scaler is None:
        return None
    try:
        features_array = np.array(rule_features, dtype=np.float32).reshape(1, -1)
        features_scaled = scaler.transform(features_array)
        features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
        with torch.no_grad():
            score = model(features_tensor).item()
        return max(0.0, min(1.0, float(score)))
    except Exception:
        return None


def default_model_path(backend_data_dir: str) -> str:
    return str(Path(backend_data_dir) / "relevance_model.pt")
