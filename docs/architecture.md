# LocalQuant Research Platform Architecture

## 1. Scope

LocalQuant is a research and decision-support platform for discretionary trading workflows.

It is not an execution bot. It does not place real orders automatically.

## 2. End-to-End System Layers

1. Data Collection
- `collector/binance_collector.py` fetches OHLCV market data.
- `collector/update_service.py` writes normalized candles to SQLite.

2. Feature & Regime Layer
- `features/feature_service.py` builds technical and contextual features.
- `regime/` detects market regime and regime confidence.

3. Model Layer
- `ml/model_trainer.py` trains global and regime-aware models.
- `ml/model_registry.py` manages model versions and lifecycle metadata.
- `ml/monitoring/model_monitor.py` computes drift diagnostics.

4. Market Reasoning Brain Layer
- `reasoning/market_reasoning_brain.py` produces:
  - Evidence for
  - Evidence against
  - Confluence score
  - Conflict level/details
  - Decision trace

5. Risk Layer
- `risk/risk_guard.py` enforces hard risk controls.
- Hard-block states include `BLOCKED` and `COOLDOWN`.
- RiskGuard can force `WAIT` regardless of directional model confidence.

6. Signal & Explanation Layer
- `signals/signal_engine.py` emits final `TradeSetup`.
- Legacy-compatible signal payload remains available.
- Enhanced payload adds `reasoning_decision` and structured `decision_trace`.

7. Backtest & Analytics Layer
- `backtest/backtester.py` simulates strategy outcomes.
- `backtest/analyzer.py` groups performance by:
  - regime
  - strategy
  - setup_type
  - wait_reason
  - conflict_level
- `backtest/ablation.py` evaluates component-level contribution.

8. API & Frontend Layer
- FastAPI routes under `src/api/routes/*`.
- React dashboards in `frontend/src/pages/*` render:
  - Signal intelligence and decision trace
  - Backtest research analytics
  - Model status/calibration/drift
  - RiskGuard status and risk events

## 3. Market Reasoning Brain Data Contract

Enhanced signal payload includes:

- `reasoning_decision.final_signal`
- `reasoning_decision.setup_type`
- `reasoning_decision.confluence_score`
- `reasoning_decision.evidence_for[]`
- `reasoning_decision.evidence_against[]`
- `reasoning_decision.conflict_level`
- `reasoning_decision.decision_trace`

`decision_trace.steps[]` carries step-level `input_score`, `output_score`, `delta`, warnings, and details.

## 4. RiskGuard Hard Block Behavior

RiskGuard returns runtime status and can block new entries when configured thresholds are breached:

- Daily/weekly drawdown cap
- Consecutive loss limit
- Cooldown period
- Data quality hard fail
- Low regime confidence (if enabled)

When blocked, dashboards must surface state and reason clearly.

## 5. Non-Execution Safety Boundary

System outputs are advisory only:

- No exchange/broker order submission path for live trading
- Paper trading is simulation-only
- Human approval is required before any real market action
