"""Advanced Reasoning — strukturierte JSON-Envelopes, optional injizierbarer Executor."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any, Callable

logger = logging.getLogger(__name__)

_ExecuteFn = Callable[..., dict[str, Any]]

class AdvancedReasoning:
    def __init__(self, execute_fn: _ExecuteFn | None = None) -> None:
        self._execute_fn = execute_fn

    def _exec(
        self,
        payload: str,
        context: str = "",
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        if self._execute_fn is not None:
            return self._execute_fn(payload, context=context, system_prompt=system_prompt)
        from hybrid_optimizer import hybrid_optimizer

        return hybrid_optimizer.execute_optimized(
            payload,
            context=context,
            system_prompt=(system_prompt if system_prompt is not None else "") or "",
        )

    @staticmethod
    def _envelope(op: str, **fields: Any) -> str:
        return json.dumps({"op": op, **fields}, ensure_ascii=False, default=str)

    def chain_of_thought(self, task: str, variant: int = 0) -> dict[str, Any]:
        payload = self._envelope("cot", task=task, variant=variant)
        r = self._exec(payload, context="", system_prompt="")
        return {
            "method": "chain_of_thought",
            "variant": variant,
            "success": bool(r.get("success")),
            "text": r.get("response", ""),
            "model": r.get("model", ""),
        }

    def tree_of_thought(self, task: str, num_paths: int = 3, depth: int = 3) -> dict[str, Any]:
        paths: list[dict[str, Any]] = []
        n_paths = max(1, num_paths)
        dlim = max(1, depth)
        for path_idx in range(n_paths):
            payload = self._envelope(
                "tot",
                task=task,
                path_id=path_idx,
                num_paths=n_paths,
                depth_limit=dlim,
            )
            r = self._exec(payload, context="", system_prompt="")
            text = str(r.get("response", ""))
            qm = re.search(r"QUALITY_SCORE\s*[:=]\s*([0-9]*\.?[0-9]+)", text, re.I)
            score = float(qm.group(1)) if qm else min(1.0, max(0.0, len(text) / 2000.0))
            paths.append(
                {
                    "path_id": path_idx,
                    "text": text,
                    "quality_score": score,
                    "success": bool(r.get("success")),
                }
            )
        ranked = sorted(paths, key=lambda p: p.get("quality_score", 0.0), reverse=True)
        return {
            "all_paths": ranked,
            "best_path": ranked[0] if ranked else None,
            "diversity": self._calculate_diversity(paths),
        }

    @staticmethod
    def _calculate_diversity(paths: list[dict[str, Any]]) -> float:
        if len(paths) < 2:
            return 0.0
        texts = [str(p.get("text", ""))[:500] for p in paths]
        uniq = len(set(texts))
        return round(uniq / len(texts), 3)

    def self_consistency(self, task: str, num_runs: int = 5) -> dict[str, Any]:
        n = max(2, min(12, num_runs))
        solutions: list[dict[str, Any]] = []
        for i in range(n):
            solutions.append(self.chain_of_thought(task, variant=i))
        winner = self._majority_voting(solutions)
        agree = sum(1 for s in solutions if self._solutions_similar(s, winner))
        return {
            "all_solutions": solutions,
            "consensus": winner,
            "confidence": self._calculate_consensus(solutions),
            "agreement_percentage": round(100.0 * agree / n, 1),
        }

    @staticmethod
    def _normalize_snippet(text: str) -> str:
        t = " ".join((text or "").split())[:240].lower()
        return t

    def _majority_voting(self, solutions: list[dict[str, Any]]) -> dict[str, Any]:
        if not solutions:
            return {}
        buckets: dict[str, list[dict[str, Any]]] = {}
        for s in solutions:
            key = self._normalize_snippet(str(s.get("text", "")))
            buckets.setdefault(key or "empty", []).append(s)
        _best_key, group = max(buckets.items(), key=lambda kv: len(kv[1]))
        return group[0] if group else solutions[0]

    @staticmethod
    def _solutions_similar(a: dict[str, Any], b: dict[str, Any]) -> bool:
        return AdvancedReasoning._normalize_snippet(str(a.get("text", ""))) == AdvancedReasoning._normalize_snippet(
            str(b.get("text", ""))
        )

    @staticmethod
    def _calculate_consensus(solutions: list[dict[str, Any]]) -> float:
        if not solutions:
            return 0.0
        keys = [AdvancedReasoning._normalize_snippet(str(s.get("text", ""))) for s in solutions]
        top = Counter(keys).most_common(1)[0][1]
        return round(top / len(solutions), 3)

    @staticmethod
    def _parse_causal_structured(response: str) -> dict[str, Any]:
        base: dict[str, Any] = {
            "immediate_cause": "",
            "root_cause": "",
            "contributing_factors": [],
            "generalized_fix": "",
        }
        raw = (response or "").strip()
        if not raw:
            return base
        try:
            o = json.loads(raw)
            if isinstance(o, dict):
                base["immediate_cause"] = str(o.get("immediate_cause", ""))
                base["root_cause"] = str(o.get("root_cause", ""))
                base["generalized_fix"] = str(o.get("generalized_fix", ""))
                cf = o.get("contributing_factors", [])
                if isinstance(cf, list):
                    base["contributing_factors"] = [str(x) for x in cf]
                elif isinstance(cf, str) and cf.strip():
                    base["contributing_factors"] = [cf.strip()]
                return base
        except json.JSONDecodeError:
            pass
        for line in raw.splitlines():
            s = line.strip()
            if not s:
                continue
            low = s.lower()
            if low.startswith("immediate_cause:"):
                base["immediate_cause"] = s.split(":", 1)[1].strip()
            elif low.startswith("root_cause:"):
                base["root_cause"] = s.split(":", 1)[1].strip()
            elif low.startswith("generalized_fix:"):
                base["generalized_fix"] = s.split(":", 1)[1].strip()
            elif low.startswith("contributing_factors:"):
                rest = s.split(":", 1)[1].strip()
                base["contributing_factors"] = [x.strip() for x in rest.split(";") if x.strip()]
        return base

    def causal_analysis(self, problem: str, error: str, context: str = "") -> dict[str, Any]:
        payload = self._envelope("causal", problem=problem, error=error, context=context)
        analysis = self._exec(payload, context="", system_prompt="")
        resp = str(analysis.get("response", ""))
        structured = self._parse_causal_structured(resp)
        return {
            "success": bool(analysis.get("success")),
            "model": analysis.get("model", ""),
            "immediate_cause": structured["immediate_cause"],
            "root_cause": structured["root_cause"],
            "contributing_factors": structured["contributing_factors"],
            "generalized_fix": structured["generalized_fix"],
            "actionable_insights": [x for x in structured["contributing_factors"] if x][:12],
            "raw_response": resp,
        }

    def recursive_reasoning(self, task: str, depth: int = 5) -> dict[str, Any]:
        d = max(1, min(8, depth))
        chain: list[dict[str, Any]] = []
        level1 = self.chain_of_thought(task, variant=0)
        chain.append({"level": 1, "reasoning": level1})
        for level in range(2, d + 1):
            prev = str(chain[-1]["reasoning"].get("text", ""))[:1200]
            payload = self._envelope("recursive", prior=prev, task=task, level=level)
            r = self._exec(payload, context="", system_prompt="")
            level_result = {
                "method": "chain_of_thought",
                "variant": level,
                "success": bool(r.get("success")),
                "text": r.get("response", ""),
                "model": r.get("model", ""),
            }
            chain.append({"level": level, "reasoning": level_result})
        return {
            "depth": d,
            "reasoning_chain": chain,
            "final_answer": chain[-1]["reasoning"] if chain else None,
        }

    def assumption_validation(self, task: str, assumptions: list[str] | None = None) -> dict[str, Any]:
        payload = self._envelope(
            "assumption",
            task=task,
            assumptions=list(assumptions or []),
        )
        r = self._exec(payload, context="", system_prompt="")
        return {
            "method": "assumption_validation",
            "task": task,
            "assumptions": list(assumptions or []),
            "text": r.get("response", ""),
            "success": bool(r.get("success")),
        }

    def health(self) -> dict[str, Any]:
        return {"module": "agent_reasoning", "ok": True}


advanced_reasoning = AdvancedReasoning()
__all__ = ["AdvancedReasoning", "advanced_reasoning"]
