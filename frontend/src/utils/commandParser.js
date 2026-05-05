/** Parser für Chat-Kommandos → Canvas-Aktionen (Phase K.3). */

export const parseCanvasCommand = (message) => {
  const raw = String(message ?? "").trim();
  const msg = raw.toLowerCase();

  const patterns = [
    {
      regex: /erstelle\s+(?:eine|ein|einen)?\s*(?:rote|rotes|roten)?\s*(?:box|rechteck|quadrat)/i,
      action: "add",
      element: "rect",
      props: { fill: "#ff0000", width: 100, height: 100 },
    },
    {
      regex: /erstelle\s+(?:eine|ein|einen)?\s*(?:blaue|blaues|blauen)?\s*(?:box|rechteck|quadrat)/i,
      action: "add",
      element: "rect",
      props: { fill: "#0000ff", width: 100, height: 100 },
    },
    {
      regex: /erstelle\s+(?:einen|ein)?\s*(?:grünen|grüner|grünes)?\s*(?:kreis|circle)/i,
      action: "add",
      element: "circle",
      props: { fill: "#00ff00", width: 100, height: 100 },
    },
    {
      regex: /erstelle\s+(?:einen|ein)?\s*text/i,
      action: "add",
      element: "text",
      props: { text: "Neuer Text", fontSize: 16, fill: "#000000" },
    },
    {
      regex: /lösche\s+(?:das\s+)?(?:letzte|letztes)\s*(?:element)?/i,
      action: "delete",
      target: "last",
    },
    {
      regex: /lösche\s+alle?\s*(?:elemente)?/i,
      action: "deleteAll",
    },
    {
      regex: /ändere\s+(?:die\s+)?farbe\s+(?:zu\s+)?(rot|blau|grün|gelb|orange|lila|schwarz|weiß)/i,
      action: "updateColor",
      target: "selected",
    },
    {
      regex: /vergrößere/i,
      action: "resize",
      target: "selected",
      size: 1.2,
    },
    {
      regex: /verkleinere/i,
      action: "resize",
      target: "selected",
      size: 0.8,
    },
    {
      regex: /zentriere/i,
      action: "center",
      target: "selected",
    },
  ];

  for (const pattern of patterns) {
    if (pattern.regex.test(msg)) {
      return {
        recognized: true,
        action: pattern.action,
        element: pattern.element,
        props: pattern.props,
        target: pattern.target,
        size: pattern.size,
        originalMessage: raw,
      };
    }
  }

  return {
    recognized: false,
    originalMessage: raw,
    suggestion:
      'Ich habe das nicht verstanden. Versuche: „Erstelle eine rote Box“ oder „Lösche alle Elemente“.',
  };
};

export const parseColor = (colorName) => {
  const colors = {
    rot: "#ff0000",
    red: "#ff0000",
    blau: "#0000ff",
    blue: "#0000ff",
    grün: "#00ff00",
    green: "#00ff00",
    gelb: "#ffff00",
    yellow: "#ffff00",
    orange: "#ffa500",
    lila: "#800080",
    purple: "#800080",
    schwarz: "#000000",
    black: "#000000",
    weiß: "#ffffff",
    white: "#ffffff",
  };
  return colors[String(colorName ?? "").toLowerCase()] || "#000000";
};
