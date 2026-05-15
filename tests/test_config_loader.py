"""Tests for YAML config loading."""

from __future__ import annotations

from config.loader import load_settings


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
