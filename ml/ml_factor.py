"""
ML Factor Engine — sklearn-powered factor generation and walk-forward optimisation.

Provides:
  - MLFactor       : Scikit-learn pipeline wrapper with fit / predict / predict_proba
  - WalkForwardCV  : Time-series-aware train/test splitter
  - MLFactorRouter : High-level API for training, prediction, and model management

Usage:
    from ml import MLFactor, WalkForwardCV, MLFactorRouter

    engine = MLFactor()
    engine.add_feature("momentum", lambda df: df["close"].pct_change(20))
    engine.add_feature("volatility", lambda df: df["close"].pct_change().rolling(20).std())
    engine.fit(X_train, y_train)

    probs = engine.predict_proba(X_test)
"""

from __future__ import annotations

import io
import json
import joblib
import numpy as np
import pandas as pd
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.ensemble import (
    RandomForestClassifier,
    RandomForestRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge, Lasso
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    mean_squared_error,
    r2_score,
)

from utils.logger import logger

# ──────────────────────────────────────────────────────────────────────
# Feature engineering
# ──────────────────────────────────────────────────────────────────────


class FeatureBuilder:
    """
    Composable feature engineering interface.
    Stores named callables that accept a DataFrame and return a Series.
    """

    def __init__(self, features: Optional[Dict[str, Callable]] = None):
        self._features: Dict[str, Callable] = dict(features or {})

    def add(self, name: str, fn: Callable[[pd.DataFrame], pd.Series]) -> None:
        """Register a new feature by name."""
        if name in self._features:
            logger.warning(f"Overwriting existing feature '{name}'")
        self._features[name] = fn
        logger.debug(f"Feature '{name}' registered")

    def remove(self, name: str) -> bool:
        """Remove a registered feature. Returns True if removed."""
        return self._features.pop(name, None) is not None

    def build(
        self, data: pd.DataFrame, feature_names: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Build feature matrix from raw data."""
        names = feature_names or list(self._features.keys())
        rows = {}
        for name in names:
            fn = self._features.get(name)
            if fn is None:
                raise ValueError(f"Unknown feature '{name}'")
            series = fn(data)
            rows[name] = series.values if isinstance(series, pd.Series) else series
        return pd.DataFrame(rows, index=data.index)

    @property
    def feature_names(self) -> List[str]:
        return list(self._features.keys())

    def __len__(self) -> int:
        return len(self._features)

    def __repr__(self) -> str:
        return f"FeatureBuilder({len(self)} features: {', '.join(self.feature_names)})"


# ──────────────────────────────────────────────────────────────────────
# Walk-forward cross-validation
# ──────────────────────────────────────────────────────────────────────


class WalkForwardCV:
    """
    Time-series-aware walk-forward splitter.

    Produces expanding (or sliding) train/test windows that respect
    temporal order to avoid look-ahead bias.
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_size: int = 252,  # ~1 year of daily bars
        test_size: int = 63,    # ~1 quarter
        gap: int = 0,
        expanding: bool = True,
    ):
        self.n_splits = n_splits
        self.train_size = train_size
        self.test_size = test_size
        self.gap = gap
        self.expanding = expanding

    def split(
        self, X: Union[pd.DataFrame, np.ndarray], y: Optional[np.ndarray] = None
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Generate train/test index pairs."""
        n = len(X)
        splits: List[Tuple[np.ndarray, np.ndarray]] = []
        start = 0

        for i in range(self.n_splits):
            if self.expanding:
                train_end = start + self.train_size
            else:
                # sliding window
                train_end = start + self.train_size
                start += self.test_size + self.gap

            test_start = train_end + self.gap
            test_end = test_start + self.test_size

            if test_end > n:
                break

            train_idx = np.arange(start, train_end)
            test_idx = np.arange(test_start, test_end)
            splits.append((train_idx, test_idx))

            if not self.expanding:
                # for expanding, we just grow the end boundary
                pass

            # For expanding window, extend train_end for next iteration
            if self.expanding:
                start = 0
                self.train_size += self.test_size + self.gap

        return splits

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits


# ──────────────────────────────────────────────────────────────────────
# MLFactor — sklearn pipeline wrapper
# ──────────────────────────────────────────────────────────────────────


class MLFactor:
    """
    Scikit-learn-powered factor generation engine.

    Supports:
      - Classification (RandomForest, GradientBoost, LogisticRegression)
      - Regression (RandomForestRegressor, GradientBoostingRegressor, Ridge)
      - Custom sklearn pipelines
      - Walk-forward training & evaluation
      - Model persistence via joblib
    """

    # Pre-built model presets
    PRESETS: Dict[str, Dict[str, Any]] = {
        "rf_classifier": {
            "pipeline": [
                ("scaler", StandardScaler()),
                ("classifier", RandomForestClassifier(
                    n_estimators=100, max_depth=6, random_state=42, n_jobs=-1
                )),
            ]
        },
        "gb_classifier": {
            "pipeline": [
                ("scaler", RobustScaler()),
                ("classifier", GradientBoostingClassifier(
                    n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
                )),
            ]
        },
        "lr_classifier": {
            "pipeline": [
                ("scaler", StandardScaler()),
                ("classifier", LogisticRegression(C=1.0, max_iter=1000, random_state=42)),
            ]
        },
        "rf_regressor": {
            "pipeline": [
                ("scaler", StandardScaler()),
                ("regressor", RandomForestRegressor(
                    n_estimators=100, max_depth=6, random_state=42, n_jobs=-1
                )),
            ]
        },
        "gb_regressor": {
            "pipeline": [
                ("scaler", RobustScaler()),
                ("regressor", GradientBoostingRegressor(
                    n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
                )),
            ]
        },
        "ridge_regressor": {
            "pipeline": [
                ("scaler", StandardScaler()),
                ("regressor", Ridge(alpha=1.0, random_state=42)),
            ]
        },
    }

    def __init__(
        self,
        model: Optional[object] = None,
        preset: Optional[str] = None,
        feature_builder: Optional[FeatureBuilder] = None,
        name: Optional[str] = None,
        model_dir: Optional[str] = None,
    ):
        """
        Args:
            model: Pre-configured sklearn estimator or Pipeline.
            preset: Named preset configuration (overrides `model`).
            feature_builder: Shared FeatureBuilder instance.
            name: Human-readable name for this model.
            model_dir: Directory for model persistence.
        """
        self.name = name or f"ml_factor_{id(self):x}"
        self.model_dir = Path(model_dir) if model_dir else Path("models")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.feature_builder = feature_builder or FeatureBuilder()
        self._pipeline: Optional[Pipeline] = None
        self._is_classifier: bool = True
        self._fitted: bool = False

        # Initialize model
        if preset:
            self._init_from_preset(preset)
        elif model is not None:
            self._init_from_model(model)
        else:
            # Default: RandomForest classifier
            self._init_from_preset("rf_classifier")

        logger.info(
            f"MLFactor '{self.name}' initialized "
            f"(type={'classifier' if self._is_classifier else 'regressor'})"
        )

    def _init_from_preset(self, preset: str) -> None:
        """Initialise from a named preset."""
        if preset not in self.PRESETS:
            valid = list(self.PRESETS.keys())
            raise ValueError(f"Unknown preset '{preset}'. Valid: {valid}")

        config = self.PRESETS[preset]
        self._pipeline = Pipeline(config["pipeline"])
        self._is_classifier = "classifier" in dict(config["pipeline"])

    def _init_from_model(self, model: object) -> None:
        """Initialise from a user-supplied model."""
        if isinstance(model, Pipeline):
            self._pipeline = model
        elif isinstance(model, (ClassifierMixin, RegressorMixin)):
            self._pipeline = Pipeline([("model", model)])
        else:
            raise TypeError(
                f"Expected sklearn Pipeline, ClassifierMixin, or RegressorMixin, "
                f"got {type(model).__name__}"
            )
        self._is_classifier = isinstance(model, ClassifierMixin) or (
            isinstance(self._pipeline.steps[-1][1], ClassifierMixin)
        )

    # ── Feature management ──────────────────────────────────────────

    def add_feature(
        self, name: str, fn: Callable[[pd.DataFrame], pd.Series]
    ) -> None:
        """Register a feature engineering function."""
        self.feature_builder.add(name, fn)

    def remove_feature(self, name: str) -> bool:
        """Remove a registered feature."""
        return self.feature_builder.remove(name)

    def build_features(
        self, data: pd.DataFrame, feature_names: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Transform raw data into feature matrix."""
        return self.feature_builder.build(data, feature_names)

    @property
    def feature_names(self) -> List[str]:
        return self.feature_builder.feature_names

    # ── Training ────────────────────────────────────────────────────

    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        sample_weight: Optional[np.ndarray] = None,
    ) -> "MLFactor":
        """Train the underlying sklearn pipeline."""
        if self._pipeline is None:
            raise RuntimeError("No model pipeline configured")

        self._pipeline.fit(X, y)
        self._fitted = True
        logger.info(
            f"Model '{self.name}' fitted on {len(X)} samples "
            f"with {X.shape[1] if hasattr(X, 'shape') else '?'} features"
        )
        return self

    def walk_forward_fit(
        self,
        data: pd.DataFrame,
        target_col: str = "target",
        feature_cols: Optional[List[str]] = None,
        cv: Optional[WalkForwardCV] = None,
    ) -> Dict[str, Any]:
        """
        Run walk-forward training and evaluation.

        Returns dict with per-split metrics.
        """
        cv = cv or WalkForwardCV(n_splits=5, train_size=252, test_size=63)

        # Build feature matrix
        if feature_cols:
            X = data[feature_cols]
        else:
            X = self.build_features(data)

        y = data[target_col].values

        results: Dict[str, Any] = {
            "splits": [],
            "mean_score": 0.0,
            "std_score": 0.0,
        }

        for i, (train_idx, test_idx) in enumerate(cv.split(X, y)):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            self.fit(X_train, y_train)

            # Score
            if self._is_classifier:
                y_pred = self.predict(X_test)
                score = accuracy_score(y_test, y_pred)
                metrics = {
                    "accuracy": score,
                    "precision": precision_score(y_test, y_pred, average="weighted", zero_division=0),
                    "recall": recall_score(y_test, y_pred, average="weighted", zero_division=0),
                    "f1": f1_score(y_test, y_pred, average="weighted", zero_division=0),
                }
            else:
                y_pred = self.predict(X_test)
                score = r2_score(y_test, y_pred)
                metrics = {
                    "r2": score,
                    "mse": mean_squared_error(y_test, y_pred),
                    "rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
                }

            results["splits"].append({
                "split": i,
                "train_start": str(data.index[train_idx[0]]),
                "train_end": str(data.index[train_idx[-1]]),
                "test_start": str(data.index[test_idx[0]]),
                "test_end": str(data.index[test_idx[-1]]),
                "train_size": len(train_idx),
                "test_size": len(test_idx),
                "metrics": metrics,
            })

            logger.info(
                f"Walk-forward split {i + 1}: "
                f"train={len(train_idx)} test={len(test_idx)} "
                f"score={score:.4f}"
            )

        scores = [s["metrics"]["accuracy" if self._is_classifier else "r2"] for s in results["splits"]]
        results["mean_score"] = float(np.mean(scores))
        results["std_score"] = float(np.std(scores))
        results["n_splits"] = len(results["splits"])

        return results

    # ── Prediction ──────────────────────────────────────────────────

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict labels (classification) or values (regression)."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        return self._pipeline.predict(X)

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict class probabilities (classification only)."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        if not self._is_classifier:
            raise TypeError("predict_proba is only available for classification models")
        return self._pipeline.predict_proba(X)

    def score(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
    ) -> float:
        """Return accuracy (classifier) or R² (regressor)."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        return self._pipeline.score(X, y)

    def evaluate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
    ) -> Dict[str, float]:
        """
        Comprehensive evaluation metrics.

        Returns a dict of metric names to values.
        """
        y_pred = self.predict(X)
        if self._is_classifier:
            return {
                "accuracy": accuracy_score(y, y_pred),
                "precision": precision_score(y, y_pred, average="weighted", zero_division=0),
                "recall": recall_score(y, y_pred, average="weighted", zero_division=0),
                "f1": f1_score(y, y_pred, average="weighted", zero_division=0),
            }
        else:
            return {
                "r2": r2_score(y, y_pred),
                "mse": mean_squared_error(y, y_pred),
                "rmse": np.sqrt(mean_squared_error(y, y_pred)),
            }

    # ── Persistence ─────────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> str:
        """Save the fitted pipeline to disk with joblib."""
        if self._pipeline is None:
            raise RuntimeError("Nothing to save — model has not been fitted")

        path = path or str(self.model_dir / f"{self.name}.joblib")
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # Save metadata alongside
        metadata = {
            "name": self.name,
            "is_classifier": self._is_classifier,
            "features": self.feature_names,
            "saved_at": datetime.utcnow().isoformat(),
        }
        meta_path = Path(path).with_suffix(".json")
        meta_path.write_text(json.dumps(metadata, indent=2))

        joblib.dump(self._pipeline, path)
        logger.info(f"Model '{self.name}' saved to {path}")
        return path

    def load(self, path: str) -> "MLFactor":
        """Load a fitted pipeline from disk."""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        self._pipeline = joblib.load(path)
        self._fitted = True

        # Try to load metadata
        meta_path = path_obj.with_suffix(".json")
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
            self.name = metadata.get("name", self.name)
            self._is_classifier = metadata.get("is_classifier", True)
            logger.info(f"Model '{self.name}' loaded from {path}")
        else:
            logger.warning(f"No metadata found for {path}")

        return self

    def get_pipeline(self) -> Optional[Pipeline]:
        """Return the underlying sklearn Pipeline."""
        return self._pipeline

    def get_feature_importance(self) -> Optional[pd.Series]:
        """
        Return feature importance if the model supports it.

        Returns a Series indexed by feature name, sorted descending.
        """
        if self._pipeline is None:
            return None

        # Walk pipeline steps to find the estimator
        estimator = self._pipeline.steps[-1][1]
        if hasattr(estimator, "feature_importances_"):
            names = self.feature_names or [f"f{i}" for i in range(len(estimator.feature_importances_))]
            return pd.Series(estimator.feature_importances_, index=names).sort_values(ascending=False)
        elif hasattr(estimator, "coef_"):
            coef = estimator.coef_.flatten() if estimator.coef_.ndim > 1 else estimator.coef_
            names = self.feature_names or [f"f{i}" for i in range(len(coef))]
            return pd.Series(np.abs(coef), index=names).sort_values(ascending=False)
        return None

    def summary(self) -> Dict[str, Any]:
        """Return a human-readable summary of the model state."""
        return {
            "name": self.name,
            "type": "classifier" if self._is_classifier else "regressor",
            "fitted": self._fitted,
            "n_features": len(self.feature_names),
            "features": self.feature_names,
            "pipeline_steps": (
                [str(s) for s in self._pipeline.steps] if self._pipeline else []
            ),
            "model_dir": str(self.model_dir),
        }


# ──────────────────────────────────────────────────────────────────────
# MLFactorRouter — high-level API for training & prediction orchestration
# ──────────────────────────────────────────────────────────────────────


@dataclass
class TrainedModelRecord:
    """Record of a trained model."""
    name: str
    model_type: str  # e.g. "rf_classifier"
    created_at: str
    metrics: Dict[str, float]
    path: str
    n_features: int
    feature_names: List[str]


class MLFactorRouter:
    """
    High-level API for managing multiple ML models.

    Provides training, prediction, listing, and loading capabilities
    suitable for use from a REST API or automated pipeline.
    """

    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._models: Dict[str, MLFactor] = {}
        self._records: List[TrainedModelRecord] = []
        self._load_existing_records()

    def _load_existing_records(self) -> None:
        """Scan model_dir for existing model metadata."""
        for meta_file in self.model_dir.glob("*.json"):
            try:
                metadata = json.loads(meta_file.read_text())
                model_path = meta_file.with_suffix(".joblib")
                if model_path.exists():
                    record = TrainedModelRecord(
                        name=metadata.get("name", meta_file.stem),
                        model_type=metadata.get("model_type", "unknown"),
                        created_at=metadata.get("saved_at", "unknown"),
                        metrics=metadata.get("metrics", {}),
                        path=str(model_path),
                        n_features=metadata.get("n_features", 0),
                        feature_names=metadata.get("features", []),
                    )
                    self._records.append(record)
            except Exception as e:
                logger.warning(f"Failed to load metadata from {meta_file}: {e}")

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        preset: str = "rf_classifier",
        name: Optional[str] = None,
        feature_builder: Optional[FeatureBuilder] = None,
        save: bool = True,
    ) -> TrainedModelRecord:
        """
        Train a new model and optionally persist it.

        Returns a TrainedModelRecord.
        """
        model_name = name or f"model_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        mf = MLFactor(
            preset=preset,
            feature_builder=feature_builder,
            name=model_name,
            model_dir=str(self.model_dir),
        )

        # If feature_builder has features, transform data
        if feature_builder and len(feature_builder) > 0:
            X_transformed = feature_builder.build(X)
        else:
            X_transformed = X

        mf.fit(X_transformed, y)

        metrics = mf.evaluate(X_transformed, y)
        model_path = mf.save() if save else ""

        record = TrainedModelRecord(
            name=model_name,
            model_type=preset,
            created_at=datetime.utcnow().isoformat(),
            metrics=metrics,
            path=model_path,
            n_features=X_transformed.shape[1],
            feature_names=list(X_transformed.columns) if hasattr(X_transformed, "columns") else [],
        )
        self._models[model_name] = mf
        self._records.append(record)

        logger.info(f"Trained model '{model_name}' ({preset}): {metrics}")
        return record

    def predict(
        self,
        model_name: str,
        X: pd.DataFrame,
        return_proba: bool = False,
    ) -> np.ndarray:
        """
        Make predictions with a previously trained model.

        If the model is not loaded, attempts to load it from disk.
        """
        mf = self._get_model(model_name)

        if return_proba:
            return mf.predict_proba(X)
        return mf.predict(X)

    def list_models(self) -> List[TrainedModelRecord]:
        """Return all available model records."""
        return self._records

    def get_model(self, model_name: str) -> Optional[MLFactor]:
        """Get a loaded MLFactor instance by name."""
        return self._models.get(model_name)

    def _get_model(self, model_name: str) -> MLFactor:
        """Get or load a model by name."""
        if model_name in self._models:
            return self._models[model_name]

        # Try to load from disk
        model_path = self.model_dir / f"{model_name}.joblib"
        meta_path = self.model_dir / f"{model_name}.json"

        if model_path.exists():
            mf = MLFactor(name=model_name, model_dir=str(self.model_dir))
            mf.load(str(model_path))
            self._models[model_name] = mf
            return mf

        raise ValueError(
            f"Model '{model_name}' not found. "
            f"Available: {[r.name for r in self._records]}"
        )

    def delete_model(self, model_name: str) -> bool:
        """Delete a model from disk and memory."""
        if model_name in self._models:
            del self._models[model_name]

        removed = False
        for f in self.model_dir.glob(f"{model_name}.*"):
            f.unlink()
            removed = True

        self._records = [r for r in self._records if r.name != model_name]
        return removed

    def get_metrics(self, model_name: str) -> Optional[Dict[str, float]]:
        """Return stored metrics for a model."""
        for r in self._records:
            if r.name == model_name:
                return r.metrics
        return None


__all__ = [
    "FeatureBuilder",
    "WalkForwardCV",
    "MLFactor",
    "MLFactorRouter",
    "TrainedModelRecord",
]