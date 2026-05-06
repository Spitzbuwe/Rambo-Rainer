# Rainer-Pro — Entwicklungsplan

**Ziel:** Cursor/Codex-Qualität mit lokalem + Groq-Backend.

**Dokument im Repo:** `docs/rainer_pro_entwicklungsplan.md`  
**Letzte Aktualisierung:** 06.05.2026 — Phase 1.1 intelligent-run ↔ direct-run Hub

---

## STATUS (Code-Stand, nicht nur Wunschliste)

### Erledigt / deutlich verbessert

| Thema | Kurz |
|--------|------|
| Große Dateien | Env `AGENT_MAX_FILE_SIZE_BYTES` (Default `-1`), Reader in `main.py` env-basiert |
| Guard + Auto-Recovery | `unsafe_large_rewrite` → interne Step-Engine bei validiertem kleinen Patch (`backend/main.py`) |
| Prompt-vs-Code (Backend) | `agent_file_guard.py`; **zusätzlich** `agent_loop._content_looks_like_instruction_dump` vor Writes |
| Bild-Generator | `POST /api/image/generate`, `GET /api/generated-media/…`, Frontend-Intent (`OPENAI_API_KEY` / `RAINER_IMAGE_API_KEY`) |
| UTF-8 / UI-Mojibake | `frontend/src/App.jsx` bereinigt; Hilfsskript `scripts/fix_appjsx_mojibake.py` |
| Polling / Proxy | `apiFetchWithRetry` für `/api/status` |
| Prozesshygiene | `start-backend.bat` (Health vor Start), `stop-backend.bat`, Doppelstart in `main.py` optional vermeidbar |
| Check-Pipeline | `check.ps1` mit Pytest, Vitest, Build-Retry, `check-report.txt` |
| **Phase 1.2 Groq-Klassifikation** | `classify_with_groq()` → `change` \| `analysis` \| `chat` \| `unknown`, Timeout 3s, `max_tokens` 5; **Risky zuerst**, kein zweites Groq bei `unknown`-Fallback (`prompt_routing.py`) |
| **Phase 1.3 SUCHE-Recovery** | Bis zu `AGENT_SUCHE_REPAIR_ATTEMPTS` (Default 2) Groq-Neuauflage des SUCHE-Blocks (`agent_loop.py`) |
| **Phase 1.4 Prompt-Guard im Loop** | Blockiert verdächtigen ERSETZE/<<NEU>>-Inhalt vor Write |
| **MAX_REPAIR_ATTEMPTS** | Agent-Loop-Reparatur: 2 Versuche |

### Noch offen (Roadmap)

| Phase | Inhalt |
|--------|--------|
| **1.1 Ein Pfad** | *teilweise:* `/api/intelligent-run` → gleiche Pipeline wie `/api/direct-run` (interner Aufruf); Ausnahme `implementation: true` → weiterhin `execute_intelligent`. Builder/electron-Zweige weiterhin in `direct-run`. |
| **2.x** | Session-Kontext, Multi-Datei-Plan, LLM-Dateiwahl, Analyse-Antwort immer als Chat-Text, Workspace strikt |
| **3.x** | 3D-Designer produktiv, Office-Export, Git-UI, Terminal stabil |
| **4.x** | E2E `tests/test_e2e_real_prompts.py` mit echten Nutzer-Prompts als CI-Gate; Smoke nach Start |

---

## PHASE 1 — STABILER KERN *(Priorität: HOCH)*

Ziel: Jeder Prompt landet zuverlässig beim richtigen Handler.

### 1.1 Einziger Ausführungspfad

- **Problem:** Mehrere parallele Pfade (direct-run, agent-loop, Builder).
- **Lösung:** Zentral über `agent_loop.py` + Groq; `direct-run` → nach Klassifikation `AgentLoop.run` / `run_analysis` / Chat.
- **Dateien:** `backend/main.py`, `backend/agent_loop.py`
- **Status:** *teilweise* — `intelligent-run` hub mit `direct-run`; optional Builder/Verschmelzung weiterer Zweige offen.

