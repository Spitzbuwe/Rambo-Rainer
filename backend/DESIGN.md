# Design-Generierung für CorelDRAW (Phase J.2)

Rambo erzeugt **SVG**-Dateien (optional **EPS**), die sich in **CorelDRAW** öffnen und weiterbearbeiten lassen.

## Formate

| Format | Nutzung |
|--------|---------|
| **SVG** | Primär; gut editierbar, üblicher Import in CorelDRAW |
| **EPS** | Optional; wird bei erfolgreicher ReportLab-EPS-Erzeugung zusätzlich unter dem gleichen Basisnamen abgelegt |

Ausgabe: **`backend/output/designs/`**

## Endpoints

### `POST /api/generate/svg-design`

**Header:** `X-Rambo-Admin: <Token>`

**Body (JSON):**

```json
{
  "template_type": "business_card",
  "variables": {
    "name": "Max Mustermann",
    "title": "Senior Designer",
    "email": "max@example.com"
  },
  "width": 90,
  "height": 50,
  "content": "Freitext für Platzhalter content",
  "colors": { "fill": "#FF0000" }
}
```

`width` / `height` überschreiben die Maße aus dem Template (gleiche Einheit wie im Template: `mm` oder `px`).

**Antwort (Erfolg):**

```json
{
  "status": "success",
  "file": "business_card_20260419_120000.svg",
  "path": "…\\backend\\output\\designs\\…",
  "format": "SVG",
  "eps_file": "business_card_20260419_120000.eps",
  "eps_path": "…"
}
```

`eps_*` nur, wenn EPS erzeugt werden konnte.

### `POST /api/generate/design-template`

**Header:** `X-Rambo-Admin`

**Body:**

```json
{
  "design_type": "flyer",
  "brand_style": "modern",
  "variables": { "title": "Mein Flyer", "content": "Text" }
}
```

Nutzt dieselbe SVG-Engine wie `svg-design`, ergänzt Branding-Variablen (`brand_primary`, `brand_secondary`) aus `design_templates.json`.

### `GET /api/generate/design-templates`

Ohne Admin-Header. Liefert Schlüssel und Metadaten:

```json
{
  "svg_templates": ["business_card", "flyer", "logo_background"],
  "brand_colors": ["default", "modern"],
  "template_details": {
    "business_card": {
      "full_name": "Visitenkarte",
      "width": 90,
      "height": 50,
      "unit": "mm"
    }
  }
}
```

## Platzhalter in Templates

Im JSON stehen Texte wie `[Name]`, `[Title]`, `[LOGO]`. Beim Rendern werden sie durch Einträge in `variables` ersetzt (Schlüssel z. B. `name`, `title`, `logo` – Groß-/Kleinschreibung wird mehrfach abgedeckt).

## CorelDRAW

1. **Datei → Öffnen** → SVG (oder EPS) aus `backend/output/designs/` wählen.  
2. Objekte bearbeiten, bei Bedarf als **CDR** speichern.

## Konfiguration

- Vorlagen: **`design_templates.json`**
- Logik: **`services/design_generator.py`**
- Abhängigkeiten: **`svgwrite`**, **`reportlab`** (`requirements.txt`)

## Tests

```powershell
cd backend
pytest tests/test_design_generator.py -v
```
