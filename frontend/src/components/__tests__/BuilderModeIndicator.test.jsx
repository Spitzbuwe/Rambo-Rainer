import React from "react";
import { describe, test, expect, afterEach, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import BuilderModeIndicator from "../BuilderModeIndicator.jsx";

vi.mock("../GeneratorUI.jsx", () => ({
  default: function MockGeneratorUI() {
    return <div data-testid="mock-generator-ui">GeneratorUI</div>;
  },
}));

vi.mock("../DesignStudio.jsx", () => ({
  default: function MockDesignStudio({ onClose }) {
    return (
      <div data-testid="mock-design-studio">
        <button type="button" onClick={onClose}>
          close-ds
        </button>
      </div>
    );
  },
}));

function baseProps(over = {}) {
  return {
    builderModalOpen: false,
    setBuilderModalOpen: vi.fn(),
    generatorModalOpen: false,
    setGeneratorModalOpen: vi.fn(),
    designStudioOpen: false,
    setDesignStudioOpen: vi.fn(),
    ...over,
  };
}

describe("BuilderModeIndicator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  test("renders no modals when all closed", () => {
    render(<BuilderModeIndicator {...baseProps()} />);
    expect(screen.queryByRole("heading", { name: /Rambo App Builder/i })).not.toBeInTheDocument();
  });

  test("shows builder modal when builderModalOpen", () => {
    render(<BuilderModeIndicator {...baseProps({ builderModalOpen: true })} />);
    expect(screen.getByRole("heading", { name: /Rambo App Builder/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/my_awesome_app/i)).toBeInTheDocument();
  });

  test("shows generator modal when generatorModalOpen", () => {
    render(<BuilderModeIndicator {...baseProps({ generatorModalOpen: true })} />);
    expect(screen.getByRole("heading", { name: /Datei-Generator/i })).toBeInTheDocument();
    expect(screen.getByTestId("mock-generator-ui")).toBeInTheDocument();
  });

  test("shows design studio when designStudioOpen", () => {
    render(<BuilderModeIndicator {...baseProps({ designStudioOpen: true })} />);
    expect(screen.getByTestId("mock-design-studio")).toBeInTheDocument();
  });

  test("closes design studio via onClose", () => {
    const setStudio = vi.fn();
    render(<BuilderModeIndicator {...baseProps({ designStudioOpen: true, setDesignStudioOpen: setStudio })} />);
    fireEvent.click(screen.getByText("close-ds"));
    expect(setStudio).toHaveBeenCalledWith(false);
  });
});
