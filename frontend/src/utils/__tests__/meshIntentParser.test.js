import { describe, it, expect } from "vitest";
import { parse3DIntent, is3DIntent } from "../meshIntentParser.js";

describe("meshIntentParser", () => {
  it('recognizes "konvertiere zu 3D-Modell"', () => {
    const result = parse3DIntent("konvertiere zu 3D-Modell");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("image_to_3d");
  });

  it('recognizes "erstelle ein Mesh"', () => {
    const result = parse3DIntent("erstelle ein Mesh");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("generate_mesh");
  });

  it('recognizes "point cloud"', () => {
    const result = parse3DIntent("generiere eine point cloud");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("point_cloud");
  });

  it('recognizes "photogrammetrie"', () => {
    const result = parse3DIntent("photogrammetrie aus diesem bild");
    expect(result.recognized).toBe(true);
    expect(result.action).toBe("image_to_3d");
  });

  it("returns false for non-3D intent", () => {
    const result = parse3DIntent("schreib mir ein gedicht");
    expect(result.recognized).toBe(false);
  });

  it("is3DIntent returns true for recognized high-confidence", () => {
    const result = parse3DIntent("konvertiere zu 3D-Modell");
    expect(is3DIntent(result)).toBe(true);
  });

  it("is3DIntent returns false for unrecognized", () => {
    const result = parse3DIntent("hallo welt");
    expect(is3DIntent(result)).toBe(false);
  });
});
