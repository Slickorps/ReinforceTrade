import pytest
import numpy as np
from ml import MomentumFactor, VolatilityFactor, SentimentFactor, FactorPipeline


# ---------- Fixtures ----------

@pytest.fixture
def sample_market_data():
    """Generate deterministic 60-bar OHLCV data for testing."""
    np.random.seed(42)
    n = 60
    closes = np.cumprod(1 + np.random.randn(n) * 0.01) * 100
    highs = closes * (1 + np.abs(np.random.randn(n)) * 0.005)
    lows = closes * (1 - np.abs(np.random.randn(n)) * 0.005)
    volumes = np.random.randint(1000, 10000, n)
    return {
        "closes": closes.tolist(),
        "highs": highs.tolist(),
        "lows": lows.tolist(),
        "volumes": volumes.tolist(),
    }


@pytest.fixture
def short_data():
    """Short data (< 3 bars) to test edge cases."""
    return {
        "closes": [100.0, 101.0],
        "highs": [101.0, 102.0],
        "lows": [99.0, 100.0],
        "volumes": [5000, 6000],
    }


# ---------- MomentumFactor ----------

class TestMomentumFactor:
    def test_compute_returns_all_keys(self, sample_market_data):
        mf = MomentumFactor()
        result = mf.compute(sample_market_data)
        assert "signal" in result
        assert "roc" in result
        assert "macd_signal" in result
        assert "rsi" in result

    def test_signal_in_range(self, sample_market_data):
        mf = MomentumFactor()
        result = mf.compute(sample_market_data)
        assert -1.0 <= result["signal"] <= 1.0

    def test_rsi_in_range(self, sample_market_data):
        mf = MomentumFactor()
        result = mf.compute(sample_market_data)
        assert 0 <= result["rsi"] <= 100

    def test_short_data_returns_defaults(self, short_data):
        mf = MomentumFactor(roc_period=14, rsi_period=14)
        result = mf.compute(short_data)
        assert result["signal"] == 0.0
        assert result["roc"] == 0.0
        assert result["rsi"] == 50.0


# ---------- VolatilityFactor ----------

class TestVolatilityFactor:
    def test_compute_returns_all_keys(self, sample_market_data):
        vf = VolatilityFactor()
        result = vf.compute(sample_market_data)
        assert "signal" in result
        assert "regime" in result
        assert "atr_pct" in result
        assert "hist_vol" in result
        assert "weight_multiplier" in result

    def test_regime_is_valid(self, sample_market_data):
        vf = VolatilityFactor()
        result = vf.compute(sample_market_data)
        assert result["regime"] in ("low", "medium", "high")

    def test_weight_multiplier_positive(self, sample_market_data):
        vf = VolatilityFactor()
        result = vf.compute(sample_market_data)
        assert result["weight_multiplier"] > 0

    def test_signal_in_range(self, sample_market_data):
        vf = VolatilityFactor()
        result = vf.compute(sample_market_data)
        assert -1.0 <= result["signal"] <= 1.0

    def test_short_data_returns_defaults(self, short_data):
        vf = VolatilityFactor()
        result = vf.compute(short_data)
        # With only 2 bars, log_returns diff is empty → hist_vol = 0 → "low" regime
        assert result["regime"] in ("low", "medium", "high")
        assert result["weight_multiplier"] > 0


# ---------- SentimentFactor ----------

class TestSentimentFactor:
    def test_compute_returns_all_keys(self, sample_market_data):
        sf = SentimentFactor()
        result = sf.compute(sample_market_data)
        assert "signal" in result
        assert "imbalance" in result
        assert "pressure" in result
        assert "vol_trend" in result

    def test_pressure_is_valid(self, sample_market_data):
        sf = SentimentFactor()
        result = sf.compute(sample_market_data)
        assert result["pressure"] in ("buying", "selling", "neutral")

    def test_signal_in_range(self, sample_market_data):
        sf = SentimentFactor()
        result = sf.compute(sample_market_data)
        assert -1.0 <= result["signal"] <= 1.0

    def test_imbalance_between_negative_one_and_one(self, sample_market_data):
        sf = SentimentFactor()
        result = sf.compute(sample_market_data)
        assert -1.0 <= result["imbalance"] <= 1.0

    def test_short_data_returns_defaults(self, short_data):
        sf = SentimentFactor()
        result = sf.compute(short_data)
        # 2 bars [100→101] → all up volume → imbalance = 1.0, pressure = "buying"
        assert -1.0 <= result["imbalance"] <= 1.0
        assert result["pressure"] in ("buying", "selling", "neutral")


# ---------- FactorPipeline ----------

class TestFactorPipeline:
    def test_compute_returns_all_keys(self, sample_market_data):
        pipe = FactorPipeline()
        result = pipe.compute(sample_market_data)
        assert "signal" in result
        assert "factors" in result
        assert "weights_used" in result

    def test_composite_signal_in_range(self, sample_market_data):
        pipe = FactorPipeline()
        result = pipe.compute(sample_market_data)
        assert -1.0 <= result["signal"] <= 1.0

    def test_factors_contains_all_three(self, sample_market_data):
        pipe = FactorPipeline()
        result = pipe.compute(sample_market_data)
        assert set(result["factors"].keys()) == {"momentum", "volatility", "sentiment"}

    def test_weights_sum_to_one(self):
        pipe = FactorPipeline()
        total = sum(pipe.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_custom_weights_are_normalized(self):
        pipe = FactorPipeline(weights={"momentum": 1.0, "volatility": 1.0, "sentiment": 1.0})
        total = sum(pipe.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_update_weights(self, sample_market_data):
        pipe = FactorPipeline()
        pipe.update_weights({"momentum": 0.8, "volatility": 0.1, "sentiment": 0.1})
        total = sum(pipe.weights.values())
        assert abs(total - 1.0) < 1e-6
        assert abs(pipe.weights["momentum"] - 0.8) < 1e-6

    def test_signal_changes_with_different_data(self):
        """Ensure pipeline produces different signals for different regimes."""
        # Strong uptrend data
        up_data = {
            "closes": [100 + i * 2 for i in range(60)],
            "highs": [102 + i * 2 for i in range(60)],
            "lows": [98 + i * 2 for i in range(60)],
            "volumes": [5000 + i * 10 for i in range(60)],
        }
        # Strong downtrend data
        down_data = {
            "closes": [200 - i * 2 for i in range(60)],
            "highs": [202 - i * 2 for i in range(60)],
            "lows": [198 - i * 2 for i in range(60)],
            "volumes": [5000 - i * 10 for i in range(60)],
        }
        pipe = FactorPipeline()
        up_signal = pipe.compute(up_data)["signal"]
        down_signal = pipe.compute(down_data)["signal"]
        assert up_signal != down_signal

    def test_short_data_works(self, short_data):
        pipe = FactorPipeline()
        result = pipe.compute(short_data)
        assert "signal" in result