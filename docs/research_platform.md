# Research Platform Integration Guide

## 1. Purpose

This document summarizes how backend intelligence and frontend dashboards are integrated for research operations.

It focuses on:
- Signal (legacy + reasoning-enhanced)
- Decision trace transparency
- Backtest analytics and ablation
- Model drift monitoring
- RiskGuard controls

## 2. Signal API Response Modes

### 2.1 Legacy-compatible signal

Core fields remain available:
- `symbol`
- `timeframe`
- `signal`
- `confidence`
- `entry`
- `stop_loss`
- `take_profit_1`
- `take_profit_2`
- `risk_reward`
- `reasons`

### 2.2 Reasoning-enhanced signal

When Market Reasoning Brain is enabled, response includes:
- `reasoning_decision`
  - `final_signal`
  - `setup_type`
  - `confluence_score`
  - `evidence_for[]`
  - `evidence_against[]`
  - `warnings[]`
  - `conflict_level`
  - `decision_trace`

Contract reference:
- `tests/test_signal_engine.py` verifies:
  - legacy mode can keep `reasoning_decision = null`
  - reasoning mode includes `reasoning_decision` and `decision_trace`

## 3. Decision Trace Contract

`decision_trace` structure:
- `trace_id`
- `symbol`
- `timeframe`
- `steps[]`
  - `step_name`
  - `input_score`
  - `output_score`
  - `delta`
  - `passed`
  - `details`
  - `warnings[]`
  - `timestamp`
- `final_signal`
- `final_confidence`
- `wait_reason`
- `warnings[]`

Contract reference:
- `tests/test_decision_trace.py`

## 4. Backtest Analytics Contract

Backtest summary includes:
- headline performance metrics
- `grouped` segment analytics
- `trades[]`

Research-level analytics include grouped dimensions:
- `regime`
- `strategy`
- `setup_type`
- `setup_grade`
- `signal`
- `wait_reason`
- `safety_filter`
- `model_scope`
- `probability_source`
- `conflict_level`
- `confluence_bucket`

Contract reference:
- `tests/test_backtest_analyzer_ablation.py`

## 5. Drift Report Contract

Model drift endpoint returns:
- `symbol`
- `timeframe`
- `model_id`
- `model_version`
- `report`
  - `drift_level`
  - `drift_score`
  - `drifted_features[]`
  - `prediction_shift`
  - `calibration_shift`
  - `regime_shift`
  - `recommended_action`

Contract reference:
- `tests/test_drift_monitoring.py`

## 6. Frontend Research Dashboards

### Backtest Page
- Overall metrics
- Equity curve
- Drawdown curve
- Slice analytics by regime/strategy/setup_type/wait_reason/conflict_level
- Wait reason distribution
- Ablation result table

### Model Page
- Model version/status card
- Calibration panel
- Drift report card
- Drifted features table

### Risk Page
- RiskGuard state and limits
- Paper trading analytics
- Risk events table

## 7. Safety Constraint

The platform is strictly research-first:
- no automated real-money execution
- no live order placement path
- outputs are advisory and must be human-reviewed
