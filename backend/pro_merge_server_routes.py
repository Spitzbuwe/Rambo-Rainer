# -*- coding: utf-8 -*-
"""Registriert Routen aus server.py auf der Flask-App von main.py ohne Methoden-Konflikte."""

from __future__ import annotations

from typing import Any


def _methods(rule: Any) -> set[str]:
    raw = rule.methods or set()
    return {m for m in raw if m not in ("HEAD", "OPTIONS")}


def _collect_main_methods(main_app: Any) -> dict[str, set[str]]:
    by_path: dict[str, set[str]] = {}
    for rule in main_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        p = str(rule.rule)
        by_path.setdefault(p, set()).update(_methods(rule))
    return by_path


def attach_rambo_server_routes(main_app: Any) -> int:
    """
    Übernimmt URL-Regeln aus dem separaten Rambo-/Pro-server-Modul.
    Wenn main.py dieselbe Route + Methode bereits hat, gilt main (Rainer-Build) als maßgeblich.
    """
    import server as rambo_srv  # noqa: WPS433

    main_by_path = _collect_main_methods(main_app)
    added = 0
    seen_ep: set[str] = set(frozenset(main_app.view_functions.keys()))
    for rule in rambo_srv.app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = str(rule.rule)
        srv_m = _methods(rule)
        if not srv_m:
            continue
        occupied = main_by_path.get(path, set())
        add_m = srv_m - occupied
        if not add_m:
            continue
        view = rambo_srv.app.view_functions.get(rule.endpoint)
        if view is None:
            continue
        base_ep = f"rambo_{rule.endpoint}"
        ep = base_ep
        n = 0
        while ep in seen_ep:
            n += 1
            ep = f"{base_ep}_{n}"
        seen_ep.add(ep)
        main_app.add_url_rule(
            path,
            endpoint=ep,
            view_func=view,
            methods=sorted(add_m),
            strict_slashes=getattr(rule, "strict_slashes", True),
        )
        main_by_path.setdefault(path, set()).update(add_m)
        added += 1
    return added
