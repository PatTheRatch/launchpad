"""Unit tests for the mock World Cup service (no network)."""

from __future__ import annotations

from launchpad.services.experimental.mock_world_cup_service import MockWorldCupService


def test_fetch_returns_three_teams() -> None:
    watchlist = MockWorldCupService().fetch()
    assert len(watchlist.teams) == 3


def test_fetch_team_codes_in_order() -> None:
    watchlist = MockWorldCupService().fetch()
    assert [team.team_code for team in watchlist.teams] == ["USA", "FRA", "SEN"]


def test_fetch_retrieved_at_is_timezone_aware() -> None:
    watchlist = MockWorldCupService().fetch()
    assert watchlist.retrieved_at.tzinfo is not None


def test_name() -> None:
    assert MockWorldCupService().name == "mock:world-cup"
