import { describe, it, expect } from "vitest";
import { parseCodeIntent, isCodeIntent } from "../codeIntentParser.js";

describe("codeIntentParser", () => {
  it('recognizes "Füge eine Funktion ein"', () => {
    const result = parseCodeIntent("Füge eine Funktion ein");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("add_function");
  });

  it('recognizes "Fixiere diesen Bug"', () => {
    const result = parseCodeIntent("Fixiere diesen Bug");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("fix_bug");
  });

  it('recognizes "Erkläre mir diesen Code"', () => {
    const result = parseCodeIntent("Erkläre mir diesen Code");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("explain_code");
  });

  it('recognizes "Optimiere diesen Code"', () => {
    const result = parseCodeIntent("Optimiere diesen Code");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("optimize_code");
  });

  it('recognizes "Schreib Unit-Tests"', () => {
    const result = parseCodeIntent("Schreib Unit-Tests");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("write_tests");
  });

  it("returns false for non-code intent", () => {
    const result = parseCodeIntent("schreib mir ein gedicht");
    expect(result.recognized).toBe(false);
  });

  it("isCodeIntent checks confidence", () => {
    const result = parseCodeIntent("Füge eine Funktion ein");
    expect(isCodeIntent(result)).toBe(true);
  });
});
