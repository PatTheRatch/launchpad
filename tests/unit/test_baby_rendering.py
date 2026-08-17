"""Rendering tests for the experimental baby "last feed" section."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.features import FeatureFlags
from launchpad.models.experimental.baby import BabySnapshot, Feed, FeedType
from launchpad.models.result import Result
from launchpad.preview import PORTRAIT_SIZE, build_mock_baby_snapshot
from launchpad.rendering.portrait import PortraitRenderer, _elapsed_text, _feed_detail

LONDON = ZoneInfo("Europe/London")
OVERNIGHT = datetime(2026, 6, 15, 3, 0, tzinfo=LONDON)


def render_with_baby(baby: Result[BabySnapshot]) -> Image.Image:
    state = DashboardStateBuilder().build(
        OVERNIGHT, DashboardInputs(baby=baby), FeatureFlags(baby_tracking=True)
    )
    frame = PortraitRenderer().render(state, PORTRAIT_SIZE)
    assert isinstance(frame.buffer, Image.Image)
    return frame.buffer


def test_baby_section_renders_valid_frame() -> None:
    buffer = render_with_baby(Result.present(build_mock_baby_snapshot()))

    assert buffer.mode == "1"
    assert buffer.size == (480, 800)


def test_baby_section_renders_breast_feed() -> None:
    started = OVERNIGHT - timedelta(hours=1)
    snapshot = BabySnapshot(
        last_feed=Feed(
            feed_type=FeedType.BREAST,
            started_at=started,
            ended_at=started + timedelta(minutes=6),
            side="right",
            duration_seconds=360.0,
        ),
        retrieved_at=OVERNIGHT,
    )

    buffer = render_with_baby(Result.present(snapshot))

    assert buffer.size == (480, 800)


def test_baby_section_renders_placeholder_when_no_feeds_logged() -> None:
    buffer = render_with_baby(Result.present(BabySnapshot(retrieved_at=OVERNIGHT)))

    assert buffer.size == (480, 800)


def test_baby_section_renders_placeholder_when_unavailable() -> None:
    buffer = render_with_baby(Result.unavailable())

    assert buffer.size == (480, 800)


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #


def test_elapsed_text_humanizes_durations() -> None:
    assert _elapsed_text(timedelta(seconds=30)) == "Just now"
    assert _elapsed_text(timedelta(minutes=5)) == "5m ago"
    assert _elapsed_text(timedelta(hours=1, minutes=20)) == "1h 20m ago"
    assert _elapsed_text(timedelta(hours=2)) == "2h ago"
    assert _elapsed_text(timedelta(days=1, hours=3)) == "1d 3h ago"
    assert _elapsed_text(timedelta(days=2)) == "2d ago"


def test_elapsed_text_never_goes_negative() -> None:
    # Clock skew between the feed's end and the frame timestamp must not
    # produce nonsense like "-1m ago".
    assert _elapsed_text(timedelta(seconds=-90)) == "Just now"


def test_feed_detail_for_each_feed_type() -> None:
    when = OVERNIGHT
    formula = Feed(FeedType.FORMULA, when, when, amount_ml=80.0)
    bottle = Feed(FeedType.BOTTLE, when, when, amount_ml=118.294)
    breast = Feed(
        FeedType.BREAST, when, when + timedelta(minutes=6), side="right", duration_seconds=360.0
    )

    assert _feed_detail(formula) == "Formula · 80ml"
    assert _feed_detail(bottle) == "Bottle · 118ml"
    assert _feed_detail(breast) == "Breast · right · 6m"


def test_feed_detail_omits_missing_fields() -> None:
    when = OVERNIGHT
    assert _feed_detail(Feed(FeedType.FORMULA, when, when)) == "Formula"
    assert _feed_detail(Feed(FeedType.BREAST, when, when)) == "Breast"
