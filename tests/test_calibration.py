"""Comprehensive tests for probability calibration module."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from nba_betting_agent.agents.analysis_agent.calibration import (
    ProbabilityCalibrator,
    calibrate_probability,
)


class TestProbabilityCalibratorBasic:
    """Tests for basic calibrator functionality."""

    def test_calibrator_init_default(self):
        """Test calibrator initializes with default sigmoid method."""
        calibrator = ProbabilityCalibrator()
        assert calibrator.method == "sigmoid"
        assert not calibrator._is_fitted

    def test_calibrator_init_invalid_method(self):
        """Test calibrator rejects invalid calibration methods."""
        with pytest.raises(ValueError, match="Only 'sigmoid' method is supported"):
            ProbabilityCalibrator(method="isotonic")

    def test_calibrator_fit_basic(self):
        """Test calibrator can be fitted with simple data."""
        calibrator = ProbabilityCalibrator()
        raw_probs = np.array([0.5, 0.6, 0.7, 0.8])
        outcomes = np.array([0, 1, 1, 1])

        result = calibrator.fit(raw_probs, outcomes)

        assert result is calibrator  # Returns self for chaining
        assert calibrator._is_fitted
        assert calibrator._calibrator is not None


class TestProbabilityCalibratorValidation:
    """Tests for input validation."""

    def test_calibrator_invalid_probs_fit(self):
        """Test calibrator rejects probabilities outside [0, 1]."""
        calibrator = ProbabilityCalibrator()
        raw_probs = np.array([0.5, 1.5, 0.7])  # 1.5 is invalid
        outcomes = np.array([0, 1, 1])

        with pytest.raises(ValueError, match="raw_probs must be in"):
            calibrator.fit(raw_probs, outcomes)

    def test_calibrator_invalid_probs_negative(self):
        """Test calibrator rejects negative probabilities."""
        calibrator = ProbabilityCalibrator()
        raw_probs = np.array([0.5, -0.2, 0.7])  # -0.2 is invalid
        outcomes = np.array([0, 1, 1])

        with pytest.raises(ValueError, match="raw_probs must be in"):
            calibrator.fit(raw_probs, outcomes)

    def test_calibrator_invalid_outcomes_fit(self):
        """Test calibrator rejects non-binary outcomes."""
        calibrator = ProbabilityCalibrator()
        raw_probs = np.array([0.5, 0.6, 0.7])
        outcomes = np.array([0, 2, 1])  # 2 is invalid

        with pytest.raises(ValueError, match="outcomes must be binary"):
            calibrator.fit(raw_probs, outcomes)

    def test_calibrator_mismatched_lengths(self):
        """Test calibrator rejects mismatched array lengths."""
        calibrator = ProbabilityCalibrator()
        raw_probs = np.array([0.5, 0.6, 0.7])
        outcomes = np.array([0, 1])  # Different length

        with pytest.raises(ValueError, match="must have same length"):
            calibrator.fit(raw_probs, outcomes)


class TestProbabilityCalibratorCalibration:
    """Tests for calibration quality and behavior."""

    def test_calibrator_calibrate_outputs_valid_probs(self):
        """Test calibrated probabilities are in valid [0, 1] range."""
        calibrator = ProbabilityCalibrator()
        # Train on diverse data
        np.random.seed(42)
        raw_probs = np.random.uniform(0.2, 0.9, 100)
        outcomes = (np.random.random(100) < raw_probs).astype(int)

        calibrator.fit(raw_probs, outcomes)

        test_probs = np.array([0.3, 0.5, 0.7, 0.9])
        calibrated = calibrator.calibrate(test_probs)

        assert np.all(calibrated >= 0.0)
        assert np.all(calibrated <= 1.0)

    def test_calibrator_improves_overconfident(self):
        """Test calibrator reduces overconfident probability estimates."""
        calibrator = ProbabilityCalibrator()

        # Overconfident model: predicts 0.8 but only wins 55% of the time
        raw_probs = np.array([0.8] * 100)
        outcomes = np.array([1] * 55 + [0] * 45)

        calibrator.fit(raw_probs, outcomes)
        calibrated = calibrator.calibrate_single(0.8)

        # Calibrated should be closer to 0.55 than 0.8
        assert calibrated < 0.8
        assert abs(calibrated - 0.55) < abs(0.8 - 0.55)

    def test_calibrator_improves_underconfident(self):
        """Test calibrator increases underconfident probability estimates."""
        calibrator = ProbabilityCalibrator()

        # Underconfident model: predicts 0.4 but wins 70% of the time
        raw_probs = np.array([0.4] * 100)
        outcomes = np.array([1] * 70 + [0] * 30)

        calibrator.fit(raw_probs, outcomes)
        calibrated = calibrator.calibrate_single(0.4)

        # Calibrated should be closer to 0.70 than 0.4
        assert calibrated > 0.4
        assert abs(calibrated - 0.70) < abs(0.4 - 0.70)

    def test_calibrator_preserves_well_calibrated(self):
        """Test calibrator minimally adjusts already well-calibrated probabilities."""
        calibrator = ProbabilityCalibrator()

        # Well-calibrated model
        np.random.seed(42)
        raw_probs = np.random.uniform(0.3, 0.7, 200)
        # Outcomes match probabilities (well-calibrated)
        outcomes = (np.random.random(200) < raw_probs).astype(int)

        calibrator.fit(raw_probs, outcomes)

        test_prob = 0.5
        calibrated = calibrator.calibrate_single(test_prob)

        # Should stay close to original (within 10%)
        assert abs(calibrated - test_prob) < 0.1

    def test_calibrator_extreme_probs(self):
        """Test calibrator handles extreme probabilities (0.0 and 1.0)."""
        calibrator = ProbabilityCalibrator()

        # Train with diverse data
        np.random.seed(42)
        raw_probs = np.random.uniform(0.1, 0.9, 100)
        outcomes = (np.random.random(100) < raw_probs).astype(int)

        calibrator.fit(raw_probs, outcomes)

        # Test edge cases
        extreme_probs = np.array([0.0, 1.0])
        calibrated = calibrator.calibrate(extreme_probs)

        # Should produce valid probabilities (not NaN or inf)
        assert not np.any(np.isnan(calibrated))
        assert not np.any(np.isinf(calibrated))
        assert np.all(calibrated >= 0.0)
        assert np.all(calibrated <= 1.0)


class TestProbabilityCalibratorPersistence:
    """Tests for save/load functionality."""

    def test_calibrator_save_load(self):
        """Test calibrator can be saved and loaded while preserving calibration."""
        # Fit original calibrator
        calibrator = ProbabilityCalibrator()
        raw_probs = np.array([0.8] * 100)
        outcomes = np.array([1] * 55 + [0] * 45)
        calibrator.fit(raw_probs, outcomes)

        original_prediction = calibrator.calibrate_single(0.8)

        # Save and load
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "calibrator.pkl"
            calibrator.save(save_path)

            loaded_calibrator = ProbabilityCalibrator.load(save_path)

        # Verify loaded calibrator produces same results
        loaded_prediction = loaded_calibrator.calibrate_single(0.8)

        assert loaded_calibrator._is_fitted
        assert loaded_calibrator.method == calibrator.method
        assert np.isclose(loaded_prediction, original_prediction)

    def test_calibrator_save_unfitted_raises(self):
        """Test saving unfitted calibrator raises error."""
        calibrator = ProbabilityCalibrator()

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "calibrator.pkl"

            with pytest.raises(RuntimeError, match="Cannot save unfitted calibrator"):
                calibrator.save(save_path)

    def test_calibrator_load_nonexistent_raises(self):
        """Test loading from nonexistent path raises error."""
        with pytest.raises(FileNotFoundError):
            ProbabilityCalibrator.load(Path("/nonexistent/path.pkl"))


class TestProbabilityCalibratorMethods:
    """Tests for calibrator methods."""

    def test_calibrator_single_value(self):
        """Test calibrate_single() works for individual values."""
        calibrator = ProbabilityCalibrator()
        raw_probs = np.array([0.6, 0.7, 0.8])
        outcomes = np.array([1, 0, 1])

        calibrator.fit(raw_probs, outcomes)

        single_result = calibrator.calibrate_single(0.7)
        array_result = calibrator.calibrate(np.array([0.7]))[0]

        # Should produce same result as array calibration
        assert np.isclose(single_result, array_result)
        assert isinstance(single_result, float)

    def test_calibrator_not_fitted_raises(self):
        """Test calibrate() before fit() raises RuntimeError."""
        calibrator = ProbabilityCalibrator()

        with pytest.raises(RuntimeError, match="Calibrator not fitted"):
            calibrator.calibrate(np.array([0.5]))

    def test_calibrator_not_fitted_single_raises(self):
        """Test calibrate_single() before fit() raises RuntimeError."""
        calibrator = ProbabilityCalibrator()

        with pytest.raises(RuntimeError, match="Calibrator not fitted"):
            calibrator.calibrate_single(0.5)


class TestProbabilityCalibratorSmallDataset:
    """Tests for calibrator with small datasets."""

    def test_calibrator_small_dataset(self):
        """Test calibrator works with small calibration set (50 samples)."""
        calibrator = ProbabilityCalibrator()

        # Small dataset - still should work with sigmoid method
        np.random.seed(42)
        raw_probs = np.random.uniform(0.4, 0.8, 50)
        outcomes = (np.random.random(50) < raw_probs).astype(int)

        calibrator.fit(raw_probs, outcomes)
        calibrated = calibrator.calibrate(np.array([0.6]))

        # Should produce valid probability
        assert 0.0 <= calibrated[0] <= 1.0

    def test_calibrator_minimum_dataset(self):
        """Test calibrator with minimal dataset (10 samples)."""
        calibrator = ProbabilityCalibrator()

        # Very small dataset
        raw_probs = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 0.4, 0.3, 0.55, 0.65, 0.75])
        outcomes = np.array([0, 1, 1, 1, 1, 0, 0, 1, 0, 1])

        calibrator.fit(raw_probs, outcomes)
        calibrated = calibrator.calibrate_single(0.6)

        # Should work without errors
        assert 0.0 <= calibrated <= 1.0


class TestStandaloneFunctions:
    """Tests for standalone helper functions."""

    def test_calibrate_probability_with_calibrator(self):
        """Test standalone calibrate_probability() with fitted calibrator."""
        calibrator = ProbabilityCalibrator()
        raw_probs = np.array([0.8] * 100)
        outcomes = np.array([1] * 55 + [0] * 45)
        calibrator.fit(raw_probs, outcomes)

        result = calibrate_probability(0.8, calibrator)
        expected = calibrator.calibrate_single(0.8)

        assert np.isclose(result, expected)

    def test_calibrate_probability_without_calibrator(self):
        """Test standalone calibrate_probability() without calibrator (passthrough)."""
        raw_prob = 0.75

        result = calibrate_probability(raw_prob)

        # Should return unchanged when no calibrator
        assert result == raw_prob

    def test_calibrate_probability_none_calibrator(self):
        """Test standalone calibrate_probability() with explicit None calibrator."""
        raw_prob = 0.6

        result = calibrate_probability(raw_prob, calibrator=None)

        # Should passthrough
        assert result == raw_prob
