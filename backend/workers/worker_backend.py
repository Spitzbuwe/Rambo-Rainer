def run(prompt: str) -> dict:
    return {"ok": True, "worker": "backend", "summary": f"backend analysis: {prompt[:80]}"}
