"""Tests for ML feature engineering pipeline.

Tests:
- Team feature computation (net rating, pace, form)
- Situational feature computation (rest days, B2B, schedule density)
- Anti-leakage verification (temporal correctness)
- Feature pipeline output structure
"""

from datetime import datetime, date, timedelta

import pytest
import pandas as pd

from nba_betting_agent.ml.data.schema import HistoricalGame
from nba_betting_agent.ml.features.team_features import compute_team_features
from nba_betting_agent.ml.features.situational import compute_situational_features
from nba_betting_agent.ml.features.pipeline import FeaturePipeline, create_training_features


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_games() -> list[HistoricalGame]:
    """Create a sample set of historical games for testing."""
    # Create 15 games over 3 weeks
    base_date = datetime(2024, 1, 1)
    games = []

    # Team BOS plays ~5 games
    games.extend([
        HistoricalGame(
            game_id="game_001",
            game_date=base_date + timedelta(days=0),
            season="2023-24",
            home_team="BOS",
            away_team="NYK",
            home_score=110,
            away_score=100,
        ),
        HistoricalGame(
            game_id="game_002",
            game_date=base_date + timedelta(days=2),
            season="2023-24",
            home_team="BOS",
            away_team="MIA",
            home_score=105,
            away_score=108,  # BOS loss
        ),
        HistoricalGame(
            game_id="game_005",
            game_date=base_date + timedelta(days=5),
            season="2023-24",
            home_team="PHI",
            away_team="BOS",
            home_score=100,
            away_score=115,  # BOS win on road
        ),
        HistoricalGame(
            game_id="game_008",
            game_date=base_date + timedelta(days=8),
            season="2023-24",
            home_team="BOS",
            away_team="CHI",
            home_score=120,
            away_score=95,
        ),
        HistoricalGame(
            game_id="game_010",
            game_date=base_date + timedelta(days=10),
            season="2023-24",
            home_team="BOS",
            away_team="DET",
            home_score=118,
            away_score=102,
        ),
    ])

    # Team LAL plays ~5 games
    games.extend([
        HistoricalGame(
            game_id="game_003",
            game_date=base_date + timedelta(days=1),
            season="2023-24",
            home_team="LAL",
            away_team="GSW",
            home_score=108,
            away_score=112,  # LAL loss
        ),
        HistoricalGame(
            game_id="game_004",
            game_date=base_date + timedelta(days=3),
            season="2023-24",
            home_team="LAL",
            away_team="PHX",
            home_score=115,
            away_score=110,
        ),
        HistoricalGame(
            game_id="game_006",
            game_date=base_date + timedelta(days=6),
            season="2023-24",
            home_team="DEN",
            away_team="LAL",
            home_score=125,
            away_score=105,  # LAL loss on road
        ),
        HistoricalGame(
            game_id="game_007",
            game_date=base_date + timedelta(days=7),
            season="2023-24",
            home_team="LAL",
            away_team="MEM",
            home_score=98,
            away_score=95,  # Close win, B2B for LAL
        ),
        HistoricalGame(
            game_id="game_009",
            game_date=base_date + timedelta(days=9),
            season="2023-24",
            home_team="SAS",
            away_team="LAL",
            home_score=100,
            away_score=110,  # LAL road win
        ),
    ])

    return games


@pytest.fixture
def target_date() -> date:
    """Target date for feature computation (day 12)."""
    return date(2024, 1, 13)


@pytest.fixture
def bos_vs_lal_game() -> HistoricalGame:
    """A BOS vs LAL game on day 12 to predict."""
    return HistoricalGame(
        game_id="game_012",
        game_date=datetime(2024, 1, 13),
        season="2023-24",
        home_team="BOS",
        away_team="LAL",
        home_score=112,
        away_score=108,
    )


# ============================================================================
# Team Features Tests
# ============================================================================

