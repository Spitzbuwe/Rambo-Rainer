# Coach-Engine für Rambo Rainer

## Zweck

Nach jedem Dev-Workflow oder Scaffold schlägt der Coach intelligent den nächsten kleinsten Schritt vor.

## Intelligenz-Merkmale

- **Context Awareness**: Liest `data/state.json`, versteht den aktuellen Stand (Felder wie `structure`, `scaffold_done`, …).
- **Step Prioritization**: Wählt nur einen sinnvollen Schritt nach Priorität.
- **Risk Assessment**: Kennt typische Risiken und Mitigationen aus `coach_engine.json`.
- **Learning from State**: Passt Vorschläge an den gespeicherten Progress an.

## Step-Prioritäten

1. State leer → Scaffold anlegen
2. Scaffold da → Dateien generieren
3. Dateien da → Tests schreiben
4. Tests da → Dev-Workflow ausführen
5. Alles stabil → Nächste Feature

## API

`POST /api/coach/next-step`

**Input:** `{ "context": "optional" }`

**Output (Beispiel):**

```json
{
  "next_step": {
    "priority": 1,
    "name": "Wenn state.json leer: Scaffold anlegen",
    "action": "Implement",
    "condition_met": true
  },
  "current_state": {
    "scaffold_done": false,
    "files_created": false,
    "tests_written": false,
    "dev_workflow_done": false,
    "stable": false
  },
  "detected_risks": [],
  "recommendation": "…",
  "template_response": "…"
}
```
