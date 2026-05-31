from typing import Dict, Any, Tuple
import numpy as np
from utils.logger import logger


class VolatilityFactor:
    """
    Volatility regime classifier: low / medium / high volatility.
    Adjusts position sizing weights based on market conditions.
    """

    REGIME_LOW = "low"
    REGIME_MEDIUM = "medium"
    REGIME_HIGH = "high"

    def __init__(self, atr_period: int = 14, hist_period: int = 50):
        self.atr_period = atr_period
        self.hist_period = hist_period
        logger.info(f"VolatilityFactor initialized (atr={atr_period}, hist={hist_period})")

    def compute(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        highs = market_data.get("highs", [])
        lows = market_data.get("lows", [])
        closes = market_data.get("closes", [])

        if len(closes) < 2:
            return {"signal": 0.0, "regime": self.REGIME_MEDIUM, "atr_pct": 0.0, "weight_multiplier": 1.0}

        prices = np.array(closes, dtype=float)
        hp = np.array(highs, dtype=float) if len(highs) == len(closes) else prices
        lp = np.array(lows, dtype=float) if len(lows) == len(closes) else prices

        # ATR (Average True Range) as % of price
        if len(closes) < self.atr_period + 1:
            tr = hp[-1] - lp[-1]
            atr = tr
        else:
            tr_values = []
            for i in range(1, min(self.atr_period + 1, len(closes))):
                high_low = hp[-i] - lp[-i]
                high_close = abs(hp[-i] - prices[-i - 1])
                low_close = abs(lp[-i] - prices[-i - 1])
                tr_values.append(max(high_low, high_close, low_close))
            atr = np.mean(tr_values)

        atr_pct = atr / (prices[-1] + 1e-10)

        # Historical volatility (std of log returns)
        if len(prices) >= self.hist_period:
            log_returns = np.diff(np.log(prices[-self.hist_period:]))
        else:
            log_returns = np.diff(np.log(prices))
        hist_vol = np.std(log_returns)

        # Classify regime using percentiles
        if hist_vol < 0.01:
            regime = self.REGIME_LOW
        elif hist_vol < 0.03:
            regime = self.REGIME_MEDIUM
        else:
            regime = self.REGIME_HIGH

        # Weight multiplier: inverse to volatility
        weight_map = {
            self.REGIME_LOW: 1.5,
            self.REGIME_MEDIUM: 1.0,
            self.REGIME_HIGH: 0.5,
        }
        weight_multiplier = weight_map[regime]

        # Signal: negative for high vol (risk-off), positive for low vol (risk-on)
        signal_map = {self.REGIME_LOW: 0.3, self.REGIME_MEDIUM: 0.0, self.REGIME_HIGH: -0.5}
        signal = signal_map[regime]

        return {
            "signal": signal,
            "regime": regime,
            "atr_pct": float(atr_pct),
            "hist_vol": float(hist_vol),
            "weight_multiplier": weight_multiplier,
        }