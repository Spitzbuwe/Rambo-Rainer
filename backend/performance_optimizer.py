"""
Performance-Optimierungen fuer Backend-Funktionen.
"""
from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable


class PerformanceOptimizer:
    CACHE: dict[str, tuple[Any, float]] = {}

    def optimize(self, code, language):
        text = str(code or "")
        optimizations = []
        optimizations.extend(self.find_caching_opportunities(text))
        optimizations.extend(self.find_algorithm_improvements(text))
        optimizations.extend(self.find_parallelization(text))
        return {
            "optimizations": optimizations,
            "estimated_speedup": self.estimate_speedup(optimizations),
        }

    def find_caching_opportunities(self, code):
        opps = []
        text = str(code or "").lower()
        if "query" in text or "database" in text or "select " in text:
            opps.append({
                "type": "Caching",
                "description": "Datenbank-/Query-Ergebnisse wirken cachebar",
                "suggestion": "In-Memory Cache oder Redis für Read-Last einbauen",
                "speedup": "3x-20x",
            })
        return opps

    def find_algorithm_improvements(self, code):
        opps = []
        text = str(code or "")
        if text.count("for ") >= 2:
            opps.append({
                "type": "Algorithm",
                "description": "Mehrere Loops können algorithmisch verbessert werden",
                "suggestion": "Set/Dict Lookups und Voraggregation statt mehrfacher Durchläufe",
                "speedup": "2x-10x",
            })
        return opps

    def find_parallelization(self, code):
        opps = []
        text = str(code or "")
        if text.count("for ") >= 2 or "requests.get(" in text:
            opps.append({
                "type": "Parallelization",
                "description": "Unabhängige Arbeitspakete identifiziert",
                "suggestion": "ThreadPool/asyncio für I/O-lastige Aufgaben prüfen",
                "speedup": "1.5x-4x",
            })
        return opps

    def estimate_speedup(self, optimizations):
        if not optimizations:
            return "1.0x"
        factors = []
        for item in optimizations:
            speedup = str(item.get("speedup") or "")
            if "x" in speedup:
                base = speedup.split("x")[0].strip().split("-")[0]
                try:
                    factors.append(float(base))
                except Exception:
                    pass
        if not factors:
            return "1.2x"
        avg = sum(factors) / len(factors)
        return f"{avg:.1f}x"

    @staticmethod
    def time_function(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            if elapsed > 1.0:
                print(f"[perf] {func.__name__}: {elapsed:.2f}s")
            return result

        return wrapper

    @staticmethod
    def cache_result(ttl: int = 300):
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                key = f"{func.__name__}:{repr(args)}:{repr(kwargs)}"
                now = time.time()
                if key in PerformanceOptimizer.CACHE:
                    cached, ts = PerformanceOptimizer.CACHE[key]
                    if now - ts < ttl:
                        return cached
                result = func(*args, **kwargs)
                PerformanceOptimizer.CACHE[key] = (result, now)
                return result

            return wrapper

        return decorator

    @staticmethod
    def lazy_load(func: Callable):
        _loaded = {"ok": False, "value": None}

        @wraps(func)
        def wrapper(*args, **kwargs):
            if not _loaded["ok"]:
                _loaded["value"] = func(*args, **kwargs)
                _loaded["ok"] = True
            return _loaded["value"]

        return wrapper
