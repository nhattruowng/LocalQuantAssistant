"""Tests for YAML config loading."""

from __future__ import annotations

import pytest

from config.loader import load_settings
from config.reasoning_config import get_reasoning_config


def test_load_settings_from_yaml(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        """
app:
  name: Test App
  environment: test
database:
  driver: sqlite
  path: test.db
logging:
  level: DEBUG
  serialize: false
""",
        encoding="utf-8",
    )

    settings = load_settings(config_file)

    assert settings.app.name == "Test App"
    assert settings.database.driver == "sqlite"
    assert settings.logging.level == "DEBUG"


def test_load_reasoning_config_from_yaml(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        """
reasoning_brain:
  enabled: false
  min_confluence_score: 0.68
  medium_score_threshold: 0.58
  strong_conflict_threshold: 0.25
  allow_reduced_size_for_medium_score: true
  max_conflict_penalty: 0.30
trace:
  enabled: true
  include_evidence: true
  include_score_delta: true
  include_config_hash: true
  include_model_version: true
risk_guard:
  hard_block_data_quality_fail: true
  hard_block_extreme_volatility: true
  hard_block_daily_drawdown: true
  hard_block_risk_reward_fail: true
""",
        encoding="utf-8",
    )

    settings = load_settings(config_file)
    reasoning_config = get_reasoning_config(settings)

    assert reasoning_config.reasoning_brain.enabled is False
    assert reasoning_config.reasoning_brain.min_confluence_score == 0.68
    assert reasoning_config.reasoning_brain.medium_score_threshold == 0.58
    assert reasoning_config.reasoning_brain.strong_conflict_threshold == 0.25
    assert reasoning_config.reasoning_brain.allow_reduced_size_for_medium_score is True
    assert reasoning_config.reasoning_brain.max_conflict_penalty == 0.30
    assert reasoning_config.trace.enabled is True
    assert reasoning_config.trace.include_evidence is True
    assert reasoning_config.trace.include_score_delta is True
    assert reasoning_config.trace.include_config_hash is True
    assert reasoning_config.trace.include_model_version is True
    assert settings.risk_guard.hard_block_data_quality_fail is True
    assert settings.risk_guard.hard_block_extreme_volatility is True
    assert settings.risk_guard.hard_block_daily_drawdown is True
    assert settings.risk_guard.hard_block_risk_reward_fail is True


def test_reasoning_config_missing_fields_uses_safe_defaults(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text("app:\n  name: Minimal\n", encoding="utf-8")

    settings = load_settings(config_file)
    reasoning_config = get_reasoning_config(settings)

    assert reasoning_config.reasoning_brain.enabled is False
    assert reasoning_config.reasoning_brain.min_confluence_score == 0.68
    assert reasoning_config.trace.enabled is True
    assert reasoning_config.trace.include_evidence is True
    assert settings.risk_guard.hard_block_data_quality_fail is True
    assert settings.risk_guard.hard_block_extreme_volatility is True
    assert settings.risk_guard.hard_block_daily_drawdown is True
    assert settings.risk_guard.hard_block_risk_reward_fail is True


def test_reasoning_config_invalid_values_raise_clear_error(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        """
reasoning_brain:
  enabled: false
  min_confluence_score: 1.2
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="reasoning_brain.min_confluence_score must be between 0 and 1",
    ):
        load_settings(config_file)
