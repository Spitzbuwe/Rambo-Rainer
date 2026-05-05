export const parse3DIntent = (message) => {
  const msg = String(message || "").toLowerCase().trim();

  const patterns = [
    {
      regex: /\b(mach|wandle|konvertier)\w*\s+daraus[^\n]*\b3d\b/i,
      action: "image_to_3d",
      label: "3D aus hochgeladenem Bild (Deixis)",
      confidence: 0.97,
    },
    {
      regex: /(mesh|netz|geometri).*?(generi|erstell|create)|(?:generi|erstell|create).*?(mesh|netz|geometri)/i,
      action: "generate_mesh",
      label: "Mesh generieren",
      confidence: 0.85,
    },
    {
      regex:
        /(konvertier|convert|erstell|create|generi|generat|mach|wandle).*\s+(3d|3d-modell|mesh|modell|object|obj)|(?:meshy\.?ai|wie\s+meshy)/i,
      action: "image_to_3d",
      label: "3D-Modell aus Bild",
      confidence: 0.95,
    },
    {
      regex: /(foto|bild|image).*?(3d|modell|mesh)/i,
      action: "image_to_3d",
      label: "3D-Modell aus Bild",
      confidence: 0.9,
    },
    {
      regex: /(photogrammetri|scanning|scan|depth|tiefe)/i,
      action: "image_to_3d",
      label: "3D aus Bild (Photogrammetrie)",
      confidence: 0.8,
    },
    {
      regex: /(normal.*map|depth.*map|heightmap|height-map)/i,
      action: "generate_map",
      label: "Normal/Depth-Map generieren",
      confidence: 0.85,
    },
    {
      regex: /(point.*cloud|punktwolke|3d.*cloud)/i,
      action: "point_cloud",
      label: "Point Cloud generieren",
      confidence: 0.8,
    },
    {
      regex: /(rekonstrui|reconstruct|3d.*reconstruct)/i,
      action: "image_to_3d",
      label: "3D-Rekonstruktion",
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
    suggestion: 'Versuche: "Konvertiere zu 3D-Modell" oder "Erstelle ein Mesh"',
  };
};

export const is3DIntent = (intent) => {
  return !!intent?.recognized && Number(intent?.confidence || 0) >= 0.8;
};

/**
 * Grobe Erkennung für Prompt→3D ohne Bild (muss mit backend/_detect_text_to_3d_intent konsistent bleiben).
 * Wenn true: Design-Studio-Chat soll /api/chat/message nutzen, nicht /api/canvas/ai-generate.
 */
export function isTextTo3dChatPrompt(message) {
  let low = String(message || "").trim().toLowerCase();
  low = low
    .replace(/\bdart[\s-]+pfeil(?:e|en)?\b/g, "dartpfeil")
    .replace(/\btrink[\s-]+flasche(?:n)?\b/g, "trinkflasche")
    .replace(/\bregen[\s-]+schirm(?:e|en)?\b/g, "regenschirm");
  if (!low) return false;
  if (/\b(daraus|dieses\s+bild|das\s+bild|dieses\s+foto|aus\s+dem\s+bild)\b/.test(low)) return false;
  const has3d = /\b3d\b|\b3-d\b|\b3d-modell\b/.test(low);
  const buildVerb = /\b(mach\w*|erstell\w*|baue?\w*|generier\w*|modellier\w*|erzeug\w*)\b/.test(low);
  const compositeHint =
    /\b(mann|mensch|figur|charakter|person)\b/.test(low) && /\b(dartpfeil|dart|pfeil(?:e|en)?)\b/.test(low);
  if (!buildVerb) return false;
  const shapeHint =
    /\b(modell|objekt|figur|statue|mann|mensch|person|würfel|wuerfel|cube|charakter|trophäe|trophae|pokal|dartpokal|dartpfeil|dart|pfeil|becher|tasse|cup|mug|flasche|trinkflasche|bottle|tisch|table|stuhl|chair|sessel|sitz|regenschirm|schirm|umbrella|kugel|zylinder|kegel|sphere|cylinder|cone)\b/.test(
      low,
    );
  if (!has3d && !compositeHint && !shapeHint) return false;
  const hasSubjectTail = /\b(?:von|aus)\s+\S+/.test(low) || /\b3d(?:-modell|\s+modell|\s+objekt|\s+figur)?\s+\S+/.test(low);
  if (!shapeHint && !hasSubjectTail) return false;
  return true;
}
