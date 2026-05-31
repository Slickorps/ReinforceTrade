"""
Machine Learning Factor Integration Example.

Demonstrates how to use the ML factor pipeline:
  1. MomentumFactor — ROC, MACD, RSI signals
  2. VolatilityFactor — ATR, regime classification, weight adjustment
  3. SentimentFactor — order-flow imbalance proxy

These can be used standalone or combined via FactorPipeline
and integrated into MultiAgentStrategy.
"""

import numpy as np
from ml import MomentumFactor, VolatilityFactor, SentimentFactor, FactorPipeline
from strategies import MultiAgentStrategy


def generate_sample_data(bars: int = 100, trend: float = 0.0) -> dict:
    """Generate synthetic OHLCV data with optional trend."""
    np.random.seed(42)
    closes = np.cumprod(1 + np.random.randn(bars) * 0.012 + trend) * 100
    highs = closes * (1 + np.abs(np.random.randn(bars)) * 0.004)
    lows = closes * (1 - np.abs(np.random.randn(bars)) * 0.004)
    volumes = np.random.randint(2000, 20000, bars)
    return {
        "closes": closes.tolist(),
        "highs": highs.tolist(),
        "lows": lows.tolist(),
        "volumes": volumes.tolist(),
    }


def demo_individual_factors(data: dict):
    """Run each factor independently and print results."""
    print("=" * 60)
    print("Individual Factor Signals")
    print("=" * 60)

    # Momentum
    mf = MomentumFactor(roc_period=14, rsi_period=14)
    mom = mf.compute(data)
    print(f"\nMomentumFactor:")
    print(f"  signal={mom['signal']:.4f}  roc={mom['roc']:.4f}  "
          f"macd={mom['macd_signal']:.4f}  rsi={mom['rsi']:.1f}")

    # Volatility
    vf = VolatilityFactor(atr_period=14, hist_period=50)
    vol = vf.compute(data)
    print(f"\nVolatilityFactor:")
    print(f"  signal={vol['signal']:.4f}  regime={vol['regime']}  "
          f"atr_pct={vol['atr_pct']:.4f}  hist_vol={vol['hist_vol']:.4f}  "
          f"weight_mult={vol['weight_multiplier']:.2f}")

    # Sentiment
    sf = SentimentFactor(lookback=20)
    sen = sf.compute(data)
    print(f"\nSentimentFactor:")
    print(f"  signal={sen['signal']:.4f}  imbalance={sen['imbalance']:.4f}  "
          f"pressure={sen['pressure']}  vol_trend={sen['vol_trend']:.4f}")


def demo_pipeline(data: dict):
    """Combine all factors via FactorPipeline."""
    print("\n" + "=" * 60)
    print("FactorPipeline — Composite Signal")
    print("=" * 60)

    pipeline = FactorPipeline(weights={"momentum": 0.5, "volatility": 0.25, "sentiment": 0.25})
    result = pipeline.compute(data)

    print(f"\nComposite signal: {result['signal']:.4f}  (range: [-1, 1])")
    print(f"Weights: {result['weights_used']}")
    print("Per-factor detail:")
    for name, detail in result["factors"].items():
        print(f"  {name}: raw={detail['signal']:.4f}  "
              f"weight={detail['weight']:.2f}  "
              f"weighted={detail['weighted']:.4f}")

    # Show how to dynamically re-weight
    print("\n  → Switching to risk-off weights (volatility → 0.6)")
    pipeline.update_weights({"momentum": 0.2, "volatility": 0.6, "sentiment": 0.2})
    result2 = pipeline.compute(data)
    print(f"  Composite (risk-off): {result2['signal']:.4f}")


def demo_strategy_integration():
    """
    Demonstrate how ML factors feed into MultiAgentStrategy.
    MultiAgentStrategy uses DecisionTower which can accept
    factor signals as additional market_data fields.
    """
    print("\n" + "=" * 60)
    print("MultiAgentStrategy + ML Factor Integration")
    print("=" * 60)

    strategy = MultiAgentStrategy(use_rl=False, confidence_threshold=0.6)

    # Prepare market data with factor signals
    data = generate_sample_data(bars=120, trend=0.0005)
    pipeline = FactorPipeline()
    factor_result = pipeline.compute(data)

    enriched_data = {
        **data,
        "factor_signal": factor_result["signal"],
        "factor_details": factor_result["factors"],
        # Simulated current price / OHLCV
        "close": data["closes"][-1],
        "high": data["highs"][-1],
        "low": data["lows"][-1],
        "volume": data["volumes"][-1],
        "timestamp": 1700000000,
        "symbol": "BTC/USDT",
    }

    # Decision tower processes market data includes factor signals
    should_enter = strategy.should_enter(enriched_data)

    print(f"\n  Factor composite signal: {factor_result['signal']:.4f}")
    print(f"  Should enter position:   {should_enter}")

    if should_enter:
        # Calculate position size (confidence from decision tower)
        decision_tower_result = strategy.decision_tower.process_market_data(enriched_data)
        confidence = decision_tower_result["decision"]["confidence"]
        position_size = strategy.calculate_position_size(balance=10000.0, confidence=confidence)
        print(f"  Confidence:              {confidence:.4f}")
        print(f"  Position size:           ${position_size:.2f}")


if __name__ == "__main__":
    data = generate_sample_data(bars=120, trend=0.0005)

    demo_individual_factors(data)
    demo_pipeline(data)
    demo_strategy_integration()

    print("\n" + "=" * 60)
    print("ML Factor Integration Demo Complete")
    print("=" * 60)