### 1.2 Prompt-Klassifikation via Groq

- **Umsetzung:** `classify_with_groq` in `backend/prompt_routing.py`; `classify_user_prompt` nutzt **zuerst** `_is_risky_user_intent`, dann Groq, bei `unknown` nur **Heuristik** (ohne zweites Groq). `classify_user_prompt_intent` bleibt für Legacy: Risky + Groq-Analyse + Heuristik.
- **Konfiguration:** `GROQ_API_KEY`, optional `GROQ_MODEL` (Default `llama-3.3-70b-versatile`).

### 1.3 Auto-Recovery bei SUCHE-Fehler

- **Umsetzung:** `_groq_regenerate_suche_patch` + Schleife in `AgentLoop._parse_and_write`; Env `AGENT_SUCHE_REPAIR_ATTEMPTS`, `AGENT_SUCHE_FIX_CONTEXT_CHARS`.

### 1.4 Prompt-Guard (kein Anweisungstext als Code)

- **Umsetzung:** `_content_looks_like_instruction_dump` in `agent_loop.py` vor relevanten Writes; ergänzend `agent_file_guard` für andere Pfade.

### 1.5 Große Dateien

- **Status:** erledigt (siehe STATUS-Tabelle).

---

## PHASE 2 — QUALITÄT *(MITTEL)*

*(unverändert zur ursprünglichen Planung: Session, Multi-Datei, Scanner, Analyse-Modus, Workspace — siehe historische Notizen im Chat.)*

---

## PHASE 3 — FEATURES *(NIEDRIG)*

- Bild: produktiver Pfad siehe STATUS; ggf. Groq nur für Prompt-Verfeinerung ergänzen.
- 3D, Office, Git-UI, Terminal: wie im Originalplan.

---

## PHASE 4 — STABILITÄT *(DAUERHAFT)*

- E2E-Tests mit echten Prompts (`tests/test_e2e_real_prompts.py`).
- Smoke nach Start, Rollback optional über Git.

---

## TECHNISCHER STACK

| Komponente | Technologie |
|------------|-------------|
| LLM Primary | Groq (`llama-3.3-70b-versatile` o. `GROQ_MODEL`) |
| LLM Fallback | lokal je nach `model_providers` / Ollama |
| Backend | Flask, Python 3.11 |
| Frontend | React, Vite |
| Ports | Backend 5002, Frontend 5173 |
| Workspace | z. B. `D:\Rainer-Pro` |
| Config | `.env` im Root |

---

## REIHENFOLGE (Cursor)

1. **Jetzt:** Phase 1.2–1.4 im Code (siehe STATUS „Erledigt“).
2. **Als Nächstes:** 1.1 einheitlicher `main.py`-Pfad + E2E-Gate (Phase 4).
3. Danach Phase 2 nach Bedarf.

---

## Cursor-Starter-Prompt (aktualisiert)

```
Arbeite in D:\Rainer-Pro.

ZIEL: Phase 1.1 — einen einzigen deterministischen Ausführungspfad in backend/main.py.

- Nach classify_user_prompt / classify_with_groq:
  project_task → AgentLoop.run
  project_read → AgentLoop.run_analysis (oder dedizierter Read-Pfad ohne Write)
  chat → direkte LLM-Antwort ohne Dateizugriff
- Risky → bestehende Sperre beibehalten.
- Alte parallele Zweige (wo sicher) auf diese Dreiteilung abbilden oder deaktivieren.
- Tests: neue E2E mit 3–5 echten Prompts; python -m py_compile; Commit.
```

---

*Ursprünglich erstellt: 06.05.2026 — als Nutzer-Entwurf aus Downloads übernommen und mit Repo-Stand synchronisiert.*
