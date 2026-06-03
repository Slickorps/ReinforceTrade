import pytest
import numpy as np
import pandas as pd
from ml import (
    MomentumFactor,
    VolatilityFactor,
    SentimentFactor,
    FactorPipeline,
    FeatureBuilder,
    WalkForwardCV,
    MLFactor,
    MLFactorRouter,
)


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


# ---------- MLFactor (sklearn engine) ----------

class TestFeatureBuilder:
    def test_add_and_build(self):
        fb = FeatureBuilder()
        fb.add("momentum", lambda df: df["close"].pct_change(5))
        fb.add("volatility", lambda df: df["close"].pct_change().rolling(5).std())
        data = pd.DataFrame({"close": [100, 102, 101, 105, 107, 110, 108]})
        X = fb.build(data)
        assert list(X.columns) == ["momentum", "volatility"]
        assert len(X) == len(data)

    def test_remove_feature(self):
        fb = FeatureBuilder()
        fb.add("a", lambda df: df["close"])
        assert fb.remove("a") is True
        assert fb.remove("nonexistent") is False

    def test_feature_names(self):
        fb = FeatureBuilder()
        fb.add("a", lambda df: df["close"])
        fb.add("b", lambda df: df["close"] * 2)
        assert fb.feature_names == ["a", "b"]
        assert len(fb) == 2

    def test_build_subset(self):
        fb = FeatureBuilder()
        fb.add("a", lambda df: df["close"])
        fb.add("b", lambda df: df["close"] * 2)
        data = pd.DataFrame({"close": [100, 200]})
        X = fb.build(data, feature_names=["a"])
        assert list(X.columns) == ["a"]

    def test_unknown_feature_raises(self):
        fb = FeatureBuilder()
        data = pd.DataFrame({"close": [100]})
        with pytest.raises(ValueError, match="Unknown feature 'xyz'"):
            fb.build(data, feature_names=["xyz"])

    def test_repr(self):
        fb = FeatureBuilder()
        fb.add("a", lambda df: df["close"])
        assert "FeatureBuilder" in repr(fb)


class TestWalkForwardCV:
    def test_basic_split(self):
        X = np.arange(500).reshape(-1, 1)
        cv = WalkForwardCV(n_splits=3, train_size=100, test_size=30, gap=0)
        splits = cv.split(X)
        assert len(splits) >= 1
        for train_idx, test_idx in splits:
            # Temporal ordering preserved
            assert max(train_idx) < min(test_idx)
            assert len(train_idx) >= 100
            assert len(test_idx) >= 30

    def test_gap_respected(self):
        X = np.arange(500).reshape(-1, 1)
        cv = WalkForwardCV(n_splits=2, train_size=100, test_size=30, gap=5)
        splits = cv.split(X)
        for train_idx, test_idx in splits:
            assert min(test_idx) - max(train_idx) == 6  # gap=5 → index diff = 6

    def test_expanding_window(self):
        X = np.arange(500).reshape(-1, 1)
        cv = WalkForwardCV(n_splits=3, train_size=50, test_size=20, expanding=True)
        splits = cv.split(X)
        sizes = [len(t) for t, _ in splits]
        # Expanding windows get larger each split
        assert sizes == sorted(sizes)

    def test_sliding_window(self):
        X = np.arange(500).reshape(-1, 1)
        cv = WalkForwardCV(n_splits=2, train_size=50, test_size=20, expanding=False)
        splits_0 = cv.split(X)
        # With sliding + expanding=False, the second window shifts forward
        sizes = [len(t) for t, _ in splits_0]
        assert len(splits_0) >= 2  # at least 2 splits expected

    def test_insufficient_data(self):
        X = np.arange(20).reshape(-1, 1)  # too small
        cv = WalkForwardCV(n_splits=5, train_size=100, test_size=30)
        splits = cv.split(X)
        assert len(splits) == 0  # no valid splits

    def test_get_n_splits(self):
        cv = WalkForwardCV(n_splits=5)
        assert cv.get_n_splits() == 5


