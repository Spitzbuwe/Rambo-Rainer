# Orchestration: Phasen D + E + F zusammen

## Zweck

`POST /api/build-full` orchestriert einen zusammenhängenden Build-Prozess:

1. Coach: Kontext / nächster Schritt (logisch)
2. Scaffold: Template + Code-Snippets aus `scaffold_templates.json`
3. Generate: Dateien unter `base_path` schreiben
4. Dev-Workflow: Health-Checks (in-process), pytest
5. Coach: Abschluss-Summary in der Antwort

## Input

```json
{
  "app_type": "web_app",
  "app_name": "my_awesome_app",
  "features": ["websocket", "docker"],
  "base_path": "C:/Users/mielersch/Desktop/Rambo-Rainer"
}
```

## Output (Beispiel)

```json
{
  "orchestration_id": "abc12345",
  "final_status": "success",
  "stages": {
    "stage_1_coach": {},
    "stage_2_scaffold": {},
    "stage_3_generate": {},
    "stage_4_dev_workflow": {},
    "stage_5_final_coach": {}
  },
  "summary": {
    "files_written": 5,
    "errors": 0,
    "tests_passed": true,
    "app_ready": true
  }
}
```

HTTP: `200` bei Erfolg, `207` bei Teil-Erfolg, `500` bei hartem Fehler.

## API

- **Methode:** `POST`
- **Pfad:** `/api/build-full`
- **Body:** `app_type`, `app_name`, optional `features`, `base_path` (Standard: Projekt-Root `BASE_DIR`)
