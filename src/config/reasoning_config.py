"""Feature-flag config helpers for market reasoning and decision traces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TYPE_CHECKING

from config.settings import ReasoningBrainSettings, TraceSettings

if TYPE_CHECKING:
    from config.settings import Settings


@dataclass(frozen=True)
class ReasoningConfig:
    """Combined reasoning feature flags used by callers that only need this slice."""

    reasoning_brain: ReasoningBrainSettings
    trace: TraceSettings


def parse_reasoning_brain_config(raw_config: object) -> ReasoningBrainSettings:
    """Parse reasoning-brain settings with safe defaults and clear validation errors."""
    config = _mapping(raw_config, "reasoning_brain")
    settings = ReasoningBrainSettings(
        enabled=_bool(config, "enabled", False, "reasoning_brain"),
        min_confluence_score=_float(
            config,
            "min_confluence_score",
            0.68,
            "reasoning_brain",
        ),
        medium_score_threshold=_float(
            config,
            "medium_score_threshold",
            0.58,
            "reasoning_brain",
        ),
        strong_conflict_threshold=_float(
            config,
            "strong_conflict_threshold",
            0.25,
            "reasoning_brain",
        ),
        allow_reduced_size_for_medium_score=_bool(
            config,
            "allow_reduced_size_for_medium_score",
            True,
            "reasoning_brain",
        ),
        max_conflict_penalty=_float(
            config,
            "max_conflict_penalty",
            0.30,
            "reasoning_brain",
        ),
    )
    validate_reasoning_brain_settings(settings)
    return settings


def parse_trace_config(raw_config: object) -> TraceSettings:
    """Parse decision-trace settings with safe defaults and clear validation errors."""
    config = _mapping(raw_config, "trace")
    return TraceSettings(
        enabled=_bool(config, "enabled", True, "trace"),
        include_evidence=_bool(config, "include_evidence", True, "trace"),
        include_score_delta=_bool(config, "include_score_delta", True, "trace"),
        include_config_hash=_bool(config, "include_config_hash", True, "trace"),
        include_model_version=_bool(config, "include_model_version", True, "trace"),
    )


def validate_reasoning_brain_settings(settings: ReasoningBrainSettings) -> None:
    """Validate reasoning-brain thresholds before runtime decisioning uses them."""
    _require_unit_interval(
        settings.min_confluence_score,
        "reasoning_brain.min_confluence_score",
    )
    _require_unit_interval(
        settings.medium_score_threshold,
        "reasoning_brain.medium_score_threshold",
    )
    if settings.medium_score_threshold > settings.min_confluence_score:
        raise ValueError(
            "reasoning_brain.medium_score_threshold must not exceed "
            "reasoning_brain.min_confluence_score."
        )
    _require_unit_interval(
        settings.strong_conflict_threshold,
        "reasoning_brain.strong_conflict_threshold",
    )
    _require_unit_interval(
        settings.max_conflict_penalty,
        "reasoning_brain.max_conflict_penalty",
    )


def get_reasoning_config(
    settings: "Settings | None" = None,
    config_path: str | Path | None = None,
) -> ReasoningConfig:
    """Return the reasoning-related config slice without enabling new logic by default."""
    if settings is None:
        from config.loader import load_settings

        settings = load_settings(config_path)
    return ReasoningConfig(
        reasoning_brain=settings.reasoning_brain,
        trace=settings.trace,
    )


def _mapping(raw_config: object, section: str) -> Mapping[str, object]:
    if raw_config is None:
        return {}
    if not isinstance(raw_config, Mapping):
        raise ValueError(f"{section} config must be a mapping.")
    return raw_config


def _bool(
    config: Mapping[str, object],
    key: str,
    default: bool,
    section: str,
) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    raise ValueError(f"{section}.{key} must be a boolean.")


def _float(
    config: Mapping[str, object],
    key: str,
    default: float,
    section: str,
) -> float:
    value = config.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{section}.{key} must be a number.")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{section}.{key} must be a number.") from error


def _require_unit_interval(value: float, label: str) -> None:
    if value < 0 or value > 1:
        raise ValueError(f"{label} must be between 0 and 1.")