class TestMLFactor:
    @pytest.fixture
    def classification_data(self):
        np.random.seed(42)
        X = pd.DataFrame({
            "f1": np.random.randn(200),
            "f2": np.random.randn(200),
            "f3": np.random.randn(200),
        })
        y = pd.Series((X["f1"] + X["f2"] > 0).astype(int))
        return X, y

    @pytest.fixture
    def regression_data(self):
        np.random.seed(42)
        X = pd.DataFrame({
            "f1": np.random.randn(200),
            "f2": np.random.randn(200),
        })
        y = pd.Series(X["f1"] * 2 + X["f2"] * 0.5 + np.random.randn(200) * 0.1)
        return X, y

    def test_init_with_preset(self):
        mf = MLFactor(preset="rf_classifier")
        assert mf._pipeline is not None
        assert mf._is_classifier is True

    def test_init_with_custom_model(self):
        from sklearn.linear_model import LogisticRegression
        mf = MLFactor(model=LogisticRegression())
        assert mf._pipeline is not None

    def test_init_default(self):
        mf = MLFactor()
        assert mf._pipeline is not None

    def test_fit_and_predict_classifier(self, classification_data):
        X, y = classification_data
        mf = MLFactor(preset="rf_classifier")
        mf.fit(X, y)
        preds = mf.predict(X)
        assert len(preds) == len(y)
        assert set(preds).issubset({0, 1})

    def test_fit_and_predict_regression(self, regression_data):
        X, y = regression_data
        mf = MLFactor(preset="ridge_regressor")
        mf.fit(X, y)
        preds = mf.predict(X)
        assert len(preds) == len(y)
        assert np.issubdtype(preds.dtype, np.floating)

    def test_predict_proba(self, classification_data):
        X, y = classification_data
        mf = MLFactor(preset="gb_classifier")
        mf.fit(X, y)
        probs = mf.predict_proba(X)
        assert probs.shape == (len(X), 2)
        assert np.allclose(probs.sum(axis=1), 1.0)

    def test_predict_proba_regression_raises(self, regression_data):
        X, y = regression_data
        mf = MLFactor(preset="ridge_regressor")
        mf.fit(X, y)
        with pytest.raises(TypeError, match="predict_proba is only available for classification"):
            mf.predict_proba(X)

    def test_score_classifier(self, classification_data):
        X, y = classification_data
        mf = MLFactor(preset="lr_classifier")
        mf.fit(X, y)
        score = mf.score(X, y)
        assert 0.0 <= score <= 1.0

    def test_evaluate_classifier(self, classification_data):
        X, y = classification_data
        mf = MLFactor(preset="rf_classifier")
        mf.fit(X, y)
        metrics = mf.evaluate(X, y)
        for key in ("accuracy", "precision", "recall", "f1"):
            assert key in metrics
            assert 0.0 <= metrics[key] <= 1.0

    def test_evaluate_regressor(self, regression_data):
        X, y = regression_data
        mf = MLFactor(preset="ridge_regressor")
        mf.fit(X, y)
        metrics = mf.evaluate(X, y)
        for key in ("r2", "mse", "rmse"):
            assert key in metrics

    def test_save_and_load(self, classification_data, tmp_path):
        X, y = classification_data
        mf = MLFactor(preset="rf_classifier", name="test_model", model_dir=str(tmp_path))
        mf.fit(X, y)
        path = mf.save()
        # Load into a fresh instance
        mf2 = MLFactor(name="test_model", model_dir=str(tmp_path))
        mf2.load(path)
        preds_orig = mf.predict(X)
        preds_load = mf2.predict(X)
        np.testing.assert_array_equal(preds_orig, preds_load)

    def test_get_feature_importance(self, classification_data):
        X, y = classification_data
        mf = MLFactor(preset="rf_classifier")
        mf.fit(X, y)
        # Override feature names
        mf.feature_builder = FeatureBuilder()
        mf.feature_builder.add("f1", lambda df: df["f1"])
        mf.feature_builder.add("f2", lambda df: df["f2"])
        mf.feature_builder.add("f3", lambda df: df["f3"])
        importance = mf.get_feature_importance()
        assert importance is not None
        assert len(importance) == 3

    def test_walk_forward_fit(self):
        np.random.seed(42)
        n = 600
        data = pd.DataFrame({
            "f1": np.random.randn(n),
            "f2": np.random.randn(n),
            "target": ((np.random.randn(n) + 0.5) > 0).astype(int),
        })
        mf = MLFactor(preset="rf_classifier")
        cv = WalkForwardCV(n_splits=3, train_size=150, test_size=50)
        results = mf.walk_forward_fit(data, target_col="target", feature_cols=["f1", "f2"], cv=cv)
        assert "splits" in results
        assert len(results["splits"]) >= 1
        assert "mean_score" in results
        assert 0.0 <= results["mean_score"] <= 1.0

    def test_summary(self):
        mf = MLFactor(preset="rf_classifier", name="test_summary")
        summary = mf.summary()
        assert summary["name"] == "test_summary"
        assert summary["type"] == "classifier"
        assert summary["fitted"] is False

    def test_unfitted_raises(self):
        mf = MLFactor()
        with pytest.raises(RuntimeError, match="not fitted"):
            mf.predict(np.array([[1, 2]]))

    def test_invalid_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown preset 'invalid'"):
            MLFactor(preset="invalid")

    def test_init_with_feature_builder(self):
        fb = FeatureBuilder()
        fb.add("f1", lambda df: df["close"])
        mf = MLFactor(feature_builder=fb)
        assert mf.feature_builder is fb
        assert "f1" in mf.feature_names


