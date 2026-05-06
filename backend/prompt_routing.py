"""
Zentrale Prompt-Klassifikation: Chat / Projektaufgabe / riskant / unklar.

Keine Flask-Abhaengigkeit. Reihenfolge in classify_user_prompt_intent ist kritisch:
zuerst riskant, dann reiner Chat (inkl. Textaufgaben), dann Projekt-Arbeit.
"""
from __future__ import annotations

import re
import os
import requests

# --- Riskant (blockieren / explizite Bestaetigung) ---
_RISKY_PATTERNS = (
    r"\blösche\b.*\b(projekt|ordner|verzeichnis|repo|alles|komplett)\b",
    r"\b(loesche|delete)\b.*\b(projekt|ordner|verzeichnis|repo|alles|komplett)\b",
    r"\b(delete|rm\s+-rf)\b.*\b(project|folder)\b",
    r"\brm\s+-rf\b",
    r"\b(git\s+push|git\s+merge|git\s+reset\s+--hard)\b",
    r"\b(api[_-]?key|secret|password|token)\s*[=:]\s*",
    r"\bformatier(?:e|ung)?\s+(das\s+)?laufwerk\b",
    r"\bveröffentlich|veroeffentlich|publish\b.*\b(app|paket|production)\b",
    r"\bschreib\b.*\baußerhalb\b.*\b(project|projekt)\b",
    r"\boutside\b.*\bproject\b.*\b(write|save)\b",
)

_RISKY_LITERAL = (
    "git push",
    "git merge",
    "git reset --hard",
    "reset --hard",
    " komplett löschen",
    " komplett loeschen",
    "alle dateien löschen",
    "alle dateien loeschen",
)

# Klare Kurz-Begruessung / Dialog-Huelle
_GREETING_EXACT = {
    "hallo",
    "hallo rainer",
    "hi",
    "hey",
    "servus",
    "moin",
    "guten morgen",
    "guten tag",
    "guten abend",
    "wie gehts",
    "was kannst du",
    "bist du da",
    "danke",
    "ok",
    "ja",
    "nein",
    "tschüss",
    "tschuess",
    "bye",
}

# Explizite Chat-/Erklaer-Muster (vor Coding pruefen)
_CHAT_PATTERNS = (
    r"^\s*(hallo|hi|hey|servus|moin)\s*[!?. ]*$",
    r"\b(wie geht|wie gehts|was machst du|was machen wir|was tun wir)\b",
    r"\b(erklär mir|erklaer mir|was bedeutet|was ist)\b",
    r"\b(warum kommt|warum tritt|wieso kommt).*\b(fehler|error)\b",
    r"\b(fasse zusammen|formuliere um|paraphras)\b",
    r"\b(schreib mir einen text|schreib mir text|text schreiben)\b",
    r"\bcodex[- ]?prompt\b",
    r"\b(gib mir einen codex|prompt fuer codex|prompt für codex)\b",
    r"\b(was soll ich jetzt|was soll ich tun|welcher schritt)\b",
    r"\b(ist das richtig|stimmt das so|kann ich abbrechen)\b",
    r"\b(was macht dieser|was tut dieser).*\b(powershell|cmd|bash|terminal)\b",
    r"\b(welche datei ist betroffen|welche datei meinst)\b",
    r"\brainer\b.*\b(wie funktioniert|was kann|kurz erklärt)\b",
    r"\b(allgemeine frage|nur frage|reine frage)\b",
)

# Text-/Lernaufgabe ohne Dateizugriff
_TEXT_TASK = (
    r"\b(schreib mir einen absatz|schreib einen kurzen text|aufsatz|zusammenfassung)\b",
)