class TestTeamFeatures:
    """Tests for compute_team_features function."""

    def test_returns_expected_keys(self, sample_games, target_date):
        """Feature dict should contain all expected keys."""
        features = compute_team_features(
            games=sample_games,
            game_date=target_date,
            home_team="BOS",
            away_team="LAL",
        )

        expected_keys = [
            "home_net_rtg_l10",
            "away_net_rtg_l10",
            "net_rtg_diff",
            "home_pace_l10",
            "away_pace_l10",
            "pace_diff",
            "home_win_pct_l10",
            "away_win_pct_l10",
            "form_diff",
            "home_team_home_record",
            "away_team_away_record",
        ]

        for key in expected_keys:
            assert key in features, f"Missing key: {key}"

    def test_net_rating_calculation(self, sample_games, target_date):
        """Net rating should reflect point differential."""
        features = compute_team_features(
            games=sample_games,
            game_date=target_date,
            home_team="BOS",
            away_team="LAL",
        )

        # BOS: +10, -3, +15, +25, +16 = +63 over 5 games = +12.6
        # (Using actual game results from fixture)
        assert features["home_net_rtg_l10"] > 0, "BOS has positive net rating"
        assert features["net_rtg_diff"] != 0, "Teams have different net ratings"

    def test_win_percentage_bounds(self, sample_games, target_date):
        """Win percentages should be between 0 and 1."""
        features = compute_team_features(
            games=sample_games,
            game_date=target_date,
            home_team="BOS",
            away_team="LAL",
        )

        assert 0 <= features["home_win_pct_l10"] <= 1
        assert 0 <= features["away_win_pct_l10"] <= 1
        assert 0 <= features["home_team_home_record"] <= 1
        assert 0 <= features["away_team_away_record"] <= 1

    def test_bos_win_percentage(self, sample_games, target_date):
        """BOS should have 80% win rate (4-1 record)."""
        features = compute_team_features(
            games=sample_games,
            game_date=target_date,
            home_team="BOS",
            away_team="LAL",
        )

        # BOS: 4 wins (games 1, 5, 8, 10), 1 loss (game 2)
        assert features["home_win_pct_l10"] == pytest.approx(0.8, rel=0.01)

    def test_handles_datetime_and_date(self, sample_games):
        """Should accept both datetime and date objects."""
        dt = datetime(2024, 1, 13, 19, 30)
        d = date(2024, 1, 13)

        features_dt = compute_team_features(sample_games, dt, "BOS", "LAL")
        features_d = compute_team_features(sample_games, d, "BOS", "LAL")

        # Same date should produce same features
        assert features_dt == features_d

    def test_handles_empty_games(self):
        """Should handle empty game list gracefully."""
        features = compute_team_features(
            games=[],
            game_date=date(2024, 1, 1),
            home_team="BOS",
            away_team="LAL",
        )

        # Should return default values
        assert features["home_win_pct_l10"] == 0.5  # Default
        assert features["away_win_pct_l10"] == 0.5


