import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EvidencePanel } from "@/components/reasoning/EvidencePanel";
import type { ReasoningEvidencePayload } from "@/types";

const baseEvidence: ReasoningEvidencePayload = {
  name: "EMA Trend",
  source: "technical",
  direction: "BUY",
  score: 0.71,
  confidence: 0.8,
  weight: 0.6,
  impact_on_score: 0.43,
  reason: "EMA 20 > EMA 50",
  is_critical: false,
};

describe("EvidencePanel", () => {
  it("renders evidence for tab content", () => {
    render(
      <EvidencePanel
        evidenceFor={[{ ...baseEvidence, name: "Bullish Structure", evidence_type: "SUPPORT" }]}
        evidenceAgainst={[]}
        warnings={[]}
      />,
    );

    expect(screen.getByText("Bullish Structure")).toBeInTheDocument();
  });

  it("renders evidence against tab content", async () => {
    const user = userEvent.setup();
    render(
      <EvidencePanel
        evidenceFor={[]}
        evidenceAgainst={[{ ...baseEvidence, name: "Overbought RSI", evidence_type: "AGAINST" }]}
        warnings={[]}
      />,
    );

    await user.click(screen.getByRole("tab", { name: /Evidence Against/i }));

    expect(screen.getByText("Overbought RSI")).toBeInTheDocument();
  });

  it("renders warning tab content", async () => {
    const user = userEvent.setup();
    render(
      <EvidencePanel
        evidenceFor={[]}
        evidenceAgainst={[]}
        warnings={[{ ...baseEvidence, name: "News Event Risk", evidence_type: "WARNING", direction: "NEUTRAL" }]}
      />,
    );

    await user.click(screen.getByRole("tab", { name: /Warnings/i }));

    expect(screen.getByText("News Event Risk")).toBeInTheDocument();
  });
});