# Projekt-/Coding-Arbeit (Dateien, Build, Tests, Refactor)
_PROJECT_PATTERNS = (
    r"\b(ändere|aendere|ersetze|editiere)\s+.+\.(py|js|tsx|jsx|ts|css|html|json|md)\b",
    r"\b(ändere|aendere)\s+.+\b(backend/|frontend/|src/|tests/)",
    r"\b(mache|mach)\s+.+\b(blau|rot|grün|gruen|schwarz|weiss|weiß|gelb|farbe|färbe|header|footer|titel|navbar|navigation|button|hintergrund|schrift|css|ui)\b",
    r"\b(mache|mach)\s+den\s+\b",
    r"\b(entferne|entfernen|lösche|loesche|verstecke|ausblende|blend\w*)\b",
    r"\b(zentrier\w*|zentrum|ausrichten|linksbündig|rechtsbündig)\b",
    r"\b(ergänz\w*|ergaenz\w*|füge|fuege)\s+(zu|noch|einen|eine|den|das)\b",
    r"\b(verschieb\w*|grösser|groesser|kleiner|dicker|dünner|abstand|padding|margin)\b",
    r"\b(fixe|behebe|implementiere|refactor|refaktor|baue ein)\b",
    r"\b(erstelle|lege an|anlegen)\s+.+\b(datei|modul|klasse|komponente|test)\b",
    r"\berstelle\s+(die\s+)?datei\b",
    r"\b(repariere|patch|apply patch)\b",
    r"\b(starte pytest|pytest\b|npm\s+test|npm\s+run\s+test|führe tests)\b",
    r"\b(baue installer|electron-builder|npm\s+run\s+build)\b",
    r"\b(commit plan|git diff|git status)\s+(zeigen|anzeigen|fuer|für)\b",
    r"\b(schreibe|schreib)\s+.+\s+\b(in die datei|in datei|nach datei)\b",
    r"\b(öffne|oeffne)\s+.+\s+und\s+(ändere|aendere|ersetze)\b",
)

# Schwache Projekt-Hinweise — nur wenn nicht schon Chat
_PROJECT_VERBS_SPACE = (
    "ändere ",
    "aendere ",
    "ersetze ",
    "erstelle ",
    "implementiere ",
    "behebe ",
    "fixe ",
    "repariere ",
    "refactor",
    "pytest",
    " npm ",
    "commit plan",
    "apply patch",
    "schreibe in datei",
    "schreib in datei",
    " datei anlegen",
    "baue feature",
    "ui ändern",
    "frontend ändern",
    "backend ändern",
    "mache ",
    "mach ",
    "entferne ",
    "ergänz",
    "füge ",
    "zentrier",
    "verstecke ",
)

_UNCLEAR_WHITELIST = re.compile(
    r"^(mach|mach mal|bitte|tu was|irgendwas|was soll)\s*[!.?]*$",
    re.IGNORECASE,
)


def _is_risky_user_intent(prompt: str) -> bool:
    txt = str(prompt or "").strip().lower()
    if not txt:
        return False
    for pat in _RISKY_PATTERNS:
        if re.search(pat, txt, flags=re.IGNORECASE):
            return True
    if any(s in txt for s in _RISKY_LITERAL):
        return True
    if re.search(r"\b(loesche|lösche)\b.*\b(ganze|ganzen)\b", txt) and (
        "projekt" in txt or "ordner" in txt or "verzeichnis" in txt
    ):
        return True
    if re.search(r"\b(lösche|loesche|delete|entferne)\b.*\b(alle|viele|mehrere)\s+datei", txt):
        return True
    if re.search(r"\brm\s+", txt) and "datei" in txt:
        return True
    return False


def classify_with_groq(task: str) -> str:
    """
    LLM-Intent via Groq (Primärpfad laut Entwicklungsplan).
    Rückgabe: change | analysis | chat | unknown (bei Fehler/Timeout/ohne Key).
    Timeout 3s, max_tokens 5, temperature 0.
    """
    txt = str(task or "").strip()
    if not txt:
        return "unknown"
    key = str(os.environ.get("GROQ_API_KEY") or "").strip()
    model = str(os.environ.get("GROQ_MODEL") or "llama-3.3-70b-versatile").strip()
    if not key:
        return "unknown"
    system_prompt = (
        "Du klassifizierst Nutzeranfragen für ein Coding-Tool. "
        "Antworte NUR mit genau einem Wort, ohne Satzzeichen:\n"
        "change — der Nutzer will Dateien/Projekt ändern, erstellen, Code schreiben\n"
        "analysis — nur erklären, analysieren, verstehen, lesen, Frage ohne Edit\n"
        "chat — reine Unterhaltung, Begrüßung, Meta, kein Projektbezug\n"
        "unknown — du bist dir unsicher"
    )
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": txt},
                ],
                "temperature": 0,
                "max_tokens": 5,
                "service_tier": "on_demand",
            },
            timeout=3,
        )
        resp.raise_for_status()
        payload = resp.json() if resp.content else {}
        choice = ((payload.get("choices") or [{}])[0] or {}).get("message") or {}
        raw = str(choice.get("content") or "").strip().lower()
        for token in ("analysis", "change", "chat", "unknown"):
            if raw.startswith(token):
                return token
        return "unknown"
    except Exception:
        return "unknown"


