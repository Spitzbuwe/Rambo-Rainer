# -*- coding: utf-8 -*-
"""DB-Adapter mit state.json-Fallback (Phase 17)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import select, func
    from sqlalchemy.exc import SQLAlchemyError

    from db import create_all, get_engine, init_engine, session_scope
    from models import History, Rule
    _ORM_OK = True
except ImportError:
    _ORM_OK = False
    SQLAlchemyError = Exception  # type: ignore


class DatabaseAdapter:
    def __init__(self, db_url: Optional[str] = None, state_json_path: Optional[str] = None):
        self.db_url = db_url
        self._ok = _ORM_OK
        self.state_json_path = state_json_path
        if self._ok:
            try:
                init_engine(db_url)
                create_all()
            except Exception:
                self._ok = False

    @property
    def available(self) -> bool:
        return self._ok

    def save_rule(self, rule_dict: dict) -> Optional[str]:
        if not self._ok or not isinstance(rule_dict, dict):
            return None
        rid = str(rule_dict.get("fingerprint") or rule_dict.get("id") or "").strip()
        if not rid:
            return None
        try:
            with session_scope() as s:
                row = s.get(Rule, rid)
                name = str(rule_dict.get("value") or rule_dict.get("name") or "")[:500]
                if row is None:
                    row = Rule(id=rid, name=name, conditions=json.dumps(rule_dict, ensure_ascii=False)[:8000])
                    s.add(row)
                else:
                    row.name = name
                    row.conditions = json.dumps(rule_dict, ensure_ascii=False)[:8000]
                return rid
        except SQLAlchemyError:
            return None

    def get_rule(self, rule_id: str) -> Optional[dict]:
        if not self._ok:
            return None
        try:
            with session_scope() as s:
                row = s.get(Rule, str(rule_id))
                if row is None:
                    return None
                try:
                    return json.loads(row.conditions or "{}")
                except Exception:
                    return {"id": row.id, "name": row.name}
        except SQLAlchemyError:
            return None

    def get_all_rules(self) -> List[dict]:
        if not self._ok:
            return []
        try:
            with session_scope() as s:
                rows = s.scalars(select(Rule)).all()
                out = []
                for row in rows:
                    try:
                        out.append(json.loads(row.conditions or "{}"))
                    except Exception:
                        out.append({"id": row.id, "name": row.name})
                return out
        except SQLAlchemyError:
            return []

    def update_rule(self, rule_id: str, updates: dict) -> bool:
        cur = self.get_rule(rule_id)
        if cur is None:
            cur = {"fingerprint": rule_id}
        if isinstance(updates, dict):
            cur.update(updates)
        return self.save_rule(cur) is not None

    def delete_rule(self, rule_id: str) -> bool:
        if not self._ok:
            return False
        try:
            with session_scope() as s:
                row = s.get(Rule, str(rule_id))
                if row is None:
                    return False
                s.delete(row)
                return True
        except SQLAlchemyError:
            return False

    def save_history(self, rule_id: str, context: Any, action: str, success: bool) -> Optional[int]:
        if not self._ok:
            return None
        try:
            with session_scope() as s:
                h = History(
                    rule_id=str(rule_id),
                    input_context=json.dumps(context, ensure_ascii=False)[:8000] if context is not None else "",
                    output_action=str(action or "")[:8000],
                    success=bool(success),
                )
                s.add(h)
                s.flush()
                return int(h.id)
        except SQLAlchemyError:
            return None

    def get_history(self, rule_id: str, limit: int = 100) -> List[dict]:
        if not self._ok:
            return []
        try:
            with session_scope() as s:
                q = (
                    select(History)
                    .where(History.rule_id == str(rule_id))
                    .order_by(History.timestamp.desc())
                    .limit(max(1, min(limit, 500)))
                )
                rows = s.scalars(q).all()
                return [
                    {
                        "id": r.id,
                        "rule_id": r.rule_id,
                        "input_context": r.input_context,
                        "output_action": r.output_action,
                        "success": r.success,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                    }
                    for r in rows
                ]
        except SQLAlchemyError:
            return []

    def backup_to_json(self, filepath: str) -> bool:
        if not self._ok:
            return False
        try:
            payload = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "learned_user_rules": self.get_all_rules(),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def restore_from_json(self, filepath: str) -> bool:
        if not self._ok or not os.path.isfile(filepath):
            return False
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            rules = data.get("learned_user_rules")
            if isinstance(data, dict) and "rambo_agent_policy" in data:
                pol = data.get("rambo_agent_policy") or {}
                rules = pol.get("learned_user_rules")
            if not isinstance(rules, list):
                return False
            for r in rules:
                if isinstance(r, dict):
                    self.save_rule(r)
            return True
        except Exception:
            return False

    def counts(self) -> Dict[str, Any]:
        if not self._ok:
            return {"rule_count": 0, "history_count": 0, "db_size": "0 B"}
        try:
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(backend_dir, "data", "rambo_rainer.db")
            sz = os.path.getsize(path) if os.path.isfile(path) else 0
            with session_scope() as s:
                rc = s.scalar(select(func.count()).select_from(Rule)) or 0
                hc = s.scalar(select(func.count()).select_from(History)) or 0
            return {
                "rule_count": int(rc),
                "history_count": int(hc),
                "db_size": f"{sz / 1024:.1f} KB" if sz < 1024 * 1024 else f"{sz / (1024 * 1024):.1f} MB",
            }
        except Exception:
            return {"rule_count": 0, "history_count": 0, "db_size": "?"}


_adapter_singleton: Optional[DatabaseAdapter] = None


def get_database_adapter(state_json_path: Optional[str] = None) -> DatabaseAdapter:
    global _adapter_singleton
    if _adapter_singleton is None:
        _adapter_singleton = DatabaseAdapter(state_json_path=state_json_path)
    return _adapter_singleton
