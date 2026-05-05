from performance_optimizer import PerformanceOptimizer as PO


def test_cache_result_reuses_value_within_ttl():
    calls = {"n": 0}

    @PO.cache_result(ttl=60)
    def get_value(x):
        calls["n"] += 1
        return {"x": x, "call": calls["n"]}

    first = get_value(7)
    second = get_value(7)
    assert first == second
    assert calls["n"] == 1


def test_lazy_load_runs_once():
    calls = {"n": 0}

    @PO.lazy_load
    def expensive():
        calls["n"] += 1
        return {"ok": True}

    assert expensive() == {"ok": True}
    assert expensive() == {"ok": True}
    assert calls["n"] == 1
