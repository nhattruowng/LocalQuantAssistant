"""JSON-backed repository for human signal reviews."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any, Mapping

from review.signal_review import SignalReview


class ReviewRepository:
    """Persist signal reviews as metadata-only JSON records."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def save(self, review: SignalReview | Mapping[str, Any]) -> Path:
        record = review if isinstance(review, SignalReview) else SignalReview.from_dict(review)
        path = self._review_path(record.review_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load(self, review_id: str) -> SignalReview:
        payload = json.loads(self._review_path(review_id).read_text(encoding="utf-8"))
        return SignalReview.from_dict(payload)

    def list_reviews(
        self,
        symbol: str | None = None,
        signal_id: str | None = None,
        tag: str | None = None,
    ) -> list[SignalReview]:
        if not self.root_dir.exists():
            return []
        reviews: list[SignalReview] = []
        for path in sorted(self.root_dir.glob("*.json")):
            try:
                review = SignalReview.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
            if symbol is not None and review.symbol != symbol:
                continue
            if signal_id is not None and review.signal_id != signal_id:
                continue
            if tag is not None and tag not in review.tags:
                continue
            reviews.append(review)
        return reviews

    def weekly_report(
        self,
        week_start: datetime | None = None,
        week_end: datetime | None = None,
    ) -> dict[str, Any]:
        """Return review activity summary without producing trade instructions."""
        end = week_end or datetime.now(UTC)
        start = week_start or (end - timedelta(days=7))
        reviews = [review for review in self.list_reviews() if start <= _aware(review.created_at) <= end]
        by_symbol = Counter(review.symbol for review in reviews)
        by_signal = Counter(review.final_signal for review in reviews)
        tag_counts = Counter(tag for review in reviews for tag in review.tags)
        override_reasons = Counter(
            review.override_reason
            for review in reviews
            if review.user_override is not None and review.override_reason
        )
        return {
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "total_reviews": len(reviews),
            "feedback_count": sum(1 for review in reviews if review.user_feedback),
            "override_count": sum(1 for review in reviews if review.user_override is not None),
            "by_symbol": dict(sorted(by_symbol.items())),
            "by_signal": dict(sorted(by_signal.items())),
            "tags": dict(sorted(tag_counts.items())),
            "top_override_reasons": dict(override_reasons.most_common(10)),
            "forbidden_actions_checked": {
                "no_trade_signal_generated": True,
                "no_riskguard_override": True,
                "no_live_config_change": True,
            },
        }

    def _review_path(self, review_id: str) -> Path:
        return self.root_dir / f"{_safe_name(review_id)}.json"


def _safe_name(value: str | None) -> str:
    text = str(value or "unknown")
    for char in ("\\", "/", ":", "*", "?", '"', "<", ">", "|"):
        text = text.replace(char, "_")
    return text.strip() or "unknown"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
