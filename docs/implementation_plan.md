# LocalQuant Assistant Implementation Integration Plan

## Audit Summary

- Repository root: `localquant-assistant`
- Backend framework: FastAPI, with the API app in `src/api/main.py`
- Backend service facade: `src/api/services/localquant_service.py`
- Frontend: Vite + React + TypeScript in `frontend/`
- Legacy/secondary UI: Streamlit is still present through `streamlit` in `requirements.txt` and `src/app/dashboard.py`
- API response DTOs: Pydantic response DTOs are defined in `src/api/schemas/responses.py`; signal/backtest/model route payloads currently return dictionaries from `LocalQuantApiService`
- Trading scope: research, backtest, and paper trading only; no module should place real-money orders

## Existing Modules

| Module | Current location | Current status |
| --- | --- | --- |
| SignalEngine | `src/signals/signal_engine.py` | Main signal orchestration layer. It builds `TradeSetup`, applies strategy/adaptive decisioning, risk planning, risk guard checks, structured explanation, reasoning payload, and decision trace diagnostics. |
| AdaptiveDecisionEngine | `src/signals/adaptive_decision_engine.py` | Existing adaptive selector for strategy opinions. It returns BUY/SELL/WAIT with threshold, setup quality, conflict result, wait reason, and memory adjustments. |
| RiskGuard | `src/risk/risk_guard.py` | Existing risk gate for daily/weekly drawdown, consecutive losses, open exposure, trade limits, cooldown, and low-confidence regimes. API status is surfaced through `LocalQuantApiService.risk_status`. |
| Backtester | `src/backtest/backtester.py` and `src/backtest/engine.py` | Existing backtest execution and reporting stack. API route is `src/api/routes/backtest.py`; service method is `LocalQuantApiService.run_backtest`. |
| ModelTrainer | `src/ml/model_trainer.py` | Existing local model training module. API route is `src/api/routes/model.py`; service method is `LocalQuantApiService.train_model`. |
| API response DTO | `src/api/schemas/responses.py` and `src/signals/models.py` | Pydantic DTOs exist for health/list/candle/data/features/model training. Signal response is serialized from `TradeSetup.to_dict()` rather than a dedicated Pydantic response model. |
| MarketReasoningBrain | `src/reasoning/market_reasoning_brain.py` | Already present. It evaluates evidence, confluence, conflicts, setup classification, wait reason, sizing multiplier, and decision trace. Config is under `reasoning_brain` in `src/config/settings.yaml`. |
| DecisionTrace | `src/signals/decision_trace.py` | Already present. It serializes trace id, ordered steps, final signal/confidence, warnings, model version, and timestamps. |
| Reasoning FE components | `frontend/src/components/reasoning/` and `frontend/src/features/signal/SignalPage.tsx` | Already present. React panels can render reasoning decisions, evidence, conflicts, and decision traces from `TradeSetup.reasoning_decision` or strategy diagnostics. |

## Reasoning Brain Integration Points

Primary backend integration should remain in `src/signals/signal_engine.py`:

- `SignalEngine.__init__` already constructs `MarketReasoningBrain(settings.reasoning_brain)`.
- `SignalEngine._reasoning_brain_enabled()` already gates behavior by config.
- `SignalEngine._reasoning_context()` is the adapter from existing strategy/risk state into `MarketReasoningContext`.
- `SignalEngine._approved_setup()` is the safest final gate for applying reasoning output after strategy, risk planning, safety filters, dynamic sizing, and multi-timeframe checks.
- `TradeSetup.reasoning_decision` in `src/signals/models.py` is the backward-compatible response field for new reasoning data.

Future reasoning-brain work should add fields through `reasoning_decision` or `explanation_v2.strategy` rather than changing existing top-level signal fields. Any future analyzer/backtest use must remain strictly causal: only the current bar and historical bars available at the decision timestamp may be used.

## Decision Trace Integration Points

Decision trace should remain a diagnostic payload, not an execution control surface:

- Core model: `src/signals/decision_trace.py`
- Signal diagnostics fallback: `TradeSetup.strategy_diagnostics["decision_trace"]`
- Reasoning-brain trace: `TradeSetup.reasoning_decision["decision_trace"]`
- Existing frontend resolver: `frontend/src/components/reasoning/ReasoningPanels.tsx`
- Existing viewer: `frontend/src/components/reasoning/DecisionTraceViewer.tsx`

Future trace additions should append new step names and details while preserving existing fields: `trace_id`, `steps`, `final_signal`, `final_confidence`, `warnings`, and `created_at`.

## Frontend Dashboard Integration Points

The main frontend integration should use the React app, not Streamlit:

- App shell/router state: `frontend/src/app/App.tsx`
- Main dashboard: `frontend/src/features/dashboard/DashboardPage.tsx`
- Signal reasoning dashboard: `frontend/src/features/signal/SignalPage.tsx`
- API client: `frontend/src/lib/api.ts`
- Shared signal/reasoning types: `frontend/src/types/index.ts` and `frontend/src/types/reasoning.ts`
- Existing reasoning components: `frontend/src/components/reasoning/`

Future dashboard work should reuse `resolveReasoning()` and `resolveDecisionTrace()` so older signal payloads continue rendering. New API fields should be optional in TypeScript types to avoid breaking historical payloads and saved signal history.

## API Contract Guidance

- Preserve existing route paths under `src/api/routes/`.
- Preserve existing `TradeSetup` top-level fields and add only optional fields when needed.
- If a dedicated signal response DTO is introduced later, it should mirror the current `TradeSetup.to_dict()` shape first, then add optional reasoning fields.
- Do not hardcode secrets, API keys, `.env` values, or database dumps in docs, tests, backend, or frontend.

## Test Plan For Future Reasoning Work

- Backend: run `pytest`.
- Frontend: run `npm run lint`, `npm run test` if a test script is added, and `npm run build`.
- Add or extend tests around causal behavior when reasoning uses candle history, especially ICT and price-action evidence paths.
- Keep the system limited to research, backtest, and paper trading; no auto-trading integration should be added.
