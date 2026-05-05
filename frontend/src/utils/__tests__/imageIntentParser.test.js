import { describe, it, expect } from "vitest";
import { parseImageIntent } from "../imageIntentParser.js";

describe("imageIntentParser", () => {
  it('recognizes "entferne hintergrund"', () => {
    const result = parseImageIntent("entferne hintergrund");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("remove_background");
  });

  it('recognizes "entferne den Hintergrund" (Artikel)', () => {
    const result = parseImageIntent("entferne den Hintergrund");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("remove_background");
  });

  it('recognizes "freistellen"', () => {
    const result = parseImageIntent("freistellen");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("remove_background");
  });

  it('recognizes "grayscale"', () => {
    const result = parseImageIntent("konvertiere zu graustufen");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("grayscale");
  });

  it("returns false for unknown intent", () => {
    const result = parseImageIntent("schreib mir ein gedicht");
    expect(result.recognized).toBe(false);
  });
});
