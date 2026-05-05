# -*- coding: utf-8 -*-
"""Neue Routen Phasen 15–17: Relevanz, Remote-Sync, DB."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Callable, List

from flask import jsonify, request

from db_adapter import DatabaseAdapter, get_database_adapter
from migrate import run_migrate
from ml_model import default_model_path, load_relevance_model, rules_to_training_rows, train_relevance_model
from relevance_scorer import RelevanceScorer
from remote_sync import RemoteSyncManager
from routes.management import create_management_blueprint


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def setup_phase_services(project_root: str, log_fn) -> dict:
    """Initialisiert Scorer, RemoteSync, DB-Adapter; loggt Schritte."""
    backend_dir = os.path.join(project_root, "backend")
    data_dir = os.path.join(backend_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "rambo_rainer.db")
    scorer = RelevanceScorer()
    token = os.environ.get("RAMBO_ADMIN_TOKEN", "") or ""
    sync = RemoteSyncManager(data_dir, admin_token=token)
    state_path = os.path.join(project_root, "data", "state.json")
    adapter = get_database_adapter(state_json_path=state_path)

    if not os.path.isfile(db_path):
        try:
            run_migrate()
            log_fn("info", "Phase 17: SQLite-DB angelegt (migrate).")
        except Exception as exc:
            log_fn("warning", f"Phase 17: migrate fehlgeschlagen: {exc}")
    else:
        try:
            run_migrate()
            log_fn("info", "Phase 17: DB-Tabellen geprüft/angelegt.")
        except Exception as exc:
            log_fn("warning", f"Phase 17: migrate check: {exc}")

    log_fn("info", "Phase 15: RelevanceScorer bereit.")
    log_fn("info", "Phase 16: RemoteSyncManager bereit.")

    use_ml = os.environ.get("USE_ML_SCORING", "true").strip().lower() in ("1", "true", "yes")
    model_path = default_model_path(data_dir)
    ml_model, ml_scaler = None, None
    if use_ml:
        ml_model, ml_scaler = load_relevance_model(model_path, log=lambda m: log_fn("info", m))
    ml_state = {
        "use_ml": use_ml,
        "model": ml_model,
        "scaler": ml_scaler,
        "model_path": model_path,
    }
    if use_ml and ml_model is None:
        log_fn("info", "Phase 23: ML aktiv, kein gespeichertes Modell — Ranking nutzt Heuristik bis Retrain.")

    return {
        "scorer": scorer,
        "sync": sync,
        "db_adapter": adapter,
        "data_dir": data_dir,
        "backend_dir": backend_dir,
        "ml": ml_state,
    }


def register_phase_routes(
    app,
    admin_required,
    get_learned_rules: Callable[[], List[dict]],
    project_root: str,
    log_fn,
    services: dict,
):
    scorer: RelevanceScorer = services["scorer"]
    sync: RemoteSyncManager = services["sync"]
    db_adp: DatabaseAdapter = services["db_adapter"]
    data_dir = services["data_dir"]

    @app.route("/api/rules/score", methods=["POST"], strict_slashes=False)
    @admin_required
    def api_rules_score():
        data = request.get_json(silent=True) or {}
        context = data.get("context") if isinstance(data.get("context"), dict) else {}
        rule_ids = data.get("rule_ids")
        rules = [r for r in get_learned_rules() if isinstance(r, dict)]
        if isinstance(rule_ids, list) and rule_ids:
            want = {str(x) for x in rule_ids}
            rules = [r for r in rules if str(r.get("fingerprint") or r.get("id") or "") in want]
        scores = scorer.score_batch(rules, context)
        top_match = None
        if scores:
            top_match = max(scores, key=lambda k: scores[k])
        return jsonify({"scores": scores, "top_match": top_match, "timestamp": _iso()}), 200

    @app.route("/api/rules/score-batch", methods=["POST", "GET"], strict_slashes=False)
    @admin_required
    def api_rules_score_batch():
        context = {}
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            if isinstance(data.get("context"), dict):
                context = data["context"]
        raw_q = request.args.get("context")
        if raw_q and not context:
            try:
                c = json.loads(raw_q)
                if isinstance(c, dict):
                    context = c
            except Exception:
                pass
        rules = [r for r in get_learned_rules() if isinstance(r, dict)]
        ranked = []
        for r in rules:
            rid = str(r.get("fingerprint") or r.get("id") or "").strip()
            if not rid:
                continue
            sc = scorer.score_rule(r, context)
            h = scorer.calculate_heuristics(r, context)
            ranked.append(
                {
                    "rule_id": rid,
                    "score": round(sc, 6),
                    "reason": f"keyword={h['keyword_match']}, success={h['success_rate']}, recency={h['recency_factor']}, freq={h['frequency_factor']}",
                    "heuristics": h,
                }
            )
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return jsonify({"ranked_rules": ranked, "timestamp": _iso()}), 200

    @app.route("/api/rules/heuristics/<rule_id>", methods=["GET"], strict_slashes=False)
    @admin_required
    def api_rules_heuristics(rule_id: str):
        ctx = {}
        raw = request.args.get("context")
        if raw:
            try:
                c = json.loads(raw)
                if isinstance(c, dict):
                    ctx = c
            except Exception:
                pass
        rid = str(rule_id or "").strip()
        rule = None
        for r in get_learned_rules():
            if isinstance(r, dict) and str(r.get("fingerprint") or r.get("id") or "").strip() == rid:
                rule = r
                break
        if rule is None:
            return jsonify({"error": "Regel nicht gefunden"}), 404
        h = scorer.calculate_heuristics(rule, ctx)
        return jsonify({"rule_id": rid, "heuristics": h, "timestamp": _iso()}), 200

    app.register_blueprint(
        create_management_blueprint(admin_required, get_learned_rules, scorer, services.get("ml"))
    )

    @app.route("/api/management/retrain-model", methods=["POST"], strict_slashes=False)
    @admin_required
    def api_management_retrain_model():
        ml = services.get("ml") or {}
        if not ml.get("use_ml"):
            return jsonify({"success": False, "error": "ML-Scoring ist deaktiviert (USE_ML_SCORING)."}), 400
        rules = [r for r in get_learned_rules() if isinstance(r, dict)]
        train_rows = rules_to_training_rows(rules, {})
        if len(train_rows) < 2:
            return jsonify({"success": False, "error": "Zu wenig Regeln zum Trainieren (min. 2)."}), 400

        def _train_log(msg: str) -> None:
            log_fn("info", msg)

        model, scaler = train_relevance_model(
            train_rows,
            epochs=80,
            model_path=ml.get("model_path"),
            verbose=True,
            log=_train_log,
        )
        if model is None:
            return jsonify({"success": False, "error": "Training fehlgeschlagen."}), 500
        ml["model"] = model
        ml["scaler"] = scaler
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Modell trainiert und gespeichert.",
                    "samples": len(train_rows),
                    "timestamp": _iso(),
                }
            ),
            200,
        )

    @app.route("/api/sync/register-agent", methods=["POST"], strict_slashes=False)
    @admin_required
    def api_sync_register():
        data = request.get_json(silent=True) or {}
        aid = str(data.get("agent_id") or "").strip()
        bu = str(data.get("base_url") or "").strip()
        try:
            po = int(data.get("port") or 0)
        except (TypeError, ValueError):
            return jsonify({"error": "port ungültig"}), 400
        if not aid or not bu or po <= 0:
            return jsonify({"error": "agent_id, base_url, port erforderlich"}), 400
        ok = sync.register_agent(aid, bu, po)
        if not ok:
            return jsonify({"error": "Registrierung fehlgeschlagen"}), 400
        return jsonify({"status": "registered", "agent_id": aid, "timestamp": _iso()}), 200

    @app.route("/api/sync/push-rules", methods=["POST"], strict_slashes=False)
    @admin_required
    def api_sync_push_rules():
        data = request.get_json(silent=True) or {}
        tid = str(data.get("target_agent_id") or "").strip()
        rules = data.get("rules")
        if not tid or not isinstance(rules, list):
            return jsonify({"error": "target_agent_id und rules (Liste) erforderlich"}), 400
        clean = [r for r in rules if isinstance(r, dict)]
        ok = sync.sync_rules(tid, clean)
        if not ok:
            return jsonify({"error": "sync fehlgeschlagen"}), 502
        return jsonify({"status": "synced", "count": len(clean), "timestamp": _iso()}), 200

    @app.route("/api/sync/pull-rules/<source_agent_id>", methods=["GET"], strict_slashes=False)
    @admin_required
    def api_sync_pull_rules(source_agent_id: str):
        rules = sync.pull_rules(source_agent_id)
        return jsonify({"rules": rules, "source": source_agent_id, "timestamp": _iso()}), 200

    @app.route("/api/sync/agents", methods=["GET"], strict_slashes=False)
    @admin_required
    def api_sync_agents():
        agents = sync.get_connected_agents()
        return jsonify({"agents": agents, "count": len(agents), "timestamp": _iso()}), 200

    @app.route("/api/sync/heartbeat/<agent_id>", methods=["POST"], strict_slashes=False)
    @admin_required
    def api_sync_heartbeat(agent_id: str):
        ok = sync.heartbeat(agent_id)
        return jsonify({"status": "ok" if ok else "timeout"}), 200 if ok else 404

    @app.route("/api/db/migrate", methods=["POST"], strict_slashes=False)
    @admin_required
    def api_db_migrate():
        try:
            res = run_migrate()
            return jsonify(res), 200
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.route("/api/db/status", methods=["GET"], strict_slashes=False)
    @admin_required
    def api_db_status():
        if not db_adp.available:
            return jsonify(
                {
                    "db_size": "n/a",
                    "rule_count": 0,
                    "history_count": 0,
                    "last_backup": None,
                    "mode": "state_json_fallback",
                }
            ), 200
        c = db_adp.counts()
        last_bu = None
        bu_path = os.path.join(project_root, "data", "db_backup_rules.json")
        if os.path.isfile(bu_path):
            try:
                last_bu = datetime.fromtimestamp(os.path.getmtime(bu_path), tz=timezone.utc).isoformat()
            except Exception:
                last_bu = None
        return jsonify(
            {
                **c,
                "last_backup": last_bu,
                "mode": "sqlite",
            }
        ), 200

    @app.route("/api/db/backup", methods=["POST"], strict_slashes=False)
    @admin_required
    def api_db_backup():
        if not db_adp.available:
            return jsonify({"status": "error", "message": "DB nicht verfügbar"}), 503
        out = os.path.join(project_root, "data", "db_backup_rules.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        ok = db_adp.backup_to_json(out)
        if not ok:
            return jsonify({"status": "error"}), 500
        sz = os.path.getsize(out) if os.path.isfile(out) else 0
        return jsonify({"status": "backed_up", "file": "db_backup_rules.json", "size": f"{sz} B"}), 200

    @app.route("/api/db/restore", methods=["POST"], strict_slashes=False)
    @admin_required
    def api_db_restore():
        if not db_adp.available:
            return jsonify({"status": "error", "message": "DB nicht verfügbar"}), 503
        data = request.get_json(silent=True) or {}
        name = str(data.get("file") or "db_backup_rules.json").strip()
        if "/" in name or "\\" in name or ".." in name:
            return jsonify({"error": "ungültiger Dateiname"}), 400
        path = os.path.join(project_root, "data", name)
        if not os.path.isfile(path):
            return jsonify({"error": "Datei nicht gefunden"}), 404
        ok = db_adp.restore_from_json(path)
        if not ok:
            return jsonify({"status": "error"}), 500
        cnt = db_adp.counts().get("rule_count", 0)
        return jsonify({"status": "restored", "rules_loaded": cnt}), 200

    log_fn("info", "Phase 15–17: API-Routen registriert.")
