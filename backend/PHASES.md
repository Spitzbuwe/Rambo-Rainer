# Phasen A–G – Rambo Rainer (Überblick)

Dieses Dokument fasst die **Builder- und Coding-Pipeline** grob zusammen. **JSON-Beispiele** sind illustrativ; echte Felder können vom Backend abweichen – Verhalten und Schemas bitte in `server.py` bzw. den zugehörigen Tests prüfen.

---

## Phase A: Capability + Coding-Intent

**Zweck:** Erkennen, ob der Nutzer in den „Builder“-Kontext wechseln will.

**Endpoint (Beispiel):** `POST /api/builder-mode`

**Input (Beispiel):**

```json
{ "input": "Bau mir eine Web App" }
```

**Output (Beispiel):**

```json
{
  "builder_mode_active": true,
  "intent_recognized": true,
  "capability": "Ja, ich kann..."
}
```

---

## Phase B: Scaffold (App-Vorlagen)

**Zweck:** Architektur bzw. Boilerplate als Dateiliste / Metadaten liefern.

**Endpoint:** `POST /api/scaffold`

**Input (Beispiel):**

```json
{
  "app_type": "web_app",
  "app_name": "mein_projekt",
  "features": []
}
```

**Output (Beispiel):**

```json
{
  "files": [{ "path": "...", "code": "...", "description": "..." }],
  "first_steps": [],
  "estimated_duration": "45 Minuten"
}
```

---

## Phase C: Dev-Workflow

**Zweck:** Workflow-Schritte wie Tests, Diagnose oder Wiederanlauf (je nach Implementierung).

**Endpoint (Beispiel):** `POST /api/dev-workflow`

**Ablauf (konzeptionell):**

1. Umgebung prüfen / neu starten (falls vorgesehen)  
2. Fehler oder Health auswerten  
3. Ggf. automatische Korrektur oder Report  
4. Tests oder Teiltests ausführen  

---

## Phase D: Coach-Engine

**Zweck:** Vorschlag für den **nächsten sinnvollen Schritt**.

**Endpoint:** `POST /api/coach/next-step`

**Input (Beispiel):** `{}` oder kontextabhängige Felder

**Output (Beispiel):**

```json
{
  "next_step": {
    "priority": 1,
    "name": "Scaffold anlegen",
    "action": "Implement"
  },
  "detected_risks": []
}
```

---

## Phase E: Code-Generation

**Zweck:** Übergebene Dateien **auf die Festplatte schreiben** (innerhalb erlaubter Pfade).

**Endpoint:** `POST /api/generate/write-files`

**Input (Beispiel):**

```json
{
  "app_name": "mein_projekt",
  "app_type": "web_app",
  "files": [{ "path": "...", "code": "..." }],
  "base_path": "."
}
```

**Output (Beispiel):**

```json
{
  "status": "success",
  "written_files": [],
  "errors": []
}
```

---

## Phase F: Orchestrierung (Build-Full)

**Zweck:** Mehrere Schritte (Coach, Scaffold, Generate, Workflow, …) in **einem** Lauf bündeln.

**Endpoint:** `POST /api/build-full`

**Input (Beispiel):**

```json
{
  "app_type": "web_app",
  "app_name": "mein_projekt",
  "features": []
}
```

**Output (Beispiel):**

```json
{
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
    "tests_passed": true,
    "errors": 0
  }
}
```

**Auth:** wie andere Admin-Routen – Header **`X-Rambo-Admin`**.

---

## Phase G: Builder-Mode UI

**Zweck:** Steuerung und Fortschritt für den Build im Browser.

**Komponente:** `frontend/src/components/BuilderModeIndicator.jsx`

**Features:**

- Badge (oben rechts)  
- Modal mit Formular (App-Typ, App-Name)  
- Fortschrittsanzeige  
- Erfolg- und Fehlerzustände  
- Tastenkürzel (siehe [frontend/BUILDER_MODE.md](../frontend/BUILDER_MODE.md))  

---

## Zusammenfassung (Flow)

```text
Intent / Builder-Mode (A)
        ↓
Scaffold (B)
        ↓
Dev-Workflow (C)  ←── je nach Orchestrierung eingebunden
        ↓
Coach (D)
        ↓
Dateien schreiben (E)
        ↓
Build-Full / Orchestrierung (F)
        ↓
Darstellung in der UI (G)
```

---

## Siehe auch

- [README.md](../README.md) – Schnellstart und Links  
- [ARCHITECTURE.md](../ARCHITECTURE.md) – Ports und Schichten  
- [frontend/BUILDER_MODE.md](../frontend/BUILDER_MODE.md) – Nutzerhinweise zur UI  
