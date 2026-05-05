"""Discrete cause-effect graph, cycle checks, paths, error-pattern graph (local only)."""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_RECOMMENDED_FIX: dict[str, str] = {
    "cause:unicode_string_escaping": "fix:normalize_path_literals",
    "cause:electron_asset_or_packaging": "fix:verify_asar_and_loadfile_paths",
    "cause:pytest_failure": "fix:inspect_traceback_and_assertions",
    "cause:ollama_provider_unavailable": "fix:fallback_to_local_heuristics_or_available_model",
}


@dataclass
class CausalGraphEngine:
    """Directed weighted edges cause -> effect."""

    project_root: Path = field(default_factory=lambda: Path(".").resolve())
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[dict[str, Any]] = field(default_factory=list)

    def add_node(self, node_id: str, **meta: Any) -> None:
        self.nodes[node_id] = {"id": node_id, **meta}

    def add_factor(self, name: str, **meta: Any) -> None:
        m = dict(meta)
        m.setdefault("kind", "factor")
        self.add_node(name, **m)

    def add_edge(self, cause: str, effect: str, weight: float = 0.5) -> None:
        w = max(0.0, min(1.0, float(weight)))
        self.edges.append({"source": cause, "target": effect, "weight": w})
        self.add_node(cause)
        self.add_node(effect)

    def add_relation(self, cause: str, effect: str, weight: float = 0.5, *, allow_cycle: bool = False) -> bool:
        if not allow_cycle and self.would_create_cycle(cause, effect):
            return False
        self.add_edge(cause, effect, weight)
        return True

    def _adj_out(self) -> dict[str, list[str]]:
        m: dict[str, list[str]] = defaultdict(list)
        for e in self.edges:
            m[str(e["source"])].append(str(e["target"]))
        return m

    def would_create_cycle(self, cause: str, effect: str) -> bool:
        if cause == effect:
            return True
        adj = self._adj_out()
        stack = [effect]
        seen: set[str] = {effect}
        while stack:
            u = stack.pop()
            for v in adj.get(u, ()):
                if v == cause:
                    return True
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return False

    def detect_cycles(self) -> list[list[str]]:
        adj = self._adj_out()
        nodes = sorted(set(self.nodes) | set(adj) | {t for vs in adj.values() for t in vs})
        found: list[list[str]] = []
        seen_t: set[tuple[str, ...]] = set()

        def walk2(start: str, cur: str, path: list[str], limit: int) -> None:
            if limit < 0:
                return
            for n2 in sorted(adj.get(cur, ())):
                if n2 == start and len(path) >= 2:
                    cyc = path + [start]
                    key = tuple(cyc)
                    if key not in seen_t:
                        seen_t.add(key)
                        found.append(cyc)
                elif n2 not in path:
                    walk2(start, n2, path + [n2], limit - 1)

        for s in nodes:
            for nxt in sorted(adj.get(s, ())):
                walk2(s, nxt, [s, nxt], 10)
        found.sort(key=lambda c: (len(c), c))
        return found[:32]

    def predecessors(self, effect: str) -> list[tuple[str, float]]:
        return [(str(e["source"]), float(e["weight"])) for e in self.edges if str(e["target"]) == effect]

    def score_causes_for_effects(self, observed_effects: list[str], max_depth: int = 8) -> dict[str, float]:
        raw: dict[str, float] = defaultdict(float)

        def walk(node: str, flow: float, depth: int) -> None:
            if depth > max_depth or flow < 1e-9:
                return
            for cause, w in self.predecessors(node):
                inc = flow * w
                raw[cause] += inc
                walk(cause, inc, depth + 1)

        for eff in observed_effects:
            walk(eff, 1.0, 0)
        if not raw:
            return {}
        mx = max(raw.values()) or 1.0
        return {k: round(v / mx, 6) for k, v in sorted(raw.items(), key=lambda x: (-x[1], x[0]))}

    def rank_causes(self, effect: str) -> list[dict[str, Any]]:
        scores = self.score_causes_for_effects([effect])
        items = [{"cause": k, "score": v} for k, v in scores.items()]
        items.sort(key=lambda x: (-x["score"], x["cause"]))
        return items

    def explain_path(self, cause: str, effect: str) -> list[str]:
        if cause == effect:
            return [cause]
        adj = self._adj_out()
        q: deque[str] = deque([cause])
        parent: dict[str, str | None] = {cause: None}
        while q:
            u = q.popleft()
            for v in sorted(adj.get(u, ())):
                if v not in parent:
                    parent[v] = u
                    if v == effect:
                        out: list[str] = []
                        cur: str | None = effect
                        while cur is not None:
                            out.append(cur)
                            cur = parent[cur]
                        return list(reversed(out))
                    q.append(v)
        return []

    def root_cause_candidates(self, observed_effects: list[str], top_k: int = 5) -> list[dict[str, Any]]:
        scores = self.score_causes_for_effects(observed_effects)
        out: list[dict[str, Any]] = []
        for name, sc in list(scores.items())[: max(1, top_k)]:
            out.append({"node": name, "score": sc, "meta": self.nodes.get(name, {})})
        return out

    def root_cause_analysis(self, error_text: str) -> dict[str, Any]:
        g = self.build_from_error(error_text)
        ranked = g.rank_causes("effect:observed")
        root = ranked[0]["cause"] if ranked else ""
        conf = float(ranked[0]["score"]) if ranked else 0.0
        path = g.explain_path(root, "effect:observed") if root else []
        fix = _RECOMMENDED_FIX.get(root, "fix:inspect_logs")
        return {
            "root_cause": root,
            "confidence": conf,
            "path": path,
            "recommended_fix": fix,
        }

    @classmethod
    def build_from_error(cls, error_text: str) -> CausalGraphEngine:
        g = cls()
        eff = "effect:observed"
        g.add_factor(eff, kind="effect")
        et = error_text or ""
        low = et.lower()
        if "unicodeescape" in low or ("unicode" in low and "escape" in low):
            g.add_relation("cause:unicode_string_escaping", eff, 0.92)
        if "winerror" in low and ("path" in low or "\\" in et):
            g.add_relation("cause:unicode_string_escaping", eff, 0.55)
        if ("white" in low and "screen" in low) or ("blank" in low and "window" in low):
            if "electron" in low or "vite" in low or "asar" in low:
                g.add_relation("cause:electron_asset_or_packaging", eff, 0.88)
        if "dist/" in low or "dist\\" in low:
            if "index.html" in low or "index" in low:
                g.add_relation("cause:electron_asset_or_packaging", eff, 0.8)
        if "pytest" in low or "py_compile" in low or "test failed" in low:
            g.add_relation("cause:pytest_failure", eff, 0.7)
        if "ollama" in low and ("provider" in low or "unavailable" in low or "model" in low):
            g.add_relation("cause:ollama_provider_unavailable", eff, 0.85)
        if not any(e["source"].startswith("cause:") for e in g.edges):
            g.add_relation("cause:unknown", eff, 0.1)
        return g

    def bayesian_update_table(
        self,
        hypothesis: str,
        evidence: str,
        p_e_given_h: float,
        p_e_given_not_h: float,
        prior_h: float,
    ) -> dict[str, float]:
        p_h = max(1e-9, min(1.0 - 1e-9, float(prior_h)))
        p_e_h = max(1e-9, min(1.0 - 1e-9, float(p_e_given_h)))
        p_e_nh = max(1e-9, min(1.0 - 1e-9, float(p_e_given_not_h)))
        p_e = p_e_h * p_h + p_e_nh * (1.0 - p_h)
        post = (p_e_h * p_h) / p_e
        self.add_edge(hypothesis, evidence, p_e_h)
        return {
            "hypothesis": hypothesis,
            "evidence": evidence,
            "prior": round(p_h, 6),
            "posterior": round(post, 6),
        }

    def export_graph(self) -> dict[str, Any]:
        return {
            "nodes": [{"id": k, **{kk: vv for kk, vv in v.items() if kk != "id"}} for k, v in self.nodes.items()],
            "edges": list(self.edges),
        }

    def health(self) -> dict[str, Any]:
        return {
            "module": "agent_causal_graphs",
            "class": "CausalGraphEngine",
            "ok": True,
            "status": "ready",
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }

    def describe(self) -> str:
        return "CausalGraphEngine"


def get_instance(project_root: Path | str | None = None) -> CausalGraphEngine:
    return CausalGraphEngine(project_root=Path(project_root or ".").resolve())


__all__ = ["CausalGraphEngine", "get_instance"]
