"""
ML Factor Engine — sklearn-powered alpha signal generation.

Provides:
  - **Individual factors**: MomentumFactor, VolatilityFactor, SentimentFactor
    for standalone signal computation from OHLCV data.
  - **FactorPipeline**: Weighted composite signal pipeline aggregating
    multiple factors into a single [-1, 1] signal.
  - **MLFactor**: Scikit-learn Pipeline wrapper with fit/predict/predict_proba,
    walk-forward cross-validation, and model persistence via joblib.
  - **MLFactorRouter**: High-level API for multi-model training, prediction,
    listing, and deletion — suitable for REST API integration.

Usage::

    from ml import MomentumFactor, FactorPipeline, MLFactor, MLFactorRouter
"""

from .momentum_factor import MomentumFactor
from .volatility_factor import VolatilityFactor
from .sentiment_factor import SentimentFactor
from .factor_pipeline import FactorPipeline
from .ml_factor import (
    MLFactor,
    WalkForwardCV,
    FeatureBuilder,
    MLFactorRouter,
    TrainedModelRecord,
)

__all__ = [
    "MomentumFactor",
    "VolatilityFactor",
    "SentimentFactor",
    "FactorPipeline",
    "MLFactor",
    "WalkForwardCV",
    "FeatureBuilder",
    "MLFactorRouter",
    "TrainedModelRecord",
]