# Abwärtskompatibel (interne Aufrufer)
_classify_intent_with_llm = classify_with_groq


def should_route_direct_run_as_chat(prompt: str) -> bool:
    """
    Kurze Meta-/Diagnosefragen (App offline, „was macht der Generator“) —
    Chat statt project_read. Groq klassifiziert solche Prompts oft als „analysis“.
    """
    txt = str(prompt or "").strip().lower()
    if not txt:
        return False
    if re.search(r"\büberprüfe\s+warum\b", txt) and any(
        w in txt for w in ("offline", "online", "app", "backend", "nicht erreichbar", "startet", "server")
    ):
        return True
    if ("warum" in txt or "wieso" in txt) and "app" in txt and any(
        w in txt for w in ("offline", "online", "geht nicht", "nicht erreichbar", "down", "läuft nicht", "laeuft nicht")
    ):
        return True
    # „Was macht der/tut der …“ — Typo „generato“; keine explizite Code-/Ordner-Analyse
    if len(txt) <= 130:
        m = re.search(r"\bwas\s+(macht|tut)\s+(der|die|das)\s+(\S+)", txt)
        if m:
            noun = (m.group(3) or "").lower().strip("?.!,\"'")
            if noun.startswith(("projekt", "ordner", "datei", "codebase", "komponent", "workspace")):
                return False
            if re.search(r"\b(analysiere|untersuche\s+den|bewerte\s+den|review\s+die)\b", txt, re.IGNORECASE):
                return False
            return True
    return False


def is_analysis_only_prompt(task: str) -> bool:
    if should_route_direct_run_as_chat(task):
        return False
    return classify_with_groq(task) == "analysis"


def unclear_chat_short_reply() -> str:
    """Sofort-Rückfrage bei vagen Kurzprompts (ohne LLM)."""
    return (
        "Was genau soll ich machen? Beschreib kurz, ob du eine Frage hast oder "
        "ob ich im Projekt etwas ändern soll."
    )


