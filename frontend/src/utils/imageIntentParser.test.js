import { describe, expect, it } from "vitest";
import { parseImageGenerationIntent } from "./imageIntentParser.js";

describe("parseImageGenerationIntent", () => {
  it("erkennt Erstellungs-Intent", () => {
    const r = parseImageGenerationIntent("Erstelle ein Bild von einem roten Panda");
    expect(r.recognized).toBe(true);
    expect(r.prompt.length).toBeGreaterThan(0);
  });

  it("blockt Analyse-Intent", () => {
    const r = parseImageGenerationIntent("Analysiere dieses Bild und beschreibe es");
    expect(r.recognized).toBe(false);
  });
});
