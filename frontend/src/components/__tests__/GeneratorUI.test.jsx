import React from "react";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import GeneratorUI from "../GeneratorUI.jsx";
import { generatorService } from "../../services/generatorService.js";

vi.mock("../../services/generatorService.js", () => ({
  generatorService: {
    getOfficeTemplates: vi.fn(),
    getDesignTemplates: vi.fn(),
    generateWordDocument: vi.fn(),
    generateExcelSheet: vi.fn(),
    generatePowerPoint: vi.fn(),
    generateSVGDesign: vi.fn(),
    generateDesignTemplate: vi.fn(),
    downloadGeneratedFile: vi.fn(),
  },
}));

describe("GeneratorUI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    generatorService.getOfficeTemplates.mockResolvedValue({});
    generatorService.getDesignTemplates.mockResolvedValue({});
  });

  afterEach(() => {
    cleanup();
  });

  test("renders generator UI with tabs", () => {
    render(<GeneratorUI />);
    expect(screen.getByText("📄 Office-Dokumente")).toBeInTheDocument();
    expect(screen.getByText("🎨 Designs")).toBeInTheDocument();
    expect(screen.getByText("ℹ️ Info")).toBeInTheDocument();
  });

  test("generates word document", async () => {
    generatorService.generateWordDocument.mockResolvedValue({
      status: "success",
      file: "letter_20260419.docx",
    });

    render(<GeneratorUI />);
    fireEvent.click(screen.getByText("📄 Word generieren"));

    await waitFor(() => {
      expect(screen.getByText(/letter_20260419\.docx/)).toBeInTheDocument();
    });
  });

  test("generates SVG design", async () => {
    generatorService.getDesignTemplates.mockResolvedValue({
      svg_templates: ["business_card"],
      brand_colors: ["default"],
    });
    generatorService.generateSVGDesign.mockResolvedValue({
      status: "success",
      file: "business_card_20260419.svg",
    });

    render(<GeneratorUI />);
    fireEvent.click(screen.getByText("🎨 Designs"));
    fireEvent.click(screen.getByText("🎨 Design generieren"));

    await waitFor(() => {
      expect(screen.getByText(/business_card_20260419\.svg/)).toBeInTheDocument();
    });
  });
});
