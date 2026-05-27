import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DecisionTraceViewer } from "@/components/reasoning/DecisionTraceViewer";
import type { DecisionTracePayload } from "@/types";

describe("DecisionTraceViewer", () => {
  it("does not crash on empty trace", () => {
    render(<DecisionTraceViewer trace={{ steps: [] }} />);

    expect(screen.getByText(/No decision trace available\./i)).toBeInTheDocument();
  });

  it("shows failed step state", () => {
    const trace: DecisionTracePayload = {
      steps: [
        {
          step_name: "Risk Filter",
          input_score: 0.8,
          output_score: 0.1,
          delta: -0.7,
          passed: false,
          warnings: [],
        },
      ],
    };

    render(<DecisionTraceViewer trace={trace} />);

    expect(screen.getByText("Risk Filter")).toBeInTheDocument();
    expect(screen.getAllByText(/failed/i).length).toBeGreaterThanOrEqual(2);
  });

  it("copies trace json", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    const trace: DecisionTracePayload = {
      trace_id: "trace-1",
      steps: [
        {
          step_name: "Score Blend",
          input_score: 0.4,
          output_score: 0.5,
          delta: 0.1,
          passed: true,
        },
      ],
    };

    render(<DecisionTraceViewer trace={trace} />);
    await user.click(screen.getByRole("button", { name: /Copy trace json/i }));

    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(JSON.stringify(trace, null, 2));
  });
});