class TestMLFactorRouter:
    @pytest.fixture
    def router(self, tmp_path):
        return MLFactorRouter(model_dir=str(tmp_path))

    @pytest.fixture
    def training_data(self):
        np.random.seed(42)
        X = pd.DataFrame({
            "f1": np.random.randn(200),
            "f2": np.random.randn(200),
            "f3": np.random.randn(200),
        })
        y = pd.Series((X["f1"] + X["f2"] > 0).astype(int))
        return X, y

    def test_train_and_list(self, router, training_data):
        X, y = training_data
        record = router.train(X, y, preset="rf_classifier", name="my_model")
        assert record.name == "my_model"
        assert record.model_type == "rf_classifier"
        assert record.metrics["accuracy"] > 0
        models = router.list_models()
        assert any(m.name == "my_model" for m in models)

    def test_predict(self, router, training_data):
        X, y = training_data
        router.train(X, y, preset="rf_classifier", name="pred_model")
        preds = router.predict("pred_model", X)
        assert len(preds) == len(y)

    def test_predict_with_proba(self, router, training_data):
        X, y = training_data
        router.train(X, y, preset="rf_classifier", name="proba_model")
        probs = router.predict("proba_model", X, return_proba=True)
        assert probs.shape == (len(X), 2)

    def test_unknown_model_raises(self, router):
        with pytest.raises(ValueError, match="not found"):
            router.predict("nonexistent", pd.DataFrame({"a": [1, 2]}))

    def test_get_model(self, router, training_data):
        X, y = training_data
        router.train(X, y, preset="rf_classifier", name="get_model_test")
        mf = router.get_model("get_model_test")
        assert mf is not None
        assert mf.name == "get_model_test"

    def test_get_nonexistent_model(self, router):
        assert router.get_model("missing") is None

    def test_delete_model(self, router, training_data, tmp_path):
        X, y = training_data
        router.train(X, y, preset="rf_classifier", name="del_model")
        assert router.delete_model("del_model") is True
        assert router.delete_model("del_model") is False  # already gone

    def test_get_metrics(self, router, training_data):
        X, y = training_data
        router.train(X, y, preset="rf_classifier", name="metrics_model")
        metrics = router.get_metrics("metrics_model")
        assert metrics is not None
        assert "accuracy" in metrics

    def test_get_metrics_nonexistent(self, router):
        assert router.get_metrics("ghost") is None

    def test_auto_name(self, router, training_data):
        X, y = training_data
        record = router.train(X, y, preset="gb_classifier")
        assert record.name.startswith("model_")

    def test_persistence_across_sessions(self, training_data, tmp_path):
        X, y = training_data
        # Train and save
        router1 = MLFactorRouter(model_dir=str(tmp_path))
        router1.train(X, y, preset="rf_classifier", name="persist_model")
        # Create new router from same dir
        router2 = MLFactorRouter(model_dir=str(tmp_path))
        models = router2.list_models()
        assert any(m.name == "persist_model" for m in models)
        # Predict with loaded model
        preds = router2.predict("persist_model", X)
        assert len(preds) == len(y)
