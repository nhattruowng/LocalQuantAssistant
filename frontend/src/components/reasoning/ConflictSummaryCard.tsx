import type { TradeSetup } from "@/types";
import { ConflictPanel } from "@/components/reasoning/ReasoningPanels";

export function ConflictSummaryCard({ setup }: { setup?: TradeSetup | null }) {
  return <ConflictPanel setup={setup} />;
}
