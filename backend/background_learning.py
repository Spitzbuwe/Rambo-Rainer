from __future__ import annotations

import os
import threading
import time
from datetime import datetime

from auto_analyzer import AutoAnalyzer

_BACKGROUND_THREAD = None
_BACKGROUND_LOCK = threading.Lock()


def log_learning_progress(db_path, analysis: dict):
    from pathlib import Path
    import json

    path = Path(db_path)
    if not path.exists():
        return
    try:
        db = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    db.setdefault("learning_progress", []).append({
        "kind": "background_analysis",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "snapshot": analysis,
    })
    path.write_text(json.dumps(db, ensure_ascii=True, indent=2), encoding="utf-8")


def background_learning_loop(db_path):
    analyzer = AutoAnalyzer(db_path=db_path)
    interval = int(os.getenv("RAINER_BG_LEARNING_INTERVAL_SEC", "3600"))
    if interval < 30:
        interval = 30
    while True:
        time.sleep(interval)
        analysis = analyzer.analyze_automatically()
        analyzer.auto_update_preferences(analysis)
        log_learning_progress(db_path, analysis)


def start_background_learning(db_path):
    global _BACKGROUND_THREAD
    with _BACKGROUND_LOCK:
        if _BACKGROUND_THREAD and _BACKGROUND_THREAD.is_alive():
            return _BACKGROUND_THREAD
        _BACKGROUND_THREAD = threading.Thread(
            target=background_learning_loop,
            args=(str(db_path),),
            daemon=True,
            name="rainer-passive-learning",
        )
        _BACKGROUND_THREAD.start()
        return _BACKGROUND_THREAD
