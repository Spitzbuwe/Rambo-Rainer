"""Multi-layer cache for agent runtime (memory + optional disk)."""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable

_SECRET_HINT = re.compile(r"(?i)(token|secret|password|api[_-]?key)")


def _json_dumps_stable(data: object) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


class AgentCache:
    def __init__(
        self,
        project_root: Path | str | None = None,
        *,
        max_entries: int = 256,
        enable_disk: bool = True,
    ) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self.max_entries = max(1, int(max_entries))
        self.enable_disk = bool(enable_disk)
        self.cache_dir = self.project_root / ".rainer_agent" / "cache"
        self._mem: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "expired": 0,
        }
        if self.enable_disk:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def make_key(self, namespace: str, payload: object) -> str:
        ns = (namespace or "").strip() or "default"
        payload_json = _json_dumps_stable(payload)
        raw = f"{ns}:{payload_json}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{ns}:{digest}"

    def _disk_path(self, key: str) -> Path:
        safe = hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json"
        return self.cache_dir / safe

    def _is_expired(self, entry: dict[str, Any]) -> bool:
        exp = entry.get("expires_at")
        return exp is not None and float(exp) <= time.time()

    def _evict_if_needed(self) -> None:
        while len(self._mem) > self.max_entries:
            key, old = self._mem.popitem(last=False)
            self._stats["evictions"] += 1
            if self.enable_disk:
                self._disk_path(key).unlink(missing_ok=True)

    def _validate_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        md = dict(metadata or {})
        raw = _json_dumps_stable(md)
        if _SECRET_HINT.search(raw):
            raise ValueError("metadata_contains_secret_like_content")
        return md

    def _validate_json_serializable(self, value: object) -> None:
        _json_dumps_stable(value)

    def set(
        self,
        key: str,
        value: object,
        ttl_seconds: int | None = None,
        metadata: dict | None = None,
    ) -> dict:
        try:
            self._validate_json_serializable(value)
        except Exception:
            return {"ok": False, "reason": "value_not_json_serializable", "key": key}
        try:
            md = self._validate_metadata(metadata)
        except Exception as e:
            return {"ok": False, "reason": str(e), "key": key}

        now = time.time()
        expires_at = None if ttl_seconds is None else now + max(0, int(ttl_seconds))
        entry = {
            "key": key,
            "value": value,
            "metadata": md,
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at,
            "namespace": key.split(":", 1)[0] if ":" in key else "default",
        }
        if key in self._mem:
            del self._mem[key]
        self._mem[key] = entry
        self._mem.move_to_end(key, last=True)
        self._stats["sets"] += 1
        self._evict_if_needed()
        if self.enable_disk:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._disk_path(key).write_text(_json_dumps_stable(entry), encoding="utf-8")
        return {"ok": True, "key": key}

    def _load_from_disk(self, key: str) -> dict[str, Any] | None:
        if not self.enable_disk:
            return None
        p = self._disk_path(key)
        if not p.exists():
            return None
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
            if self._is_expired(entry):
                self._stats["expired"] += 1
                p.unlink(missing_ok=True)
                return None
            self._mem[key] = entry
            self._mem.move_to_end(key, last=True)
            self._evict_if_needed()
            return entry
        except Exception:
            p.unlink(missing_ok=True)
            return None

    def get(self, key: str) -> dict:
        entry = self._mem.get(key)
        if entry is None:
            entry = self._load_from_disk(key)
        if entry is None:
            self._stats["misses"] += 1
            return {"hit": False, "key": key, "value": None}
        if self._is_expired(entry):
            self._stats["expired"] += 1
            self.delete(key)
            self._stats["misses"] += 1
            return {"hit": False, "key": key, "value": None}
        self._mem.move_to_end(key, last=True)
        self._stats["hits"] += 1
        return {"hit": True, "key": key, "value": entry["value"], "metadata": entry.get("metadata", {})}

    def has(self, key: str) -> bool:
        return bool(self.get(key)["hit"])

    def delete(self, key: str) -> dict:
        existed = key in self._mem
        self._mem.pop(key, None)
        if self.enable_disk:
            p = self._disk_path(key)
            if p.exists():
                existed = True
                p.unlink(missing_ok=True)
        if existed:
            self._stats["deletes"] += 1
        return {"ok": True, "deleted": existed, "key": key}

    def clear(self, namespace: str | None = None) -> dict:
        if namespace is None:
            n = len(self._mem)
            self._mem.clear()
            if self.enable_disk and self.cache_dir.exists():
                for p in self.cache_dir.glob("*.json"):
                    p.unlink(missing_ok=True)
            return {"ok": True, "cleared": n, "namespace": None}

        keys = [k for k in self._mem if k.startswith(f"{namespace}:")]
        for k in keys:
            self._mem.pop(k, None)
            if self.enable_disk:
                self._disk_path(k).unlink(missing_ok=True)
        return {"ok": True, "cleared": len(keys), "namespace": namespace}

    def cleanup_expired(self) -> dict:
        removed = 0
        for key in list(self._mem.keys()):
            if self._is_expired(self._mem[key]):
                self._mem.pop(key, None)
                if self.enable_disk:
                    self._disk_path(key).unlink(missing_ok=True)
                removed += 1
        if self.enable_disk and self.cache_dir.exists():
            for p in self.cache_dir.glob("*.json"):
                try:
                    item = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    p.unlink(missing_ok=True)
                    removed += 1
                    continue
                if self._is_expired(item):
                    p.unlink(missing_ok=True)
                    removed += 1
        self._stats["expired"] += removed
        return {"ok": True, "removed": removed}

    def stats(self) -> dict:
        return {
            **self._stats,
            "size": len(self._mem),
            "max_entries": self.max_entries,
            "disk_enabled": self.enable_disk,
        }

    def export_index(self) -> dict:
        entries = {
            k: {
                "value": v["value"],
                "metadata": v.get("metadata", {}),
                "created_at": v.get("created_at"),
                "updated_at": v.get("updated_at"),
                "expires_at": v.get("expires_at"),
                "namespace": v.get("namespace", "default"),
            }
            for k, v in self._mem.items()
            if not self._is_expired(v)
        }
        return {"ok": True, "entries": entries, "stats": self.stats()}

    def import_index(self, data: dict) -> dict:
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            return {"ok": False, "reason": "invalid_payload"}
        loaded = 0
        for key, entry in data["entries"].items():
            if not isinstance(entry, dict):
                continue
            if entry.get("expires_at") is not None and float(entry["expires_at"]) <= time.time():
                continue
            try:
                self._validate_json_serializable(entry.get("value"))
            except Exception:
                continue
            self._mem[key] = {
                "key": key,
                "value": entry.get("value"),
                "metadata": dict(entry.get("metadata", {})),
                "created_at": entry.get("created_at", time.time()),
                "updated_at": entry.get("updated_at", time.time()),
                "expires_at": entry.get("expires_at"),
                "namespace": entry.get("namespace", key.split(":", 1)[0] if ":" in key else "default"),
            }
            if self.enable_disk:
                self._disk_path(key).write_text(_json_dumps_stable(self._mem[key]), encoding="utf-8")
            loaded += 1
        self._evict_if_needed()
        return {"ok": True, "loaded": loaded}

    def cached_call(
        self,
        namespace: str,
        payload: object,
        fn: Callable[[], object],
        ttl_seconds: int | None = None,
    ) -> dict:
        key = self.make_key(namespace, payload)
        cached = self.get(key)
        if cached["hit"]:
            return {"hit": True, "key": key, "value": cached["value"]}
        value = fn()
        set_out = self.set(key, value, ttl_seconds=ttl_seconds)
        if not set_out["ok"]:
            return {"hit": False, "key": key, "error": set_out["reason"]}
        return {"hit": False, "key": key, "value": value}

    def health(self) -> dict:
        return {"ok": True, "status": "ready", "module": "agent_caching", "stats": self.stats()}

    def describe(self) -> str:
        return "AgentCache"


_INSTANCE: AgentCache | None = None


def get_instance(project_root: Path | str | None = None) -> AgentCache:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AgentCache(project_root)
    return _INSTANCE


AgentCacheLayer = AgentCache

__all__ = ["AgentCache", "AgentCacheLayer", "get_instance"]