def _classify_user_prompt_intent_heuristic_core(prompt: str) -> str:
    """Regex/Keyword-Intent ohne zweites Groq (für classify_user_prompt-Fallback)."""
    txt = str(prompt or "").strip().lower()
    if not txt:
        return "unknown"

    if txt in _GREETING_EXACT:
        return "greeting"

    for pat in _TEXT_TASK:
        if re.search(pat, txt, flags=re.IGNORECASE):
            return "chat_question"

    for pat in _CHAT_PATTERNS:
        if re.search(pat, txt, flags=re.IGNORECASE):
            return "chat"

    # Kurze Meta-Fragen (Wortgrenzen — vermeidet "hi" in "logging" etc.)
    if len(txt) <= 56:
        if re.search(
            r"\b(hallo|hi|hey|servus|moin|guten\s+morgen|guten\s+tag|guten\s+abend|wie\s+geht|danke|tschüss|tschuess)\b",
            txt,
            flags=re.IGNORECASE,
        ):
            return "chat"

    # Erklaer-Hilfe ohne Coding-Verben in derselben Zeile
    if (
        any(k in txt for k in ("erklär", "erklaer", "hilfe", "was kannst du", "wie funktioniert"))
        and not any(k in txt for k in _PROJECT_VERBS_SPACE)
        and not re.search(r"\.(py|js|tsx|jsx|ts)\b", txt)
    ):
        return "help_question"

    conversational = (
        "fasse zusammen",
        "was machen wir",
        "was tun wir",
        "was soll ich",
        "wie soll ich",
        "erzähl",
        "erzaehl",
        "unterhalt",
        "meine meinung",
        "was denkst du",
    )
    if any(c in txt for c in conversational) and not any(k in txt for k in _PROJECT_VERBS_SPACE):
        return "chat_question"

    # Ordner-/Listen-Leseauftraege + Projekt-/Code-Analyse (ohne Edit-Verben → project_read)
    read_keywords = (
        "ordnerliste",
        "dateiliste",
        "verzeichnisliste",
        "zeig mir den ordner",
        "liste dateien im ordner",
        "inhalt des ordners",
        "tree ",
        "projekt anzeigen",
        "analysiere den ordner",
        "analysiere kompletten ordner",
        "kompletten ordner analysieren",
        "gesamten ordner analysieren",
        "gesamtes projekt analysieren",
        "komplettes projekt analysieren",
        "den gesamten ordner",
        "die gesamte codebase",
        "codebase durchgehen",
        "dateien durchsuchen ohne zu ändern",
        "dateien durchsuchen ohne zu aendern",
        "zeige mir den inhalt der datei",
        "inhalt der datei",
        "lies die datei",
        "lese die datei",
        # Explizite Analyse-Auftraege → read_request / project_read
        "projektanalyse",
        "projekt analyse",
        "code-analyse",
        "code analyse",
        "codebase analys",
        "architektur analys",
        "generator analys",
        "abhängigkeit analys",
        "abhängigkeiten analys",
        "dependency analys",
        "statische analyse",
        "analysiere das projekt",
        "analysiere die struktur",
        "analysiere den code",
        "analyse den code",
        "analyse die struktur",
        "analyse durchführen",
        "analyse durchfuehren",
        "führ eine analyse",
        "fuehr eine analyse",
        "analyze the code",
        "analyze the project",
        "project analysis",
        "code analysis",
        "untersuche das projekt",
        "untersuche den code",
        "review die architektur",
        "sicherheitsanalyse",
        "performance-analyse",
        "performance analys",
    )
    if any(re.search(r"\b" + re.escape(k) + r"\b", txt) for k in read_keywords):
        return "read_request"
    # Freiere Muster: „analysiere“ + Projekt/Code-Kontext (Pfade, Endungen, Ordner)
    if re.search(r"\b(analysiere|analyse|untersuche|bewert\w*)\b", txt, re.IGNORECASE) and (
        re.search(r"\.(py|js|tsx|jsx|ts|css|html|json|md)\b", txt, re.IGNORECASE)
        or re.search(
            r"\b(backend|frontend|src/|src\\|tests/|tests\\|projekt|projektordner|codebase|modul|komponente|ordner|verzeichnis|workspace)\b",
            txt,
            re.IGNORECASE,
        )
    ):
        return "read_request"

    if _UNCLEAR_WHITELIST.match(txt.strip()):
        return "ambiguous"

    # --- Projekt-Coding ---
    for pat in _PROJECT_PATTERNS:
        if re.search(pat, txt, flags=re.IGNORECASE):
            return "coding_task"

    if any(k in txt for k in _PROJECT_VERBS_SPACE):
        return "coding_task"

    if any(k in txt for k in ("lösche ", "loesche ", "delete datei", " entferne die datei")):
        return "risky_task"

    # Fragen mit ? tendenziell Chat (kein Pfad / kein Imperativ-Verben)
    if "?" in txt and len(txt) < 500:
        if not re.search(r"\b(ändere|aendere|implementiere|erstelle die datei|fixe|pytest)\b", txt):
            return "chat"

    return "unknown"


def classify_user_prompt_intent(prompt: str) -> str:
    """Voll-Intent inkl. Risky + Groq-Analyse + Heuristik (für Legacy-Aufrufer)."""
    txt = str(prompt or "").strip().lower()
    if not txt:
        return "unknown"
    if _is_risky_user_intent(prompt):
        return "risky_task"
    if is_analysis_only_prompt(prompt):
        return "analysis_request"
    return _classify_user_prompt_intent_heuristic_core(prompt)


def classify_user_prompt(prompt: str) -> str:
    """
    Rueckgabe: chat | project_read | project_task | risky_project_task | unknown
    Reihenfolge: riskant zuerst, dann Groq (change/analysis/chat), bei unknown nur Heuristik (kein zweites Groq).
    """
    txt = str(prompt or "").strip().lower()
    if not txt:
        return "unknown"
    if _is_risky_user_intent(prompt):
        return "risky_project_task"
    if should_route_direct_run_as_chat(prompt):
        return "chat"

    llm_intent = classify_with_groq(prompt)
    if llm_intent == "analysis":
        intent = "analysis_request"
    elif llm_intent == "change":
        intent = "coding_task"
    elif llm_intent == "chat":
        return "chat"
    else:
        intent = _classify_user_prompt_intent_heuristic_core(prompt)
    if intent == "risky_task":
        return "risky_project_task"
    if intent == "analysis_request":
        return "project_read"
    if has_project_change_intent(prompt):
        return "project_task"
    if intent == "chat_question":
        ui_terms = (
            "header",
            "footer",
            "farbe",
            "color",
            "hintergrund",
            "schrift",
            "button",
            "gradient",
            "border",
            "padding",
        )
        low = str(prompt or "").lower()
        if any(term in low for term in ui_terms):
            return "unknown"
    # Analyse-/Lese-Surface: eigene Klasse — Direktmodus darf hier keine Dateien schreiben
    if intent == "read_request":
        return "project_read"
    if intent in {"greeting", "chat", "help_question", "chat_question"}:
        return "chat"
    if intent == "coding_task":
        return "project_task"
    if intent == "ambiguous":
        return "unknown"
    if intent == "unknown":
        txt = str(prompt or "").strip().lower()
        if len(txt) <= 400:
            if not re.search(r"\.(py|js|tsx|jsx|ts|css|html|json)\b", txt):
                if not any(x in txt for x in ("backend/", "frontend/", "src/", "tests/", "pytest", "npm run", "git diff")):
                    return "chat"
        return "unknown"
    return "unknown"


