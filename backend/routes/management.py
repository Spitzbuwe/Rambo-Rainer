# -*- coding: utf-8 -*-
"""Management-API: Regeln gerankt nach Relevanz (Phase 15)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from flask import Blueprint, jsonify, request

from ml_model import predict_relevance_ml, rule_to_feature_vector
from relevance_scorer import RelevanceScorer


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_context_arg() -> dict:
    raw = request.args.get("context")
    if not raw:
        return {}
    try:
        c = json.loads(raw)
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}


def create_management_blueprint(
    admin_required,
    get_learned_rules: Callable[[], List[dict]],
    scorer: RelevanceScorer,
    ml_state: Optional[Dict[str, Any]] = None,
) -> Blueprint:
    bp = Blueprint("management", __name__, url_prefix="/api/management")

    @bp.route("/rules/ranked", methods=["GET"], strict_slashes=False)
    @admin_required
    def rules_ranked():
        ctx = _parse_context_arg()
        rules = [r for r in get_learned_rules() if isinstance(r, dict)]
        ms = ml_state or {}
        use_ml = bool(
            ms.get("use_ml")
            and ms.get("model") is not None
            and ms.get("scaler") is not None
        )
        batch: Dict[str, float] = {}
        for r in rules:
            rid = str(r.get("fingerprint") or r.get("id") or "").strip()
            if not rid:
                continue
            if use_ml:
                feats = rule_to_feature_vector(r, ctx)
                pr = predict_relevance_ml(feats, ms.get("model"), ms.get("scaler"))
                batch[rid] = float(pr) if pr is not None else scorer.score_rule(r, ctx)
            else:
                batch[rid] = scorer.score_rule(r, ctx)
        rows = []
        for r in rules:
            rid = str(r.get("fingerprint") or r.get("id") or "").strip()
            if not rid:
                continue
            sc = float(batch.get(rid, 0.0))
            h = scorer.calculate_heuristics(r, ctx)
            rows.append(
                {
                    "rule_id": rid,
                    "score": round(sc, 6),
                    "preview": str(r.get("value") or "")[:200],
                    "heuristics": h,
                    "scoring_mode": "ml" if use_ml else "heuristic",
                }
            )
        rows.sort(key=lambda x: x["score"], reverse=True)
        return jsonify({"success": True, "count": len(rows), "ranked": rows, "timestamp": _iso()}), 200

    @bp.route("/rules/<rule_id>/scoring-details", methods=["GET"], strict_slashes=False)
    @admin_required
    def scoring_details(rule_id: str):
        ctx = _parse_context_arg()
        rid = str(rule_id or "").strip()
        if not rid:
            return jsonify({"success": False, "error": "rule_id erforderlich"}), 400
        rule = None
        for r in get_learned_rules():
            if isinstance(r, dict) and str(r.get("fingerprint") or r.get("id") or "").strip() == rid:
                rule = r
                break
        if rule is None:
            return jsonify({"success": False, "error": "Regel nicht gefunden"}), 404
        h = scorer.calculate_heuristics(rule, ctx)
        return jsonify({"success": True, "rule_id": rid, "heuristics": h, "timestamp": _iso()}), 200

    return bp
