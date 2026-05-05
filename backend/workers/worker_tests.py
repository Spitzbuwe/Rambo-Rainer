def run(prompt: str) -> dict:
    return {"ok": True, "worker": "tests", "summary": f"test mapping: {prompt[:80]}"}
