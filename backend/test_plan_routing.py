"""Regression: RAINER_BEHEBUNGSPLAN Phase 1 (classify_direct_execution_route)."""
import importlib.util
from pathlib import Path


def _load_main():
    root = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("main_routing", root / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_routing():
    m = _load_main()
    small_diff = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
    r = m.classify_direct_execution_route(
        "aendere zeile in frontend/app.js", "local", "safe", True, small_diff, True
    )
    assert r[0] == "direct_execute", r
    r2 = m.classify_direct_execution_route(
        "loesche alle logs", "local", "safe", True, small_diff, True
    )
    assert r2[0] == "safe_review", r2
    huge = "\n".join(["x"] * 300)
    r3 = m.classify_direct_execution_route("refactor", "local", "safe", True, huge, True)
    assert r3[0] == "safe_review", r3
    r4 = m.classify_direct_execution_route("x", "local", "safe", True, small_diff, False)
    assert r4[0] == "safe_review", r4


if __name__ == "__main__":
    test_routing()
    print("plan_routing_ok")
