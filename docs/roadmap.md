# LocalQuant Roadmap

## Current Milestone: Research Platform Integration

Completed integration scope:

1. Market Reasoning Brain
- Evidence-for / evidence-against modeling
- Confluence scoring
- Conflict detection and traceable decisions

2. RiskGuard hard-block controls
- Block/cooldown state surfaced in API/UI
- Drawdown and streak-based risk constraints

3. BacktestAnalyzer deep analytics
- Multi-dimensional grouping
- Wait reason distribution
- Conflict-level and confluence-bucket segmentation
- Ablation-study outputs

4. Model monitoring
- Calibration diagnostics
- Drift report and drifted feature exposure

5. Frontend dashboards
- Backtest research dashboard
- Model diagnostics dashboard
- RiskGuard operations dashboard

6. Safety boundary
- Explicit non-auto-trading policy maintained

## Next Milestone: Reliability & Quality Gates

1. Backend runtime standardization
- Move from MSYS Python runtime to supported CPython runtime
- Stabilize dependency install pipeline for CI and local contributors

2. Full CI quality gate
- Backend full pytest on every merge
- Frontend lint/test/build on every merge
- API contract snapshot checks

3. E2E integration tests
- Seed market symbol presets (`XAUUSD`, `BTCUSDT`)
- Signal request -> reasoning render -> decision trace render
- Backtest page render and analytics integrity checks

4. Performance improvements
- FE bundle split for large chart modules
- Backtest/report payload compression options

## Medium-Term Milestone: Assisted Research Workbench

1. Scenario comparison workflows
- Parameter sweeps and side-by-side result diff

2. Drift-aware retraining assistant
- Trigger recommendations based on drift and calibration degradation

3. Research audit trail
- Persist decision trace and evidence snapshots per signal revision

## Long-Term Milestone: Governance-Ready Research Stack

1. Reproducible experiment manifests
2. Data lineage and feature provenance
3. Role-based review workflow for strategy promotion

## Non-Negotiable Principle

No auto trade execution in live markets.

LocalQuant remains a research and decision-support platform, not a live trading bot.
