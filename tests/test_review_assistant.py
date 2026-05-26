"""Tests for human review and safe research assistant."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from research_assistant.hypothesis_generator import HypothesisGenerator
from research_assistant.trace_summarizer import TraceSummarizer, validate_assistant_output
from review.review_repository import ReviewRepository
from review.signal_review import SignalReview


def test_save_review(tmp_path) -> None:
    repository = ReviewRepository(tmp_path)
    review = SignalReview(
        review_id="review-1",
        signal_id="signal-1",
        symbol="BTC/USDT",
        timeframe="1h",
        final_signal="BUY",
        setup_type="CLEAN_BREAKOUT",
        confluence_score=0.72,
        decision_trace_id="trace-1",
        user_feedback="Good structure, but execution was late.",
        tags=["late-entry"],
    )

    repository.save(review)
    loaded = repository.load("review-1")

    assert loaded.review_id == "review-1"
    assert loaded.signal_id == "signal-1"
    assert loaded.user_feedback == "Good structure, but execution was late."
    assert loaded.tags == ["late-entry"]


def test_override_does_not_change_original_signal() -> None:
    review = SignalReview(
        signal_id="signal-2",
        symbol="ETH/USDT",
        timeframe="4h",
        final_signal="SELL",
    )

    updated = review.with_feedback(
        user_override="manual_reject",
        override_reason="Risk context unclear.",
        tags=["risk-review"],
    )

    assert review.final_signal == "SELL"
    assert updated.final_signal == "SELL"
    assert updated.user_override == "manual_reject"
    assert updated.override_reason == "Risk context unclear."


def test_llm_output_matches_safe_json_schema() -> None:
    trace = {
        "trace_id": "trace-1",
        "steps": [
            {
                "step_name": "conflict_check",
                "passed": False,
                "warnings": ["BUY and SELL wording should be scrubbed."],
            }
        ],
        "warnings": ["WAIT wording should be scrubbed."],
    }

    response = TraceSummarizer().summarize(trace).to_dict()

    assert validate_assistant_output(response) is True
    assert response["forbidden_actions_checked"] == {
        "no_trade_signal_generated": True,
        "no_riskguard_override": True,
        "no_live_config_change": True,
    }
    payload = json.dumps(response)
    assert "BUY" not in payload
    assert "SELL" not in payload
    assert "WAIT" not in payload


def test_hypothesis_generator_output_matches_schema() -> None:
    response = HypothesisGenerator().generate(
        review={"confluence_score": 0.55, "user_override": "manual_reject"},
        decision_trace={"steps": [{"step_name": "risk_check", "passed": False}]},
        backtest_metrics={"expectancy": -0.1},
    ).to_dict()

    assert validate_assistant_output(response) is True
    assert response["hypotheses"]
    assert response["recommended_backtests"]


def test_weekly_report_runs(tmp_path) -> None:
    repository = ReviewRepository(tmp_path)
    now = datetime.now(UTC)
    repository.save(
        SignalReview(
            review_id="review-weekly",
            signal_id="signal-weekly",
            symbol="BTC/USDT",
            timeframe="1h",
            final_signal="WAIT",
            user_feedback="Needs follow-up.",
            user_override="manual_reject",
            override_reason="Data quality concern.",
            tags=["data-quality"],
            created_at=now,
        )
    )

    report = repository.weekly_report(
        week_start=now - timedelta(days=1),
        week_end=now + timedelta(days=1),
    )

    assert report["total_reviews"] == 1
    assert report["override_count"] == 1
    assert report["by_symbol"] == {"BTC/USDT": 1}
    assert report["forbidden_actions_checked"]["no_trade_signal_generated"] is True
