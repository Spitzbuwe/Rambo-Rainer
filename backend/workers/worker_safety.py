def run(prompt: str) -> dict:
    return {"ok": True, "worker": "safety", "summary": f"safety checks: {prompt[:80]}"}
