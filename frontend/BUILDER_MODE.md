# Builder-Mode UI für Rambo Rainer

## Für Nutzer

### Zugriff
- Klick auf "🏗️ Builder-Mode" Button (oben rechts)
- Oder: Ctrl+? (Tastenkombination)

### Workflow
1. **App-Type wählen**
   - Web App (React + Flask)
   - CLI Tool (Python)
   - Dashboard (WebSocket)

2. **App-Name eingeben**
   - z.B. "mein_projekt"

3. **Build starten** 🚀
   - Rambo analysiert
   - Generiert Boilerplate
   - Schreibt Dateien
   - Führt Tests aus

4. **Ergebnis sehen**
   - ✅ Success: Anzahl Dateien + Test-Status
   - ❌ Error: Fehler-Details

## Für Entwickler

### Komponenten
- `BuilderModeIndicator.jsx` - Main-Komponente
- `BuilderModeIndicator.css` - Styling
- Tests in `__tests__/`

### API-Endpoints
- `/api/coach/next-step` (Phase D)
- `/api/scaffold` (Phase B)
- `/api/generate/write-files` (Phase E)
- `/api/build-full` (Phase F)

### Keyboard-Shortcut
- Ctrl+? öffnet Builder-Dialog (hardcoded in useEffect)

### Admin-Header
- Requests nutzen `X-Rambo-Admin` mit demselben Token wie im restlichen Frontend (vgl. `App.jsx`).
