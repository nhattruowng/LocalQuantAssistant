import { useState } from "react";
import { Button } from "@/components/forms/Button";
import { MetricCard } from "@/components/cards/MetricCard";
import { SignalCard } from "@/components/cards/SignalCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { useActions } from "@/hooks/useApiQueries";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { TradeSetup } from "@/types";

interface SignalPageProps {
  latestSignal?: TradeSetup | null;
  onSignalGenerated: (setup: TradeSetup) => void;
}

export function SignalPage({ latestSignal, onSignalGenerated }: SignalPageProps) {
  const actions = useActions();
  const [multiTimeframe, setMultiTimeframe] = useState(true);
  const explanation = latestSignal?.explanation_v2;

  const generate = async () => {
    const setup = await actions.generateSignal.mutateAsync(multiTimeframe);
    onSignalGenerated(setup);
  };

  return (
    <div>
      <PageHeader
        title="Signal"
        description="Risk-aware BUY / SELL / WAIT recommendation with reasons and levels."
        actions={
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={multiTimeframe}
                onChange={(event) => setMultiTimeframe(event.target.checked)}
              />
              Multi-timeframe
            </label>
            <Button onClick={generate} disabled={actions.generateSignal.isPending}>Generate Signal</Button>
          </div>
        }
      />
      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <SignalCard setup={latestSignal} />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Entry" value={formatNumber(latestSignal?.entry, 4)} />
          <MetricCard label="Stop Loss" value={formatNumber(latestSignal?.stop_loss, 4)} />
          <MetricCard label="Take Profit 1" value={formatNumber(latestSignal?.take_profit_1, 4)} />
          <MetricCard label="Take Profit 2" value={formatNumber(latestSignal?.take_profit_2, 4)} />
          <MetricCard label="Position Size" value={formatNumber(latestSignal?.position_size, 6)} />
          <MetricCard label="Risk/Reward" value={formatNumber(latestSignal?.risk_reward, 2)} />
          <MetricCard label="Probability Source" value={latestSignal?.probability_source ?? "-"} />
          <MetricCard label="BUY %" value={formatPercent((latestSignal?.calibrated_probabilities ?? latestSignal?.raw_probabilities ?? latestSignal?.probabilities)?.BUY ?? (latestSignal?.signal === "BUY" ? latestSignal.confidence : undefined))} />
          <MetricCard label="SELL %" value={formatPercent((latestSignal?.calibrated_probabilities ?? latestSignal?.raw_probabilities ?? latestSignal?.probabilities)?.SELL ?? (latestSignal?.signal === "SELL" ? latestSignal.confidence : undefined))} />
          <MetricCard label="WAIT %" value={formatPercent((latestSignal?.calibrated_probabilities ?? latestSignal?.raw_probabilities ?? latestSignal?.probabilities)?.WAIT ?? (latestSignal?.signal === "WAIT" ? latestSignal.confidence : undefined))} />
          <MetricCard label="Regime" value={latestSignal?.market_regime ?? "-"} />
          <MetricCard label="Fallback" value={latestSignal?.fallback_reason ?? "-"} />
          <MetricCard label="Selected Strategy" value={explanation?.strategy?.selected ?? latestSignal?.strategy ?? "-"} />
          <MetricCard label="MTF" value={explanation?.multi_timeframe?.enabled ? "Enabled" : "Disabled"} />
          <MetricCard label="Regime Uncertainty" value={formatPercent(explanation?.regime?.uncertainty_score)} />
          <MetricCard label="Volatility" value={explanation?.regime?.volatility_level ?? "-"} />
        </div>
      </div>
      {explanation ? (
        <section className="mt-4 rounded-lg border border-border bg-white p-4">
          <h3 className="mb-2 font-semibold">Decision Summary</h3>
          <p className="text-sm text-muted-foreground">{explanation.final_decision_summary || explanation.summary}</p>
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <div>
              <h4 className="mb-2 text-sm font-medium">Higher Timeframes</h4>
              {explanation.multi_timeframe?.confirmations?.length ? (
                <div className="space-y-2 text-sm text-muted-foreground">
                  {explanation.multi_timeframe.confirmations.map((item) => (
                    <div key={`${item.timeframe}-${item.regime}`} className="rounded-md border border-border p-2">
                      <div className="flex items-center justify-between gap-2">
                        <span>{item.timeframe}</span>
                        <strong className="text-foreground">{item.regime}</strong>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs">
                        <span>conf {formatPercent(item.confidence)}</span>
                        <span>{item.aligned ? "aligned" : "not aligned"}</span>
                        <span>{item.conflict ? "conflict" : "no conflict"}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No higher timeframe data available.</p>
              )}
            </div>
            <div>
              <h4 className="mb-2 text-sm font-medium">Regime Scores</h4>
              {explanation.regime?.regime_scores ? (
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {Object.entries(explanation.regime.regime_scores)
                    .sort(([, left], [, right]) => right - left)
                    .slice(0, 5)
                    .map(([regime, score]) => <li key={regime}>{regime}: {formatPercent(score)}</li>)}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No regime score payload.</p>
              )}
            </div>
            <div>
              <h4 className="mb-2 text-sm font-medium">Passed Rules</h4>
              {explanation.strategy?.passed_conditions?.length ? (
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {explanation.strategy.passed_conditions.map((item) => <li key={item}>- {item}</li>)}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No passed rule payload.</p>
              )}
            </div>
            <div>
              <h4 className="mb-2 text-sm font-medium">Failed Rules</h4>
              {explanation.strategy?.failed_conditions?.length ? (
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {explanation.strategy.failed_conditions.map((item) => <li key={item}>- {item}</li>)}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No failed rules.</p>
              )}
            </div>
          </div>
        </section>
      ) : null}
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 font-semibold">Reasons</h3>
          {latestSignal?.reasons?.length ? (
            <ul className="space-y-2 text-sm text-muted-foreground">
              {latestSignal.reasons.map((reason) => <li key={reason}>- {reason}</li>)}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No signal generated</p>
          )}
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 font-semibold">Risk Notes</h3>
          {latestSignal?.risk_notes?.length ? (
            <ul className="space-y-2 text-sm text-muted-foreground">
              {latestSignal.risk_notes.map((note) => <li key={note}>- {note}</li>)}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No risk notes.</p>
          )}
        </section>
      </div>
      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <h3 className="mb-3 font-semibold">Explainability</h3>
        {latestSignal?.explainability ? (
          <div className="grid gap-4 xl:grid-cols-3">
            <p className="text-sm text-muted-foreground xl:col-span-1">{latestSignal.explainability.summary}</p>
            <div>
              <h4 className="mb-2 text-sm font-medium">Positive Factors</h4>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {latestSignal.explainability.top_positive_factors?.map((factor) => (
                  <li key={factor.feature}>{factor.feature}: {formatNumber(factor.impact, 4)}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="mb-2 text-sm font-medium">Negative Factors</h4>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {latestSignal.explainability.top_negative_factors?.map((factor) => (
                  <li key={factor.feature}>{factor.feature}: {formatNumber(factor.impact, 4)}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No explainability payload returned by the API.</p>
        )}
      </section>
    </div>
  );
}
