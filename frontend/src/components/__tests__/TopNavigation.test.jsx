import React from "react";
import { describe, test, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import TopNavigation from "../TopNavigation.jsx";

describe("TopNavigation", () => {
  afterEach(() => {
    cleanup();
  });

  test("hides Builder tab by default; shows generator and studio", () => {
    render(
      <TopNavigation
        onBuilderMode={() => {}}
        onGeneratorUI={() => {}}
        onDesignStudio={() => {}}
        onRainerAgent={() => {}}
      />,
    );

    expect(screen.queryByRole("button", { name: /Builder Mode/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Rainer Agent/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Datei-Generator/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Design Studio/i })).toBeInTheDocument();
  });

  test("calls callbacks on button click (Builder optional via showBuilderMode)", () => {
    const onBuilder = vi.fn();
    const onGenerator = vi.fn();
    const onStudio = vi.fn();
    const onRainer = vi.fn();

    render(
      <TopNavigation
        showBuilderMode
        onBuilderMode={onBuilder}
        onGeneratorUI={onGenerator}
        onDesignStudio={onStudio}
        onRainerAgent={onRainer}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Builder Mode/i }));
    expect(onBuilder).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Rainer Agent/i }));
    expect(onRainer).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Datei-Generator/i }));
    expect(onGenerator).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Design Studio/i }));
    expect(onStudio).toHaveBeenCalled();
  });
});
