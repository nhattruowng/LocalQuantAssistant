"""Research scenario runner for backtest slicing and comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from typing import Any, Callable, Iterable, Mapping, Sequence

from backtest.models import BacktestReport


class ScenarioType(str, Enum):
    """Supported market research scenarios."""

    HIGH_VOLATILITY_PERIOD = "high_volatility_period"
    LOW_LIQUIDITY_PERIOD = "low_liquidity_period"
    REGIME_SHIFT_PERIOD = "regime_shift_period"
    TREND_MARKET = "trend_market"
    SIDEWAY_MARKET = "sideway_market"
    CRASH_LIKE_PERIOD = "crash_like_period"
    NEWS_EVENT_LIKE_PERIOD = "news_event_like_period"
    CUSTOM_DATE_RANGE = "custom_date_range"


DEFAULT_SCENARIOS: tuple[ScenarioType, ...] = (
    ScenarioType.HIGH_VOLATILITY_PERIOD,
    ScenarioType.LOW_LIQUIDITY_PERIOD,
    ScenarioType.REGIME_SHIFT_PERIOD,
    ScenarioType.TREND_MARKET,
    ScenarioType.SIDEWAY_MARKET,
    ScenarioType.CRASH_LIKE_PERIOD,
    ScenarioType.NEWS_EVENT_LIKE_PERIOD,
)


ScenarioEvaluator = Callable[[Any, str], BacktestReport]


@dataclass(frozen=True)
class ScenarioDefinition:
    """One research scenario request."""

    scenario: ScenarioType | str
    start: datetime | str | None = None
    end: datetime | str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return _scenario_name(self.scenario)


@dataclass(frozen=True)
class ScenarioRunResult:
    """Comparison result for one market scenario versus baseline."""

    scenario: str
    baseline_result: dict[str, Any]
    scenario_result: dict[str, Any]
    delta_vs_baseline: dict[str, float]
    changed_config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "baseline_result": dict(self.baseline_result),
            "scenario_result": dict(self.scenario_result),
            "delta_vs_baseline": dict(self.delta_vs_baseline),
            "changed_config": dict(self.changed_config),
        }


@dataclass(frozen=True)
class ScenarioAnalysisResult:
    """Full scenario-analysis output."""

    baseline_result: dict[str, Any]
    scenarios: list[ScenarioRunResult]
    best_scenario: ScenarioRunResult | None
    worst_scenario: ScenarioRunResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_result": dict(self.baseline_result),
            "scenarios": [item.to_dict() for item in self.scenarios],
            "best_scenario": self.best_scenario.to_dict() if self.best_scenario else None,
            "worst_scenario": self.worst_scenario.to_dict() if self.worst_scenario else None,
        }

    def to_json(self) -> str:
        return json.dumps(_json_ready(self.to_dict()), indent=2, sort_keys=True)


class ScenarioEngine:
    """Run baseline and scenario-sliced backtests through a caller-provided evaluator."""

    def run(
        self,
        features: Any,
        evaluate_fn: ScenarioEvaluator,
        scenarios: Iterable[ScenarioDefinition | ScenarioType | str] | None = None,
    ) -> ScenarioAnalysisResult:
        """Run configured scenarios without mutating the original feature data."""
        baseline_features = _copy_features(features)
        baseline_report = evaluate_fn(baseline_features, "baseline")
        baseline_summary = summarize_report(baseline_report)

        scenario_results: list[ScenarioRunResult] = []
        for scenario in _normalize_scenarios(scenarios):
            scenario_features = self.apply_scenario(features, scenario)
            scenario_report = evaluate_fn(scenario_features, scenario.name)
            scenario_summary = summarize_report(scenario_report)
            changed_config = {
                "scenario": scenario.name,
                "start": str(scenario.start) if scenario.start is not None else None,
                "end": str(scenario.end) if scenario.end is not None else None,
                "row_count": _row_count(scenario_features),
                "baseline_row_count": _row_count(features),
                **dict(scenario.metadata),
            }
            scenario_results.append(
                ScenarioRunResult(
                    scenario=scenario.name,
                    baseline_result=baseline_summary,
                    scenario_result=scenario_summary,
                    delta_vs_baseline=delta_vs_baseline(
                        baseline_summary,
                        scenario_summary,
                    ),
                    changed_config=changed_config,
                )
            )

        return ScenarioAnalysisResult(
            baseline_result=baseline_summary,
            scenarios=scenario_results,
            best_scenario=_best_scenario(scenario_results),
            worst_scenario=_worst_scenario(scenario_results),
        )

    def apply_scenario(self, features: Any, scenario: ScenarioDefinition) -> Any:
        """Return a filtered feature copy for a scenario."""
        name = scenario.name
        if _is_dataframe(features):
            return _apply_dataframe_scenario(features, name, scenario)
        if isinstance(features, Sequence) and not isinstance(features, str | bytes | bytearray):
            return _apply_sequence_scenario(features, name, scenario)
        return _copy_features(features)


def summarize_report(report: BacktestReport) -> dict[str, Any]:
    """Return a compact, JSON-friendly backtest summary."""
    return {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "mode": report.mode,
        "total_trades": report.total_trades,
        "winrate": report.winrate,
        "gross_profit": report.gross_profit,
        "gross_loss": report.gross_loss,
        "net_profit": report.net_profit,
        "profit_factor": report.profit_factor,
        "expectancy": report.expectancy,
        "max_drawdown": report.max_drawdown,
    }


def delta_vs_baseline(
    baseline_result: Mapping[str, Any],
    scenario_result: Mapping[str, Any],
) -> dict[str, float]:
    """Calculate simple numeric deltas versus baseline."""
    keys = (
        "total_trades",
        "winrate",
        "gross_profit",
        "gross_loss",
        "net_profit",
        "profit_factor",
        "expectancy",
        "max_drawdown",
    )
    return {
        key: _safe_float(scenario_result.get(key)) - _safe_float(baseline_result.get(key))
        for key in keys
    }


def _normalize_scenarios(
    scenarios: Iterable[ScenarioDefinition | ScenarioType | str] | None,
) -> list[ScenarioDefinition]:
    if scenarios is None:
        return [ScenarioDefinition(item) for item in DEFAULT_SCENARIOS]
    normalized: list[ScenarioDefinition] = []
    for item in scenarios:
        if isinstance(item, ScenarioDefinition):
            normalized.append(item)
        else:
            normalized.append(ScenarioDefinition(item))
    return normalized


def _apply_dataframe_scenario(
    features: Any,
    scenario_name: str,
    scenario: ScenarioDefinition,
) -> Any:
    data = _copy_features(features)
    if scenario_name == ScenarioType.CUSTOM_DATE_RANGE.value:
        return _filter_dataframe_by_date_range(data, scenario.start, scenario.end)

    mask = _dataframe_mask(data, scenario_name)
    if mask is None:
        return data.iloc[0:0].copy()
    return data.loc[mask].copy()


def _dataframe_mask(data: Any, scenario_name: str) -> Any | None:
    if scenario_name == ScenarioType.HIGH_VOLATILITY_PERIOD.value:
        return _volatility_level(data).isin({"HIGH", "EXTREME"}) | (_atr_percent(data) >= 0.03)
    if scenario_name == ScenarioType.LOW_LIQUIDITY_PERIOD.value:
        return _numeric_column(data, "volume_ratio", 1.0) <= 0.7
    if scenario_name == ScenarioType.REGIME_SHIFT_PERIOD.value:
        regimes = _string_column(data, "market_regime", "UNKNOWN")
        return regimes.ne(regimes.shift(1)).fillna(False)
    if scenario_name == ScenarioType.TREND_MARKET.value:
        regimes = _string_column(data, "market_regime", "UNKNOWN")
        trend_score = _numeric_column(data, "trend_score", 0.0).abs()
        return regimes.isin({"UPTREND", "DOWNTREND", "BREAKOUT_UP", "BREAKOUT_DOWN"}) | (trend_score >= 0.6)
    if scenario_name == ScenarioType.SIDEWAY_MARKET.value:
        regimes = _string_column(data, "market_regime", "UNKNOWN")
        trend_score = _numeric_column(data, "trend_score", 0.0).abs()
        return regimes.isin({"SIDEWAY", "RANGE", "RANGING"}) | (trend_score <= 0.2)
    if scenario_name == ScenarioType.CRASH_LIKE_PERIOD.value:
        returns = _close_returns(data)
        return returns <= -0.05
    if scenario_name == ScenarioType.NEWS_EVENT_LIKE_PERIOD.value:
        volume_ratio = _numeric_column(data, "volume_ratio", 1.0)
        volatility = _volatility_level(data)
        atr_percent = _atr_percent(data)
        return (volume_ratio >= 1.8) & (volatility.isin({"HIGH", "EXTREME"}) | (atr_percent >= 0.025))
    return None


def _apply_sequence_scenario(
    features: Sequence[Any],
    scenario_name: str,
    scenario: ScenarioDefinition,
) -> list[Any]:
    rows = [_copy_mapping_like(item) for item in features]
    if scenario_name == ScenarioType.CUSTOM_DATE_RANGE.value:
        return [
            row
            for row in rows
            if _row_in_date_range(_row_get(row, "timestamp"), scenario.start, scenario.end)
        ]
    return [
        row
        for index, row in enumerate(rows)
        if _row_matches_scenario(rows, index, row, scenario_name)
    ]


def _row_matches_scenario(
    rows: Sequence[Any],
    index: int,
    row: Any,
    scenario_name: str,
) -> bool:
    if scenario_name == ScenarioType.HIGH_VOLATILITY_PERIOD.value:
        return _row_volatility(row) in {"HIGH", "EXTREME"} or _row_atr_percent(row) >= 0.03
    if scenario_name == ScenarioType.LOW_LIQUIDITY_PERIOD.value:
        return _safe_float(_row_get(row, "volume_ratio"), 1.0) <= 0.7
    if scenario_name == ScenarioType.REGIME_SHIFT_PERIOD.value:
        if index == 0:
            return False
        return str(_row_get(row, "market_regime", "UNKNOWN")).upper() != str(
            _row_get(rows[index - 1], "market_regime", "UNKNOWN")
        ).upper()
    if scenario_name == ScenarioType.TREND_MARKET.value:
        regime = str(_row_get(row, "market_regime", "UNKNOWN")).upper()
        trend_score = abs(_safe_float(_row_get(row, "trend_score"), 0.0))
        return regime in {"UPTREND", "DOWNTREND", "BREAKOUT_UP", "BREAKOUT_DOWN"} or trend_score >= 0.6
    if scenario_name == ScenarioType.SIDEWAY_MARKET.value:
        regime = str(_row_get(row, "market_regime", "UNKNOWN")).upper()
        trend_score = abs(_safe_float(_row_get(row, "trend_score"), 0.0))
        return regime in {"SIDEWAY", "RANGE", "RANGING"} or trend_score <= 0.2
    if scenario_name == ScenarioType.CRASH_LIKE_PERIOD.value:
        if index == 0:
            return False
        previous_close = _safe_float(_row_get(rows[index - 1], "close"), 0.0)
        current_close = _safe_float(_row_get(row, "close"), 0.0)
        return previous_close > 0 and (current_close - previous_close) / previous_close <= -0.05
    if scenario_name == ScenarioType.NEWS_EVENT_LIKE_PERIOD.value:
        volume_ratio = _safe_float(_row_get(row, "volume_ratio"), 1.0)
        return volume_ratio >= 1.8 and (
            _row_volatility(row) in {"HIGH", "EXTREME"} or _row_atr_percent(row) >= 0.025
        )
    return False


def _filter_dataframe_by_date_range(
    data: Any,
    start: datetime | str | None,
    end: datetime | str | None,
) -> Any:
    if "timestamp" not in data:
        return data.iloc[0:0].copy()
    timestamps = _to_datetime_series(data["timestamp"])
    mask = timestamps.notna()
    start_ts = _parse_timestamp(start)
    end_ts = _parse_timestamp(end)
    if start_ts is not None:
        mask &= timestamps >= start_ts
    if end_ts is not None:
        mask &= timestamps <= end_ts
    return data.loc[mask].copy()


def _row_in_date_range(
    value: Any,
    start: datetime | str | None,
    end: datetime | str | None,
) -> bool:
    timestamp = _parse_timestamp(value)
    if timestamp is None:
        return False
    start_ts = _parse_timestamp(start)
    end_ts = _parse_timestamp(end)
    if start_ts is not None and timestamp < start_ts:
        return False
    if end_ts is not None and timestamp > end_ts:
        return False
    return True


def _volatility_level(data: Any) -> Any:
    return _string_column(data, "volatility_level", "NORMAL")


def _atr_percent(data: Any) -> Any:
    if "atr_percent" in data:
        return _numeric_column(data, "atr_percent", 0.0)
    if "atr_14" in data and "close" in data:
        close = _numeric_column(data, "close", 0.0)
        atr = _numeric_column(data, "atr_14", 0.0)
        return (atr / close.replace(0, float("nan"))).fillna(0.0)
    return _numeric_column(data, "atr_percent", 0.0)


def _close_returns(data: Any) -> Any:
    close = _numeric_column(data, "close", 0.0)
    return close.pct_change().fillna(0.0)


def _numeric_column(data: Any, column: str, default: float) -> Any:
    import pandas as pd

    if column not in data:
        return pd.Series([default] * len(data), index=data.index, dtype="float64")
    return pd.to_numeric(data[column], errors="coerce").fillna(default)


def _string_column(data: Any, column: str, default: str) -> Any:
    import pandas as pd

    if column not in data:
        return pd.Series([default] * len(data), index=data.index, dtype="object")
    return data[column].fillna(default).astype(str).str.upper()


def _to_datetime_series(value: Any) -> Any:
    import pandas as pd

    return pd.to_datetime(value, errors="coerce", utc=True)


def _parse_timestamp(value: datetime | str | Any | None) -> Any | None:
    if value is None:
        return None
    try:
        import pandas as pd

        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        return None if pd.isna(parsed) else parsed
    except (TypeError, ValueError):
        return None


def _copy_features(features: Any) -> Any:
    if hasattr(features, "copy"):
        try:
            return features.copy(deep=True)
        except TypeError:
            return features.copy()
    if isinstance(features, Sequence) and not isinstance(features, str | bytes | bytearray):
        return [_copy_mapping_like(item) for item in features]
    return features


def _copy_mapping_like(value: Any) -> Any:
    if isinstance(value, Mapping):
        return dict(value)
    return value


def _is_dataframe(value: Any) -> bool:
    return hasattr(value, "loc") and hasattr(value, "iloc") and hasattr(value, "copy")


def _row_count(value: Any) -> int:
    try:
        return int(len(value))
    except TypeError:
        return 0


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _row_volatility(row: Any) -> str:
    return str(_row_get(row, "volatility_level", "NORMAL")).upper()


def _row_atr_percent(row: Any) -> float:
    atr_percent = _safe_float(_row_get(row, "atr_percent"), 0.0)
    if atr_percent > 0.0:
        return atr_percent
    atr = _safe_float(_row_get(row, "atr_14"), 0.0)
    close = _safe_float(_row_get(row, "close"), 0.0)
    return atr / close if close > 0.0 else 0.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _scenario_name(value: ScenarioType | str) -> str:
    if isinstance(value, ScenarioType):
        return value.value
    return str(value)


def _best_scenario(results: list[ScenarioRunResult]) -> ScenarioRunResult | None:
    return max(results, key=lambda item: _safe_float(item.scenario_result.get("net_profit")), default=None)


def _worst_scenario(results: list[ScenarioRunResult]) -> ScenarioRunResult | None:
    return min(results, key=lambda item: _safe_float(item.scenario_result.get("net_profit")), default=None)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, float):
        if value == float("inf"):
            return "Infinity"
        if value == float("-inf"):
            return "-Infinity"
    return value
