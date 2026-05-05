# App Scaffold für Rambo Rainer

## Zweck

Wenn ein Nutzer z. B. „Bau mir eine Web App“ sagt und der Builder-Intent erkannt wurde (`/api/builder-mode`), liefert **`POST /api/scaffold`** einen konkreten Plan:

- empfohlene Architektur (Stack, Beschreibung)
- Verzeichnis-/Dateibaum (`directories`)
- vorgeschlagene Dateien inkl. **Boilerplate-Code** (`files[].code`)
- **first_steps** und **estimated_duration**

Es werden **keine Dateien auf der Platte angelegt** — nur die Spezifikation für Client oder Agent.

## Unterstützte App-Typen

| `app_type`   | Inhalt |
|-------------|--------|
| `web_app`   | React + Flask SPA, SQLite, optional Docker |
| `tool`      | Python-CLI (Argparse) |
| `dashboard` | Monitoring-UI, WebSocket-Hooks |

## API

**`POST /api/scaffold`**

**Body (JSON):**

```json
{
  "app_type": "web_app",
  "app_name": "mein_projekt",
  "features": ["websocket", "docker"]
}
```

- `features` (optional): z. B. `websocket` → `additional_setup` mit pip/npm-Hinweisen; `docker` → `docker_compose` aus dem Template (boolean).

**Antwort (Auszug):**

- `app_name`, `app_type`, `template` (Metadaten aus `scaffold_templates.json`)
- `directories`, `files` (Liste mit `path`, `template`, `description`, `code`)
- `first_steps`, `estimated_duration`
- optional: `additional_setup`, `docker_compose`

Konfiguration: **`backend/scaffold_templates.json`**

## Workflow

1. Intent prüfen: `POST /api/builder-mode`
2. Scaffold holen: `POST /api/scaffold`
3. Dateien lokal anlegen und Code einfügen
4. Tests schreiben / ausführen
5. Backend/Frontend neu starten und manuell testen