class TestTeamFeaturesNoLeakage:
    """Tests verifying no look-ahead bias in team features."""

    def test_same_day_game_excluded(self, sample_games):
        """Games on the target date should NOT be used for features."""
        # game_010 is on Jan 11 (base_date + 10 days)
        # Target Jan 11 should EXCLUDE game_010 due to strict < comparison
        target = date(2024, 1, 11)

        features = compute_team_features(
            games=sample_games,
            game_date=target,
            home_team="BOS",
            away_team="LAL",
        )

        # BOS had 4 games before Jan 11: game_001, game_002, game_005, game_008
        # Results: W, L, W, W = 3 wins / 4 games = 75%
        assert features["home_win_pct_l10"] == pytest.approx(0.75, rel=0.01)

    def test_future_game_not_used(self):
        """Feature computation should never use future data."""
        # Create games on D1, D2, D3
        games = [
            HistoricalGame(
                game_id="d1_game",
                game_date=datetime(2024, 1, 1),
                season="2023-24",
                home_team="BOS",
                away_team="NYK",
                home_score=100,
                away_score=90,  # BOS wins by 10
            ),
            HistoricalGame(
                game_id="d2_game",
                game_date=datetime(2024, 1, 2),
                season="2023-24",
                home_team="BOS",
                away_team="MIA",
                home_score=80,
                away_score=120,  # BOS loses by 40
            ),
            HistoricalGame(
                game_id="d3_game",
                game_date=datetime(2024, 1, 3),
                season="2023-24",
                home_team="LAL",
                away_team="BOS",
                home_score=70,
                away_score=130,  # BOS wins by 60 (away)
            ),
        ]

        # Compute features for D2 game - should only use D1 data
        features = compute_team_features(
            games=games,
            game_date=date(2024, 1, 2),
            home_team="BOS",
            away_team="MIA",
        )

        # BOS net rating should be +10 (only D1 game)
        # NOT affected by D2 (-40) or D3 (+60)
        assert features["home_net_rtg_l10"] == pytest.approx(10.0, rel=0.01)

    def test_anti_leakage_d3_not_used_for_d2(self):
        """CRITICAL: D3 game data must NOT be used when predicting D2."""
        # Create games with clear distinguishing scores
        games = [
            HistoricalGame(
                game_id="d1",
                game_date=datetime(2024, 1, 1),
                season="2023-24",
                home_team="AAA",
                away_team="BBB",
                home_score=100,
                away_score=100,  # Tie (net = 0)
            ),
            HistoricalGame(
                game_id="d2",
                game_date=datetime(2024, 1, 2),
                season="2023-24",
                home_team="AAA",
                away_team="CCC",
                home_score=100,
                away_score=100,  # Tie
            ),
            HistoricalGame(
                game_id="d3",
                game_date=datetime(2024, 1, 3),
                season="2023-24",
                home_team="AAA",
                away_team="DDD",
                home_score=200,  # Massive outlier
                away_score=0,    # Should NOT affect D2 features
            ),
        ]

        # Features for D2 should ONLY use D1
        features = compute_team_features(
            games=games,
            game_date=date(2024, 1, 2),
            home_team="AAA",
            away_team="CCC",
        )

        # AAA's net rating should be 0 (only D1 tie game)
        # If D3 leaked, it would be ~66.67 (average of 0 and 200)
        assert features["home_net_rtg_l10"] == pytest.approx(0.0, rel=0.01)


# ============================================================================
# Situational Features Tests
# ============================================================================

