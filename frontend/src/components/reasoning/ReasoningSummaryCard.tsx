import type { TradeSetup } from "@/types";
import { ReasoningOverview } from "@/components/reasoning/ReasoningPanels";

export function ReasoningSummaryCard({ setup }: { setup?: TradeSetup | null }) {
  return <ReasoningOverview setup={setup} />;
}