def connectivity_diagnostics_reply() -> str:
    """Konkrete Checkliste bei Offline-/Verbindungsfragen (einheitlich für alle Fallback-Pfade)."""
    return (
        "**App / Backend offline — typische Ursachen**\n\n"
        "- **Backend:** Läuft der Flask-Server? Test: `GET http://127.0.0.1:5002/api/health` (oder dein Port).\n"
        "- **Frontend:** Vite (`npm run dev`) auf Port **5173** — Proxy in `vite.config.js` muss auf dasselbe Backend zeigen.\n"
        "- **Firewall / VPN:** `localhost` oder Port 5002 blockiert?\n"
        "- **Zwei Instanzen:** Nur einen Backend-Prozess auf dem Port nutzen.\n\n"
        "**Tipp:** Projektordner freigeben, dann kann ich zusätzlich Logs und Konfiguration im Workspace prüfen."
    )


def chat_reply_canned(prompt: str) -> str:
    """Kurzantwort ohne LLM (Fallback)."""
    if should_route_direct_run_as_chat(prompt):
        return connectivity_diagnostics_reply()
    txt = str(prompt or "").strip().lower()
    if "wie geht" in txt:
        return "Mir geht's gut. Ich bin bereit und kann dir direkt helfen."
    if "was kannst" in txt:
        return "Ich kann Fragen beantworten, Code erklaeren und bei freigegebenem Projekt auch aktiv im Ordner arbeiten, Dateien aendern und Tests ausfuehren."
    if any(k in txt for k in ("hallo", "hi", "hey", "servus", "moin", "guten morgen", "guten tag", "guten abend")):
        return "Hallo! Ich bin Rainer und hoere zu. Womit soll ich dir helfen?"
    return "Ich bin bereit. Stelle eine Frage oder gib mir eine konkrete Projektaufgabe (mit freigegebenem Projektordner)."


def routing_mode_label(kind: str) -> str:
    if kind == "chat":
        return "chat"
    if kind == "project_read":
        return "read_only_project"
    if kind == "project_task":
        return "project_agent"
    if kind == "risky_project_task":
        return "risky_blocked"
    return "unknown"


def unknown_clarification_reply() -> str:
    """Kurze Nachfrage wenn Absicht unklar — kein Dateizugriff."""
    return (
        "Das ist mir noch zu unspezifisch. Meinst du eine **Konversation/Erklaerung** "
        "oder soll ich **etwas im Projektordner** aendern? Beschreib kurz, was du erreichen willst."
    )


# Stoppt zuverlässig vor Rest des Satzes (Leerzeichen, Anführungszeichen, etc.).
_WIN_PATH_FOR_ANALYSIS = re.compile(
    r'([A-Za-z]:\\(?:[^\s"<>|?*]+(?:\\[^\s"<>|?*]+)*))',
    re.IGNORECASE,
)


def extract_folder_analysis_path_from_prompt(text: str) -> str | None:
    """Ersten Windows-Pfad (Laufwerk:\\...) aus dem Prompt extrahieren."""
    if not text:
        return None
    m = _WIN_PATH_FOR_ANALYSIS.search(str(text))
    if not m:
        return None
    raw = str(m.group(1) or "").strip().rstrip(".,;:!?)]}\"'")
    return raw or None


