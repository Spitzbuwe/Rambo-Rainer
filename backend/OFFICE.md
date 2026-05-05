# Office-Dokumente (Phase J.1)

Rambo Rainer kann **Word** (`.docx`), **Excel** (`.xlsx`) und **PowerPoint** (`.pptx`) erzeugen. Vorlagen liegen in `document_templates.json`, Ausgabedateien unter `backend/output/` (Verzeichnis wird angelegt).

## Abhängigkeiten

- `python-docx`
- `openpyxl`
- `python-pptx`

Siehe `requirements.txt`.

## Endpoints

### `POST /api/generate/word-document`

**Header:** `X-Rambo-Admin: <Token>`

**Body (JSON):**

```json
{
  "template_type": "letter",
  "title": "Geschäftsbrief",
  "content": "Inhalt des Briefes",
  "author": "Optional"
}
```

**Antwort (Erfolg):**

```json
{
  "status": "success",
  "file": "letter_20260419_120000.docx",
  "path": "C:\\...\\backend\\output\\letter_....docx"
}
```

Vorlagen: `letter`, `report` (siehe `document_templates.json`).

---

### `POST /api/generate/excel-sheet`

**Header:** `X-Rambo-Admin`

**Body:**

```json
{
  "template_type": "budget",
  "data": {
    "Einnahmen": [[100, 200], [300, 400]]
  },
  "formulas": {
    "Zusammenfassung!B2": "=Einnahmen!B1"
  }
}
```

`data` und `formulas` sind optional; Standard-Formeln kommen aus dem Template.

---

### `POST /api/generate/powerpoint`

**Header:** `X-Rambo-Admin`

**Body:**

```json
{
  "template_type": "presentation",
  "slides": [
    {"type": "title", "title": "Projekt", "subtitle": "2026"},
    {"type": "content", "title": "Agenda", "content": "Punkte …"}
  ]
}
```

Ohne `slides` werden die Folien aus dem Template übernommen.

---

### `GET /api/generate/office-templates`

Liefert die Schlüssel der verfügbaren Vorlagen (ohne Admin-Header).

```json
{
  "word_templates": ["letter", "report"],
  "excel_templates": ["budget", "invoice"],
  "powerpoint_templates": ["presentation"]
}
```

## Ablauf

1. `GET /api/generate/office-templates` — verfügbare `template_type`-Werte
2. Gewünschten `POST`-Endpunkt mit JSON aufrufen
3. Datei aus `path` bzw. `backend/output/` verwenden

## Tests

```powershell
cd backend
pytest tests/test_office_generator.py -v
```
