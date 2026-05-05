# Builder Mode für Rambo Rainer

## Zweck

Rambo erkennt, wenn der Nutzer etwas bauen oder programmieren lassen will, und liefert strukturierte Metadaten (Fähigkeiten, Dev-Workflow, Antwort-Vorlage) für Clients.

## Ablauf

1. Nutzer schreibt z. B. „Bau mir eine App“ oder „Kannst du mir ein Tool programmieren?“
2. `POST /api/builder-mode` mit JSON `{ "input": "…" }` prüft Teilstring-Matches gegen `intent_triggers` in `builder_mode.json` (Eingabe wird kleingeschrieben verglichen).
3. Clients können Ton und UI anpassen (z. B. Builder-Badge), ohne `state.json` oder `memory.json` zu ändern.

## Konfiguration

- Datei: `backend/builder_mode.json`
- `builder_mode.enabled`: global ein/aus
- `intent_triggers`: Liste deutscher Trigger-Phrasen (Kleinbuchstaben empfohlen; Vergleich erfolgt auf lowercased Nutzertext)

## API

- **URL:** `POST /api/builder-mode`
- **Body:** `{ "input": "<Nutzertext>" }`
- **Antwort bei Intent:** `builder_mode_active: true`, `intent_recognized: true`, `capability`, `dev_workflow`, `response_template`, `message`
- **Ohne Intent:** `builder_mode_active: false`, `intent_recognized: false`
- Kein Admin-Header nötig.

## Dev-Workflow (Empfehlung im Builder-Kontext)

1. Neu starten (Backend/Frontend sauber)
2. Fehler prüfen (Logs/Console)
3. Fehler beheben (kleinster Schritt)
4. Testen (relevant für die Änderung)
5. Erst weitermachen, wenn stabil

## Frontend (optional)

Hilfsfunktion: `frontend/src/services/builderMode.js` — Aufruf von `checkBuilderMode(apiBase, text)` ohne Änderung an `App.jsx`/`App.css`.
