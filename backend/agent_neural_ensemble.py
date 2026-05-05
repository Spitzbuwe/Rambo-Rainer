"""Neural ensemble consensus engine (lokal, deterministisch, ohne externe Dienste)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

SolverFn = Callable[[str, dict[str, Any] | None], dict[str, Any] | str]


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", (text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    uni = len(a | b)
    return inter / uni if uni else 0.0


@dataclass
class SolverState:
    name: str
    solver_fn: SolverFn | None = None
    weight: float = 1.0
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    calls: int = 0
    successes: int = 0
    failures: int = 0
    avg_score: float = 0.0


class NeuralEnsembleEngine:
    def __init__(self) -> None:
        self._solvers: dict[str, SolverState] = {}
        self._version = 1
        self._install_default_solvers()

    def _install_default_solvers(self) -> None:
        self.add_solver("concise_solver", self._concise_solver, weight=1.0, metadata={"type": "default"})
        self.add_solver("step_by_step_solver", self._step_by_step_solver, weight=1.1, metadata={"type": "default"})
        self.add_solver("risk_aware_solver", self._risk_aware_solver, weight=1.05, metadata={"type": "default"})

    @staticmethod
    def _concise_solver(task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        t = " ".join(task.strip().split())
        answer = t if len(t) <= 120 else t[:117].rstrip() + "..."
        return {"answer": answer, "tags": ["concise"], "metadata": {"context_keys": sorted((context or {}).keys())}}

    @staticmethod
    def _step_by_step_solver(task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        words = [w for w in re.findall(r"\w+", task) if len(w) > 3][:6]
        if not words:
            words = ["problem", "analyse", "umsetzung"]
        steps = [f"{idx+1}. {w}" for idx, w in enumerate(words[:4])]
        return {
            "answer": "\n".join(steps),
            "tags": ["step_by_step"],
            "metadata": {"steps": len(steps), "ctx": bool(context)},
        }

    @staticmethod
    def _risk_aware_solver(task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        low = task.lower()
        risks: list[str] = []
        if any(k in low for k in ("delete", "remove", "reset", "drop")):
            risks.append("destructive_change")
        if any(k in low for k in ("secret", "token", "password", "key")):
            risks.append("secret_handling")
        if not risks:
            risks.append("normal_change")
        return {
            "answer": f"risks={','.join(risks)}; action=review_then_apply",
            "tags": ["risk_aware"],
            "metadata": {"risks": risks, "ctx_keys": sorted((context or {}).keys())},
        }

    def add_solver(
        self,
        name: str,
        solver_fn: SolverFn | None = None,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        fn = solver_fn or self._solvers.get(name, SolverState(name=name)).solver_fn
        if name in self._solvers:
            s = self._solvers[name]
            s.solver_fn = fn
            s.weight = float(max(0.0, weight))
            s.metadata = dict(metadata or s.metadata)
            s.enabled = True
            return
        self._solvers[name] = SolverState(
            name=name,
            solver_fn=fn,
            weight=float(max(0.0, weight)),
            enabled=True,
            metadata=dict(metadata or {}),
        )

    def remove_solver(self, name: str) -> bool:
        if name not in self._solvers:
            return False
        self._solvers[name].enabled = False
        return True

    def list_solvers(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name in sorted(self._solvers):
            s = self._solvers[name]
            out.append(
                {
                    "name": s.name,
                    "weight": s.weight,
                    "enabled": s.enabled,
                    "metadata": dict(s.metadata),
                    "calls": s.calls,
                    "successes": s.successes,
                    "failures": s.failures,
                    "avg_score": round(float(s.avg_score), 6),
                }
            )
        return out

    def evaluate_solution(
        self,
        solution: dict[str, Any],
        task: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> float:
        answer = str(solution.get("answer", "")).strip()
        if not answer:
            return 0.0
        score = 0.2
        length_bonus = min(0.45, len(answer) / 600.0)
        score += length_bonus
        if task:
            overlap = _jaccard(_tokenize(answer), _tokenize(task))
            score += min(0.25, overlap * 0.5)
        tags = solution.get("tags") or []
        if isinstance(tags, list) and tags:
            score += min(0.1, 0.03 * len(tags))
        if context:
            score += 0.03
        return round(max(0.0, min(1.0, score)), 6)

    def generate_solutions(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        active = [s for s in self._solvers.values() if s.enabled]
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        if not active:
            return {"solutions": [], "errors": [{"solver": "", "error": "no_active_solvers"}]}

        for s in sorted(active, key=lambda x: x.name):
            s.calls += 1
            try:
                if s.solver_fn is None:
                    raise RuntimeError("solver_fn_missing")
                raw = s.solver_fn(task, context)
                base = raw if isinstance(raw, dict) else {"answer": str(raw)}
                sol = {
                    "solver": s.name,
                    "answer": str(base.get("answer", "")),
                    "tags": list(base.get("tags", [])) if isinstance(base.get("tags", []), list) else [],
                    "metadata": dict(base.get("metadata", {})) if isinstance(base.get("metadata", {}), dict) else {},
                }
                sol["score"] = self.evaluate_solution(sol, task=task, context=context)
                sol["confidence"] = round(max(0.0, min(1.0, 0.5 + 0.5 * sol["score"])), 6)
                results.append(sol)
                s.successes += 1
                prev_n = max(1, s.successes - 1)
                s.avg_score = ((s.avg_score * prev_n) + float(sol["score"])) / float(s.successes)
            except Exception as e:  # noqa: BLE001
                s.failures += 1
                errors.append({"solver": s.name, "error": str(e)})

        ranked = self.rank_solutions(results)
        return {"solutions": ranked, "errors": errors}

    def rank_solutions(self, solutions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = [dict(x) for x in solutions]
        out.sort(
            key=lambda x: (
                -float(x.get("score", 0.0)),
                -float(x.get("confidence", 0.0)),
                str(x.get("solver", "")),
            )
        )
        return out

    def vote(self, solutions: list[dict[str, Any]]) -> dict[str, Any]:
        if not solutions:
            return {"best_solution": None, "groups": [], "vote_weights": {}, "winner_group_weight": 0.0}
        groups: list[dict[str, Any]] = []
        for sol in self.rank_solutions(solutions):
            ans = str(sol.get("answer", ""))
            tok = _tokenize(ans)
            placed = False
            for g in groups:
                sim = _jaccard(tok, g["tokens"])
                if sim >= 0.6:
                    g["items"].append(sol)
                    g["tokens"] = g["tokens"] | tok
                    g["weight"] += self._solvers.get(sol.get("solver", ""), SolverState(name="")).weight
                    placed = True
                    break
            if not placed:
                groups.append(
                    {
                        "items": [sol],
                        "tokens": tok,
                        "weight": self._solvers.get(sol.get("solver", ""), SolverState(name="")).weight,
                    }
                )

        for g in groups:
            g["items"] = self.rank_solutions(g["items"])
        groups.sort(key=lambda g: (-float(g["weight"]), -float(g["items"][0].get("score", 0.0)), str(g["items"][0].get("solver", ""))))
        best_group = groups[0]
        weights = {str(g["items"][0].get("solver", "")): round(float(g["weight"]), 6) for g in groups}
        return {
            "best_solution": best_group["items"][0],
            "groups": [{"weight": g["weight"], "items": g["items"]} for g in groups],
            "vote_weights": weights,
            "winner_group_weight": float(best_group["weight"]),
        }

    def diversity_score(self, solutions: list[dict[str, Any]]) -> float:
        if not solutions:
            return 0.0
        norm = [_normalize_text(str(s.get("answer", ""))) for s in solutions]
        uniq = len(set(norm))
        score = 0.0 if len(norm) == 1 else (uniq - 1) / (len(norm) - 1)
        return round(max(0.0, min(1.0, score)), 6)

    def confidence_score(self, vote_result: dict[str, Any]) -> float:
        groups = vote_result.get("groups", []) or []
        if not groups:
            return 0.0
        total_weight = sum(float(g.get("weight", 0.0)) for g in groups) or 1.0
        win = float(vote_result.get("winner_group_weight", 0.0))
        base = win / total_weight
        all_solutions = [item for g in groups for item in g.get("items", [])]
        div = self.diversity_score(all_solutions)
        conf = max(0.0, min(1.0, base * (1.0 - 0.25 * div)))
        return round(conf, 6)

    def consensus(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        gen = self.generate_solutions(task, context=context)
        sols = gen["solutions"]
        if not sols:
            return {
                "best_solution": None,
                "alternatives": [],
                "confidence": 0.0,
                "errors": gen["errors"],
                "diversity": 0.0,
            }
        vote_result = self.vote(sols)
        best = vote_result.get("best_solution")
        alternatives = [s for s in sols if s != best][:5]
        conf = self.confidence_score(vote_result)
        return {
            "best_solution": best,
            "alternatives": alternatives,
            "confidence": conf,
            "errors": gen["errors"],
            "diversity": self.diversity_score(sols),
            "vote": vote_result,
        }

    def export_state(self) -> dict[str, Any]:
        return {
            "version": self._version,
            "solvers": [
                {
                    "name": s.name,
                    "weight": s.weight,
                    "enabled": s.enabled,
                    "metadata": dict(s.metadata),
                    "calls": s.calls,
                    "successes": s.successes,
                    "failures": s.failures,
                    "avg_score": s.avg_score,
                }
                for s in sorted(self._solvers.values(), key=lambda x: x.name)
            ],
        }

    def import_state(self, data: dict[str, Any]) -> None:
        self._solvers = {}
        rows = data.get("solvers", [])
        if not isinstance(rows, list):
            rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            fn: SolverFn | None = None
            if name == "concise_solver":
                fn = self._concise_solver
            elif name == "step_by_step_solver":
                fn = self._step_by_step_solver
            elif name == "risk_aware_solver":
                fn = self._risk_aware_solver
            self._solvers[name] = SolverState(
                name=name,
                solver_fn=fn,
                weight=float(max(0.0, row.get("weight", 1.0))),
                enabled=bool(row.get("enabled", True)),
                metadata=dict(row.get("metadata", {})) if isinstance(row.get("metadata", {}), dict) else {},
                calls=int(max(0, int(row.get("calls", 0)))),
                successes=int(max(0, int(row.get("successes", 0)))),
                failures=int(max(0, int(row.get("failures", 0)))),
                avg_score=float(max(0.0, min(1.0, float(row.get("avg_score", 0.0))))),
            )
        if not self._solvers:
            self._install_default_solvers()

    def health(self) -> dict[str, Any]:
        enabled = sum(1 for s in self._solvers.values() if s.enabled)
        return {
            "ok": True,
            "status": "ready",
            "solver_count": len(self._solvers),
            "enabled_solver_count": enabled,
        }

    def __repr__(self) -> str:
        return json.dumps(self.health(), ensure_ascii=True)


_INSTANCE: NeuralEnsembleEngine | None = None


def get_instance() -> NeuralEnsembleEngine:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = NeuralEnsembleEngine()
    return _INSTANCE


__all__ = ["NeuralEnsembleEngine", "get_instance"]