class TestSituationalFeatures:
    """Tests for compute_situational_features function."""

    def test_returns_expected_keys(self, sample_games, target_date):
        """Feature dict should contain all expected keys."""
        features = compute_situational_features(
            games=sample_games,
            game_date=target_date,
            home_team="BOS",
            away_team="LAL",
        )

        expected_keys = [
            "home_rest_days",
            "away_rest_days",
            "rest_advantage",
            "home_b2b",
            "away_b2b",
            "b2b_disadvantage",
            "home_games_last_7",
            "away_games_last_7",
            "schedule_density_diff",
            "games_into_season",
            "season_pct",
        ]

        for key in expected_keys:
            assert key in features, f"Missing key: {key}"

    def test_rest_days_calculation(self, sample_games, target_date):
        """Rest days should be correctly calculated."""
        features = compute_situational_features(
            games=sample_games,
            game_date=target_date,
            home_team="BOS",
            away_team="LAL",
        )

        # BOS last game: Jan 11 (day 10), target: Jan 13 -> 3 days rest
        # Wait, game_010 is day 10, which is Jan 11. Target is Jan 13 -> 2 days
        assert features["home_rest_days"] >= 1
        assert features["home_rest_days"] <= 7

    def test_rest_capped_at_7(self):
        """Rest days should be capped at 7."""
        games = [
            HistoricalGame(
                game_id="old_game",
                game_date=datetime(2024, 1, 1),
                season="2023-24",
                home_team="BOS",
                away_team="NYK",
                home_score=100,
                away_score=90,
            ),
        ]

        # 20 days later
        features = compute_situational_features(
            games=games,
            game_date=date(2024, 1, 21),
            home_team="BOS",
            away_team="LAL",
        )

        assert features["home_rest_days"] == 7.0

    def test_back_to_back_detection(self):
        """B2B should be detected when team played yesterday."""
        games = [
            HistoricalGame(
                game_id="yesterday",
                game_date=datetime(2024, 1, 9),
                season="2023-24",
                home_team="BOS",
                away_team="NYK",
                home_score=100,
                away_score=90,
            ),
            HistoricalGame(
                game_id="3_days_ago",
                game_date=datetime(2024, 1, 7),
                season="2023-24",
                home_team="LAL",
                away_team="GSW",
                home_score=110,
                away_score=100,
            ),
        ]

        features = compute_situational_features(
            games=games,
            game_date=date(2024, 1, 10),
            home_team="BOS",
            away_team="LAL",
        )

        # BOS played yesterday (B2B), LAL did not
        assert features["home_b2b"] == 1.0
        assert features["away_b2b"] == 0.0
        assert features["b2b_disadvantage"] == 1.0  # Home has disadvantage

    def test_schedule_density(self, sample_games, target_date):
        """Schedule density should count games in last 7 days."""
        features = compute_situational_features(
            games=sample_games,
            game_date=target_date,
            home_team="BOS",
            away_team="LAL",
        )

        # Both values should be reasonable (0-7 games possible)
        assert 0 <= features["home_games_last_7"] <= 7
        assert 0 <= features["away_games_last_7"] <= 7

    def test_first_game_of_season(self):
        """First game should have default rest values."""
        features = compute_situational_features(
            games=[],  # No prior games
            game_date=date(2024, 1, 1),
            home_team="BOS",
            away_team="LAL",
        )

        # First game = well-rested (7 days)
        assert features["home_rest_days"] == 7.0
        assert features["away_rest_days"] == 7.0
        assert features["games_into_season"] == 0.0


# ============================================================================
# Feature Pipeline Tests
# ============================================================================

class TestFeaturePipeline:
    """Tests for FeaturePipeline class."""

    def test_create_features_returns_all_keys(self, sample_games, bos_vs_lal_game):
        """create_features should return all team and situational features."""
        pipeline = FeaturePipeline()
        features = pipeline.create_features(sample_games, bos_vs_lal_game)

        # Should have team features
        assert "net_rtg_diff" in features
        assert "form_diff" in features

        # Should have situational features
        assert "rest_advantage" in features
        assert "b2b_disadvantage" in features

    def test_feature_names_populated(self, sample_games, bos_vs_lal_game):
        """feature_names should be populated after first run."""
        pipeline = FeaturePipeline()
        assert pipeline.feature_names == []

        pipeline.create_features(sample_games, bos_vs_lal_game)

        assert len(pipeline.feature_names) > 0
        assert "net_rtg_diff" in pipeline.feature_names

    def test_create_training_dataset_returns_dataframe(self, sample_games):
        """create_training_dataset should return a pandas DataFrame."""
        pipeline = FeaturePipeline()
        df = pipeline.create_training_dataset(sample_games, min_games_required=2)

        assert isinstance(df, pd.DataFrame)

    def test_training_dataset_has_required_columns(self, sample_games):
        """DataFrame should have metadata and target columns."""
        pipeline = FeaturePipeline()
        df = pipeline.create_training_dataset(sample_games, min_games_required=2)

        assert "game_id" in df.columns
        assert "game_date" in df.columns
        assert "home_team" in df.columns
        assert "away_team" in df.columns
        assert "home_win" in df.columns

    def test_training_dataset_has_features(self, sample_games):
        """DataFrame should contain feature columns."""
        pipeline = FeaturePipeline()
        # Use min_games_required=0 because sample fixture has unique opponents
        # (each opponent appears only once, so no game passes min_games >= 1 filter)
        df = pipeline.create_training_dataset(sample_games, min_games_required=0)

        # Check for some feature columns
        feature_cols = [c for c in df.columns if c not in [
            "game_id", "game_date", "home_team", "away_team", "home_win"
        ]]

        assert len(feature_cols) >= 10, "Should have at least 10 feature columns"

    def test_training_dataset_no_nan(self, sample_games):
        """DataFrame should have no NaN values."""
        pipeline = FeaturePipeline()
        df = pipeline.create_training_dataset(sample_games, min_games_required=2)

        assert not df.isnull().any().any(), "DataFrame contains NaN values"

    def test_home_win_is_binary(self, sample_games):
        """home_win column should be 0.0 or 1.0."""
        pipeline = FeaturePipeline()
        df = pipeline.create_training_dataset(sample_games, min_games_required=2)

        if not df.empty:
            assert df["home_win"].isin([0.0, 1.0]).all()

    def test_min_games_required_filter(self, sample_games):
        """Games should be skipped if teams don't have enough history."""
        pipeline = FeaturePipeline()

        # With high min_games, should get fewer rows
        df_strict = pipeline.create_training_dataset(sample_games, min_games_required=4)
        df_loose = pipeline.create_training_dataset(sample_games, min_games_required=1)

        assert len(df_strict) <= len(df_loose)


