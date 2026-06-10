from typing import Dict, Any
import numpy as np
from utils.logger import logger


class MomentumFactor:
    """
    Momentum factors: ROC, MACD crossover strength, RSI signal.
    Computes alpha signals from price-based momentum indicators.
    """

    def __init__(self, roc_period: int = 14, rsi_period: int = 14):
        """
        Args:
            roc_period: Lookback window for Rate-of-Change calculation.
            rsi_period: Lookback window for RSI calculation.
        """
        self.roc_period = roc_period
        self.rsi_period = rsi_period
        logger.info(f"MomentumFactor initialized (roc={roc_period}, rsi={rsi_period})")

    def compute(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute momentum-based alpha signal from price data.

        Args:
            market_data: Dict with ``"closes"`` key containing a list of closing prices.

        Returns:
            Dict with keys:
                - ``signal`` (float): Composite momentum signal in [-1, 1].
                - ``roc`` (float): Rate-of-change over ``roc_period``.
                - ``macd_signal`` (float): MACD crossover strength normalized.
                - ``rsi`` (float): RSI value in [0, 100].
        """
        closes = market_data.get("closes", [])
        if len(closes) < max(self.roc_period, self.rsi_period) + 1:
            return {"signal": 0.0, "roc": 0.0, "macd_signal": 0.0, "rsi": 50.0}

        prices = np.array(closes, dtype=float)

        # ROC (Rate of Change)
        roc = (prices[-1] - prices[-self.roc_period]) / prices[-self.roc_period]

        # MACD crossover strength — compute full MACD line over history
        macd_line = np.array([
            self._ema(prices[:i+1], 12) - self._ema(prices[:i+1], 26)
            for i in range(25, len(prices))
        ]) if len(prices) > 26 else np.array([0.0])
        macd = macd_line[-1]
        signal_line = self._ema(macd_line, 9) if len(macd_line) > 1 else 0.0
        macd_strength = (macd - signal_line) / (prices[-1] + 1e-10)

        # RSI
        gains = np.diff(prices)
        avg_gain = np.mean(gains[gains > 0]) if np.any(gains > 0) else 0.0
        avg_loss = -np.mean(gains[gains < 0]) if np.any(gains < 0) else 1e-10
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # Composite momentum signal: normalized [-1, 1]
        signal = np.clip(roc * 5 + macd_strength * 10 + (rsi - 50) / 50 * 0.3, -1.0, 1.0)

        return {
            "signal": float(signal),
            "roc": float(roc),
            "macd_signal": float(macd_strength),
            "rsi": float(rsi),
        }

    @staticmethod
    def _ema(prices: np.ndarray, period: int) -> float:
        """
        Compute Exponential Moving Average for a price series.

        Args:
            prices: 1-D array of price values.
            period: EMA lookback period.

        Returns:
            The EMA value at the most recent data point.
        """
        if len(prices) < period:
            return float(prices[-1])
        multiplier = 2.0 / (period + 1)
        ema = float(prices[0])
        for p in prices[1:]:
            ema = (p - ema) * multiplier + ema
        return ema