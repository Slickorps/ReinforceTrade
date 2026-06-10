from typing import Dict, Any
import numpy as np
from utils.logger import logger


class SentimentFactor:
    """
    Sentiment proxy using order-flow imbalance derived from OHLCV data.
    Estimates buying/selling pressure as a sentiment substitute.
    """

    def __init__(self, lookback: int = 20):
        """
        Args:
            lookback: Window size for volume trend averaging.
        """
        self.lookback = lookback
        logger.info(f"SentimentFactor initialized (lookback={lookback})")

    def compute(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute sentiment proxy signal from OHLCV data.

        Derives buying/selling pressure from volume-weighted price delta
        (order-flow imbalance proxy) and volume trend.

        Args:
            market_data: Dict with ``"closes"``, ``"volumes"``, ``"highs"``,
                and ``"lows"`` keys, each containing a list of values.

        Returns:
            Dict with keys:
                - ``signal`` (float): Composite sentiment signal in [-1, 1].
                - ``imbalance`` (float): Volume-weighted buy/sell imbalance in [-1, 1].
                - ``pressure`` (str): One of ``"buying"``, ``"selling"``, ``"neutral"``.
                - ``vol_trend`` (float): Current volume relative to lookback average.
        """
        closes = market_data.get("closes", [])
        volumes = market_data.get("volumes", [])
        highs = market_data.get("highs", [])
        lows = market_data.get("lows", [])

        if len(closes) < 2 or len(volumes) < 2:
            return {"signal": 0.0, "imbalance": 0.0, "pressure": "neutral"}

        prices = np.array(closes, dtype=float)
        vols = np.array(volumes, dtype=float)
        hp = np.array(highs, dtype=float) if len(highs) == len(closes) else prices
        lp = np.array(lows, dtype=float) if len(lows) == len(closes) else prices

        # Price direction proxy: close vs previous close
        price_delta = np.diff(prices)
        vol_series = vols[1:]

        # Volume-weighted price delta (order flow imbalance proxy)
        up_volume = np.sum(vol_series[price_delta > 0])
        down_volume = np.sum(vol_series[price_delta < 0])
        total = up_volume + down_volume

        if total < 1e-10:
            imbalance = 0.0
        else:
            # Positive = buying pressure, Negative = selling pressure
            imbalance = (up_volume - down_volume) / total

        # Pressure label
        if imbalance > 0.15:
            pressure = "buying"
        elif imbalance < -0.15:
            pressure = "selling"
        else:
            pressure = "neutral"

        # Volume trend (is volume increasing or decreasing relative to average?)
        if len(vols) >= self.lookback:
            avg_vol = np.mean(vols[-self.lookback:])
            vol_trend = (vols[-1] - avg_vol) / (avg_vol + 1e-10)
        else:
            vol_trend = 0.0

        # Composite sentiment signal: imbalance + volume confirmation
        signal = np.clip(imbalance + vol_trend * 0.3, -1.0, 1.0)

        return {
            "signal": float(signal),
            "imbalance": float(imbalance),
            "pressure": pressure,
            "vol_trend": float(vol_trend),
        }