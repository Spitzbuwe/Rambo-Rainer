def run(prompt: str) -> dict:
    return {"ok": True, "worker": "review", "summary": f"review aggregation: {prompt[:80]}"}
