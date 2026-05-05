# Dev-Workflow für Rambo Rainer

## Zweck

`POST /api/dev-workflow` führt einen dokumentierten Entwicklungszyklus aus: geplanter Neustart (ohne Selbst-Terminierung des laufenden Backends), HTTP-Checks, konservative „Fix“-Hinweise und **pytest** im Ordner `backend/tests/`.

## Phasen

| Action / Teil von `full_cycle` | Inhalt |
|-------------------------------|--------|
| `restart` | Gibt geplante Schritte aus `dev_workflow.json` zurück; **kein** automatischer Prozess-Kill aus dem laufenden Server. |
| `check_errors` | Führt die Checks aus der Konfiguration aus (u. a. `/api/health`, optional Frontend-URL, `POST /api/builder-mode`). |
| `fix_errors` | Bei gesammelten Fehlern: Hinweise; optional `pip install -r backend/requirements.txt`, wenn **`DEV_WORKFLOW_ALLOW_PIP=1`** gesetzt ist. |
| `run_tests` | `python -m pytest tests/ …` mit Arbeitsverzeichnis `backend/`. |
| `full_cycle` | `restart` → `check_errors` → bei Fehlern `fix_errors` → `run_tests`. |

## Konfiguration

- Datei: **`backend/dev_workflow.json`**
- **`session_tracking`:** Kurze Einträge in **`data/state.json`** unter **`dev_sessions`** (max. 50), sofern aktiviert.

## API

**`POST /api/dev-workflow`**

- Header: **`X-Rambo-Admin`** (wie andere Admin-Routen)
- Body: `{ "action": "restart" | "check_errors" | "run_tests" | "fix_errors" | "full_cycle" }` (Standard: `full_cycle`)

**`overall_status`:** `success` | `fixed_and_stable` | `attention_required` | `error`

## Hinweise Windows

- Port freimachen: `netstat -ano | findstr :<PORT>` und `taskkill /PID <pid> /F`
- Frontend-Check nutzt standardmäßig `http://localhost:5173`; wenn der Dev-Server woanders läuft, schlägt dieser Check fehl — Workflow meldet dann `attention_required`, Backend-Tests können trotzdem grün sein.

## Praxis

1. Nach Scaffold oder größeren Änderungen: `full_cycle` aufrufen.
2. Bei `attention_required`: `phases.check_errors.failures` und `phases.run_tests` prüfen.
3. Backend/Frontend bei Bedarf **manuell** neu starten (nicht durch den Endpoint erzwungen).
