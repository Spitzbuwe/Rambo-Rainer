import { describe, it, expect } from "vitest";
import { parseCanvasCommand } from "../commandParser.js";

describe("commandParser", () => {
  it('parses "Erstelle eine rote Box"', () => {
    const result = parseCanvasCommand("Erstelle eine rote Box");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("add");
    expect(result.element).toBe("rect");
    expect(result.props.fill).toBe("#ff0000");
  });

  it('parses "Erstelle einen grünen Kreis"', () => {
    const result = parseCanvasCommand("Erstelle einen grünen Kreis");
    expect(result.recognized).toBe(true);
    expect(result.element).toBe("circle");
  });

  it('parses "Lösche alle Elemente"', () => {
    const result = parseCanvasCommand("Lösche alle Elemente");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("deleteAll");
  });

  it("returns false for unknown command", () => {
    const result = parseCanvasCommand("Hallo Welt");
    expect(result.recognized).toBe(false);
  });
});
