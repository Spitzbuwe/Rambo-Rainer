// Code-Intent Parser
// Erkennt: "Füge Funktion ein", "Fixiere Bug", "Erkläre", etc.

export const parseCodeIntent = (message) => {
  const msg = message.toLowerCase().trim();

  const patterns = [
    // Funktionen hinzufügen
    {
      regex: /(füg|add|schreib|write).*\s+(funktion|function|methode|method)/i,
      action: "add_function",
      label: "Funktion hinzufügen",
      confidence: 0.95,
    },
    // Bug fixen
    {
      regex: /(fix|beheb|reparier|debug|fehler.*suchen|korrigier)/i,
      action: "fix_bug",
      label: "Bug fixen",
      confidence: 0.9,
    },
    // Code erklären
    {
      regex: /(erkläre|explain|versteh|understand|was.*macht|how.*works)/i,
      action: "explain_code",
      label: "Code erklären",
      confidence: 0.85,
    },
    // Optimieren
    {
      regex: /(optimier|improve|schneller|faster|refactor|umstruktur)/i,
      action: "optimize_code",
      label: "Code optimieren",
      confidence: 0.85,
    },
    // Kommentare hinzufügen
    {
      regex: /(kommentar|comment|dokumentier|docstring)/i,
      action: "add_comments",
      label: "Kommentare hinzufügen",
      confidence: 0.8,
    },
    // Tests schreiben
    {
      regex: /(test|unittest|pytest|jest)/i,
      action: "write_tests",
      label: "Tests schreiben",
      confidence: 0.85,
    },
    // Type-Hints / Typisierung
    {
      regex: /(type.*hint|typen|annotation|typed|mypy)/i,
      action: "add_types",
      label: "Type-Hints hinzufügen",
      confidence: 0.8,
    },
    // Error-Handling
    {
      regex: /(error.*handling|exception|try.*catch|fehlerbehandlung)/i,
      action: "add_error_handling",
      label: "Error-Handling hinzufügen",
      confidence: 0.85,
    },
  ];

  for (const pattern of patterns) {
    if (pattern.regex.test(msg)) {
      return {
        recognized: true,
        action: pattern.action,
        label: pattern.label,
        confidence: pattern.confidence,
        originalMessage: message,
      };
    }
  }

  return {
    recognized: false,
    originalMessage: message,
    suggestion: 'Versuche: "Füge eine Funktion ein" oder "Fixiere diesen Bug"',
  };
};

export const isCodeIntent = (intent) => {
  return intent.recognized && intent.confidence >= 0.8;
};
