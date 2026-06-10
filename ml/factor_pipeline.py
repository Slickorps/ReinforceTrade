from typing import Dict, Any, List, Optional
import numpy as np
from .momentum_factor import MomentumFactor
from .volatility_factor import VolatilityFactor
from .sentiment_factor import SentimentFactor
from utils.logger import logger


class FactorPipeline:
    """
    Composable Factor → Signal pipeline.
    Aggregates multiple alpha factors into a single composite signal
    with optional per-factor weighting.
    """

    DEFAULT_WEIGHTS = {
        "momentum": 0.5,
        "volatility": 0.25,
        "sentiment": 0.25,
    }

    def __init__(
        self,
        momentum: Optional[MomentumFactor] = None,
        volatility: Optional[VolatilityFactor] = None,
        sentiment: Optional[SentimentFactor] = None,
        weights: Optional[Dict[str, float]] = None,
    ):
        """
        Args:
            momentum: Pre-configured MomentumFactor instance. Uses defaults if ``None``.
            volatility: Pre-configured VolatilityFactor instance. Uses defaults if ``None``.
            sentiment: Pre-configured SentimentFactor instance. Uses defaults if ``None``.
            weights: Per-factor weights for composite signal. Defaults to
                ``{"momentum": 0.5, "volatility": 0.25, "sentiment": 0.25}``.
                Weights are automatically normalized to sum to 1.0.
        """
        self.momentum = momentum or MomentumFactor()
        self.volatility = volatility or VolatilityFactor()
        self.sentiment = sentiment or SentimentFactor()
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)

        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

        logger.info(f"FactorPipeline initialized with weights: {self.weights}")

    def compute(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute all factors and aggregate into a composite signal in [-1, 1].

        Args:
            market_data: Dict with OHLCV data passed to each factor's ``compute``.
                Expected keys: ``"closes"``, ``"highs"``, ``"lows"``, ``"volumes"``.

        Returns:
            Dict with keys:
                - ``signal`` (float): Weighted composite factor signal in [-1, 1].
                - ``factors`` (dict): Per-factor breakdown with ``signal``, ``weight``,
                  and ``weighted`` contribution for each factor.
                - ``weights_used`` (dict): The normalized weights applied.
        """
        factor_results = {
            "momentum": self.momentum.compute(market_data),
            "volatility": self.volatility.compute(market_data),
            "sentiment": self.sentiment.compute(market_data),
        }

        # Weighted composite signal
        composite = 0.0
        details = {}
        for name, result in factor_results.items():
            weight = self.weights.get(name, 0.0)
            signal = result.get("signal", 0.0)
            composite += weight * signal
            details[name] = {
                "signal": signal,
                "weight": weight,
                "weighted": weight * signal,
            }

        composite = float(np.clip(composite, -1.0, 1.0))

        return {
            "signal": composite,
            "factors": details,
            "weights_used": self.weights,
        }

    def update_weights(self, weights: Dict[str, float]) -> None:
        """
        Dynamically adjust per-factor weights.

        Args:
            weights: New weight mapping (e.g., ``{"momentum": 0.6, "volatility": 0.2}``).
                Automatically normalized to sum to 1.0.
        """
        total = sum(weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in weights.items()}
            logger.info(f"FactorPipeline weights updated: {self.weights}")