# Code-Generation für Rambo Rainer

## Zweck

`POST /api/generate/write-files` schreibt Code-Dateien auf die Festplatte (UTF-8) und aktualisiert `data/state.json` (`files_created`, `last_generation`).

## Workflow

1. Scaffold generieren (`POST /api/scaffold`) → Plan + Code-Snippets
2. Dateien schreiben (`POST /api/generate/write-files`) → Dateien auf Disk
3. State aktualisieren → `files_created = true` (wenn mindestens eine Datei geschrieben wurde)
4. Dev-Workflow ausführen (`POST /api/dev-workflow`) → Checks, Tests

## API

**Input:**

```json
{
  "app_name": "my_app",
  "app_type": "web_app",
  "files": [
    {"path": "src/main.py", "code": "..."},
    {"path": "frontend/App.jsx", "code": "..."}
  ],
  "base_path": "C:/Users/mielersch/Desktop/Rambo-Rainer"
}
```

**Output:**

```json
{
  "status": "success",
  "written_files": [],
  "errors": [],
  "summary": {
    "total_attempted": 0,
    "successfully_written": 0,
    "failed": 0,
    "app_name": "my_app",
    "app_type": "web_app"
  }
}
```

HTTP: `200` bei `success`, `207` bei `partial` (teilweise Fehler).

## State Tracking

Nach der Generierung werden in `data/state.json` ergänzt:

```json
{
  "files_created": true,
  "last_generation": {
    "timestamp": "...",
    "app_name": "my_app",
    "app_type": "web_app",
    "files_written": 5,
    "errors": 0
  }
}
```

Bestehende Keys (z. B. `rambo`) bleiben erhalten.