def has_project_change_intent(text: str) -> bool:
    """
    True wenn der Prompt eine konkrete Änderungs-/Bearbeitungsabsicht ausdrückt.
    Hat Vorrang vor reiner Ordner-/Workspace-Analyse (Lesen).
    """
    raw = str(text or "")
    if not raw.strip():
        return False
    t = " ".join(raw.lower().split())

    # Konkrete Wert-Angaben → fast immer Änderungsauftrag (CSS/UI)
    value_patterns = (
        r"#[0-9a-fA-F]{3,6}\b",
        r"\b\d+px\b",
        r"\b\d+em\b",
        r"\brgba?\s*\(",
    )
    if any(re.search(p, raw, flags=re.IGNORECASE) for p in value_patterns):
        return True

    # Einzel-/Komposit-Verben (DE/EN), Wortgrenzen wo sinnvoll
    verb_union = (
        r"entferne|entfernen|rausnehmen|ausblenden|deaktivieren|deaktiviere|"
        r"löschen|lösche|loeschen|loesche|ändern|ändere|aendern|aendere|"
        r"anpassen|umbauen|implementieren|implementiere|"
        r"hinzufügen|hinzufuegen|reparieren|repariere|"
        r"beheben|behebe|ersetzen|ersetze|"
        r"setzen|setzt|gesetzt|verwenden|verwendet|passt|angepasst|"
        r"nehmen|nimmt|lassen|lass|überall|"
        r"fix|fixen|fixe|remove|hide|disable|delete|change|modify|implement|add|update"
    )
    verb_re = re.compile(rf"\b({verb_union})\b", re.IGNORECASE)
    if verb_re.search(t):
        return True
    # Mehrtwort-Imperative
    if re.search(r"\bblende\b.*\baus\b", t, flags=re.DOTALL):
        return True
    if re.search(r"\bpasse\s+an\b|\banpassen\b", t):
        return True
    if re.search(r"\bfüge\s+hinzu\b|\bfuege\s+hinzu\b|\bhinzufügen\b|\bhinzufuegen\b", t):
        return True
    if re.search(r"\bbaue\s+um\b|\bumbauen\b", t):
        return True

    # Kombinationen: enge Muster, falls einzelne Verben unüblich formuliert sind
    if "builder" in t and "mode" in t and re.search(
        r"\b(entferne|entfernen|ausblenden|deaktivieren|deaktiviere|remove|hide|delete|lösche|loesche)\b",
        t,
        re.IGNORECASE,
    ):
        return True
    # Explizite Kombinationen (auch wenn Verben untypisch formuliert sind)
    if "frontend" in t and verb_re.search(t):
        return True
    for fp in (r"app\.js", r"style\.css", r"index\.html"):
        if re.search(fp, raw, re.IGNORECASE) and verb_re.search(t):
            return True

    return False


def is_folder_analysis_prompt(prompt: str) -> bool:
    """
    True bei Ordner-/Workspace-Analyse (nur Lesen, keine Code-Aenderung).
    Kombination aus Schluesselwoertern und optional Windows-Pfad.
    """
    raw = str(prompt or "")
    if has_project_change_intent(raw):
        return False
    t = " ".join(raw.lower().split())
    if not t:
        return False

    phrase_hits = (
        "analysiere den ordner",
        "analysiere nun den ordner",
        "analysiere ordner",
        "analysiere den workspace",
        "analysiere workspace",
        "sag mir den inhalt",
        "zeige mir den inhalt",
        "zeige mir die struktur",
        "ordnerstruktur",
        "struktur des ordners",
        "inhalt des ordners",
        "inhalt des ordner",
        "inhalt des verzeichnis",
        "inhalt des verzeichnisses",
        "verzeichnisstruktur",
        "zeige mir das verzeichnis",
        "liste den ordner",
        "liste das verzeichnis",
    )
    if any(p in t for p in phrase_hits):
        return True
    if ("was ist in" in t or "was ist drin" in t) and (
        extract_folder_analysis_path_from_prompt(raw)
        or "ordner" in t
        or "verzeichnis" in t
        or "drin" in t
        or re.search(r"[a-z]:\\", raw, re.I)
    ):
        return True
    if re.search(r"\btree\b", t):
        return True
    if ("analysiere" in t or "analyse " in t) and (
        "ordner" in t or "verzeichnis" in t or "workspace" in t or "projektordner" in t
    ):
        return True
    if ("inhalt" in t or "struktur" in t or "drin" in t) and ("ordner" in t or "verzeichnis" in t):
        return True

    path_hint = extract_folder_analysis_path_from_prompt(raw)
    if path_hint:
        path_keys = (
            "inhalt",
            "struktur",
            "analysiere",
            "analyse",
            "zeige",
            "sag mir",
            "was ist",
            "auflisten",
            "tree",
            "ordner",
            "verzeichnis",
            "workspace",
            "drin",
        )
        if any(k in t for k in path_keys):
            return True
    return False