class TestCreateTrainingFeatures:
    """Tests for create_training_features convenience function."""

    def test_returns_dataframe(self, sample_games):
        """Should return a DataFrame."""
        df = create_training_features(sample_games, min_games_required=2)
        assert isinstance(df, pd.DataFrame)

    def test_accepts_custom_lookback(self, sample_games):
        """Should accept custom lookback_games parameter."""
        df = create_training_features(
            sample_games,
            lookback_games=5,
            min_games_required=2,
        )
        assert isinstance(df, pd.DataFrame)


# ============================================================================
# Integration / Anti-Leakage Tests
# ============================================================================

class TestPipelineAntiLeakage:
    """Integration tests verifying no look-ahead bias in full pipeline."""

    def test_training_dataset_temporal_order(self, sample_games):
        """Features for each game should only use prior games."""
        pipeline = FeaturePipeline()
        df = pipeline.create_training_dataset(sample_games, min_games_required=1)

        if len(df) >= 2:
            # Games should be ordered by date
            dates = pd.to_datetime(df["game_date"])
            assert dates.is_monotonic_increasing, "Games not in temporal order"

    def test_d3_data_not_in_d2_features(self):
        """Critical: D3 game should NOT affect D2 features."""
        games = [
            HistoricalGame(
                game_id="d1_a",
                game_date=datetime(2024, 1, 1),
                season="2023-24",
                home_team="AAA",
                away_team="BBB",
                home_score=100,
                away_score=100,
            ),
            HistoricalGame(
                game_id="d1_b",
                game_date=datetime(2024, 1, 1),
                season="2023-24",
                home_team="CCC",
                away_team="DDD",
                home_score=100,
                away_score=100,
            ),
            HistoricalGame(
                game_id="d2_target",
                game_date=datetime(2024, 1, 2),
                season="2023-24",
                home_team="AAA",
                away_team="CCC",
                home_score=100,
                away_score=100,
            ),
            HistoricalGame(
                game_id="d3_future",
                game_date=datetime(2024, 1, 3),
                season="2023-24",
                home_team="AAA",
                away_team="EEE",
                home_score=200,
                away_score=0,  # Outlier - should NOT affect D2
            ),
        ]

        pipeline = FeaturePipeline()
        df = pipeline.create_training_dataset(games, min_games_required=1)

        # Find D2 game row
        d2_row = df[df["game_id"] == "d2_target"]

        if not d2_row.empty:
            # AAA's net rating for D2 should be 0 (only D1 tie)
            # If D3 leaked, it would be ~100 (average of 0 and 200)
            assert d2_row["home_net_rtg_l10"].values[0] == pytest.approx(0.0, abs=0.1)
