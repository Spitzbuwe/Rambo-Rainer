export const parseImageIntent = (message) => {
  const msg = String(message || "")
    .replace(/\u00a0/g, " ")
    .replace(/\u200b/g, "")
    .toLowerCase()
    .trim();

  const patterns = [
    {
      regex: /(entferne|remove|lösche)(?:\s+[\wäöüÄÖÜß]+)*\s+(hintergrund|background|bg)\b/i,
      action: "remove_background",
      label: "Hintergrund entfernen",
    },
    {
      regex: /(freistell|cutout|freischneid)/i,
      action: "remove_background",
      label: "Freistellen",
    },
    {
      regex: /(transparent|transparenz|alpha)/i,
      action: "remove_background",
      label: "Transparent machen",
    },
    {
      regex: /(zuschneid|crop|beschneid)/i,
      action: "crop",
      label: "Zuschneiden",
    },
    {
      regex: /(resize|skalier|vergrößer|verklein)/i,
      action: "resize",
      label: "Größe ändern",
    },
    {
      regex: /(drehe|rotate|dreh)/i,
      action: "rotate",
      label: "Drehen",
    },
    {
      regex: /(graustufen|grayscale|schwarz.*weiß|b&w)/i,
      action: "grayscale",
      label: "Zu Graustufen",
    },
    {
      regex:
        /\b(analysier|analyse|erkenn|detect|beschreib)\w*\b.{0,100}\b(bild|foto|image|screenshot|png|jpe?g|webp|gif)\b/i,
      action: "analyze",
      label: "Analysieren",
    },
    {
      regex: /\b(bild|foto)\b.{0,80}\b(analysier|analyse|erkenn|detect|beschreib|was\s+steht|inhalt)\w*\b/i,
      action: "analyze",
      label: "Analysieren",
    },
    {
      regex: /\bwas\s+steht\b.{0,40}\b(auf\s+dem\s+)?(bild|foto)\b/i,
      action: "analyze",
      label: "Analysieren",
    },
    {
      regex: /\bwas\s+ist\b.{0,30}\b(auf\s+dem\s+|im\s+|auf\s+)?(bild|foto|screenshot)\b/i,
      action: "analyze",
      label: "Analysieren",
    },
    {
      regex: /\bzeig\w*\b.{0,60}\b(bild|foto|image)\b/i,
      action: "analyze",
      label: "Analysieren",
    },
  ];

  for (const pattern of patterns) {
    if (pattern.regex.test(msg)) {
      return {
        recognized: true,
        action: pattern.action,
        label: pattern.label,
        originalMessage: message,
      };
    }
  }

  return {
    recognized: false,
    originalMessage: message,
  };
};
