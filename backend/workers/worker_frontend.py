def run(prompt: str) -> dict:
    return {"ok": True, "worker": "frontend", "summary": f"frontend analysis: {prompt[:80]}"}
