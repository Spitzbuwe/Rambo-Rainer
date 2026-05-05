# -*- coding: utf-8 -*-
"""Remote Multi-Agent Sync (Phase 16)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class RemoteSyncManager:
    """Verwaltet bekannte Agenten und HTTP-Sync (rules export/import)."""

    def __init__(
        self,
        backend_data_dir: str,
        admin_token: str = "",
        heartbeat_timeout_s: float = 45.0,
    ):
        self.data_dir = backend_data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.agents_path = os.path.join(self.data_dir, "agents.json")
        self._admin_token = str(admin_token or "").strip()
        self.heartbeat_timeout_s = float(heartbeat_timeout_s)

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {}
        if self._admin_token:
            h["X-Rambo-Admin"] = self._admin_token
        return h

    def _load(self) -> Dict[str, Any]:
        if not os.path.isfile(self.agents_path):
            return {"agents": []}
        try:
            with open(self.agents_path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"agents": []}
            agents = data.get("agents")
            if not isinstance(agents, list):
                data["agents"] = []
            return data
        except Exception:
            return {"agents": []}

    def _save(self, data: Dict[str, Any]) -> None:
        tmp = self.agents_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.agents_path)

    def register_agent(self, agent_id: str, base_url: str, port: int) -> bool:
        aid = str(agent_id or "").strip()
        if not aid:
            return False
        bu = str(base_url or "").strip().rstrip("/")
        try:
            po = int(port)
        except (TypeError, ValueError):
            return False
        data = self._load()
        agents: List[dict] = list(data.get("agents") or [])
        now = _iso_now()
        found = False
        for a in agents:
            if isinstance(a, dict) and str(a.get("id")) == aid:
                a["base_url"] = bu
                a["port"] = po
                a["last_sync"] = a.get("last_sync") or now
                a["last_heartbeat"] = now
                a["connected"] = True
                found = True
                break
        if not found:
            agents.append(
                {
                    "id": aid,
                    "base_url": bu,
                    "port": po,
                    "connected": True,
                    "last_sync": now,
                    "last_heartbeat": now,
                }
            )
        data["agents"] = agents
        self._save(data)
        return True

    def get_connected_agents(self) -> List[Dict[str, Any]]:
        data = self._load()
        agents = []
        now = datetime.now(timezone.utc)
        for a in data.get("agents") or []:
            if not isinstance(a, dict):
                continue
            hb_raw = a.get("last_heartbeat") or a.get("last_sync")
            connected = bool(a.get("connected", True))
            if hb_raw:
                try:
                    s = str(hb_raw).replace("Z", "+00:00")
                    hb_dt = datetime.fromisoformat(s)
                    if hb_dt.tzinfo is None:
                        hb_dt = hb_dt.replace(tzinfo=timezone.utc)
                    if (now - hb_dt).total_seconds() > self.heartbeat_timeout_s:
                        connected = False
                except Exception:
                    connected = False
            agents.append(
                {
                    "id": a.get("id"),
                    "url": a.get("base_url"),
                    "port": a.get("port"),
                    "connected": connected,
                    "last_sync": a.get("last_sync"),
                    "last_heartbeat": a.get("last_heartbeat"),
                }
            )
        return agents

    def heartbeat(self, agent_id: str) -> bool:
        aid = str(agent_id or "").strip()
        if not aid:
            return False
        data = self._load()
        now = _iso_now()
        for a in data.get("agents") or []:
            if isinstance(a, dict) and str(a.get("id")) == aid:
                a["last_heartbeat"] = now
                a["connected"] = True
                self._save(data)
                return True
        return False

    def sync_rules(self, target_agent_id: str, rules_list: List[dict]) -> bool:
        if requests is None:
            return False
        aid = str(target_agent_id or "").strip()
        agent = None
        for a in self._load().get("agents") or []:
            if isinstance(a, dict) and str(a.get("id")) == aid:
                agent = a
                break
        if not agent:
            return False
        bu = str(agent.get("base_url") or "").rstrip("/")
        po = int(agent.get("port") or 0)
        url = f"{bu}:{po}/api/rules/import"
        try:
            r = requests.post(
                url,
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"learned_user_rules": rules_list, "merge": True},
                timeout=15,
            )
            ok = r.status_code == 200
            if ok:
                agent["last_sync"] = _iso_now()
                data = self._load()
                for i, x in enumerate(data.get("agents") or []):
                    if isinstance(x, dict) and str(x.get("id")) == aid:
                        data["agents"][i] = {**x, **agent}
                        break
                self._save(data)
            return ok
        except Exception:
            return False

    def pull_rules(self, source_agent_id: str) -> List[dict]:
        if requests is None:
            return []
        aid = str(source_agent_id or "").strip()
        agent = None
        for a in self._load().get("agents") or []:
            if isinstance(a, dict) and str(a.get("id")) == aid:
                agent = a
                break
        if not agent:
            return []
        bu = str(agent.get("base_url") or "").rstrip("/")
        po = int(agent.get("port") or 0)
        url = f"{bu}:{po}/api/rules/export"
        try:
            r = requests.get(url, headers=self._headers(), timeout=15)
            if r.status_code != 200:
                return []
            body = r.json()
            rules = body.get("learned_user_rules")
            if isinstance(rules, list):
                return [x for x in rules if isinstance(x, dict)]
        except Exception:
            pass
        return []

    def push_state(self, target_agent_id: str, state_dict: dict) -> bool:
        """Persistiert Sync-State lokal pro Agent (kein Standard-Remote-State-Endpoint)."""
        aid = str(target_agent_id or "").strip()
        if not aid or not isinstance(state_dict, dict):
            return False
        path = os.path.join(self.data_dir, f"pushed_state_{aid}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, ensure_ascii=False, indent=2)
            data = self._load()
            now = _iso_now()
            for a in data.get("agents") or []:
                if isinstance(a, dict) and str(a.get("id")) == aid:
                    a["last_sync"] = now
                    break
            self._save(data)
            return True
        except Exception:
            return False
