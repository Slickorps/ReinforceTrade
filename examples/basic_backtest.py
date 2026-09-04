#!/usr/bin/env python3
"""
Basic Backtest Example
This example shows how to run a simple backtest with the multi-agent strategy.
"""

import sys
sys.path.insert(0, '..')

# Windows consoles often use a legacy code page (e.g. GBK) that cannot encode
# emoji glyphs used below; force UTF-8 output where supported.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from data import DataLoader
from strategies import MultiAgentStrategy, RiskManager
from backtesting import EnhancedBacktester
from reports import ReportGenerator
from utils import logger
import numpy as np

def generate_synthetic_data(num_points=200):
    """Generate synthetic market data for testing"""
    np.random.seed(42)
    data = []
    price = 50000
    
    for i in range(num_points):
        # Random walk with slight trend
        change = np.random.normal(0.0005, 0.015)
        price *= (1 + change)
        
        data.append({
            'timestamp': 1609459200 + i*3600,
            'open': price * (1 + np.random.normal(0, 0.001)),
            'high': price * (1 + abs(np.random.normal(0, 0.008))),
            'low': price * (1 - abs(np.random.normal(0, 0.008))),
            'close': price,
            'volume': 1000 + abs(np.random.normal(0, 300))
        })
    
    return data

def run_basic_backtest():
    """Run a basic backtest with synthetic data"""
    logger.info("=" * 60)
    logger.info("Starting Basic Backtest Example")
    logger.info("=" * 60)
    
    # Generate or load data
    logger.info("Loading market data...")
    try:
        # Try to fetch from exchange (requires API keys)
        data_loader = DataLoader()
        data = data_loader.fetch_historical_data(
            symbol='BTC/USDT',
            timeframe='1h',
            limit=200
        )
        logger.info(f"Loaded {len(data)} data points from exchange")
    except Exception as e:
        logger.warning(f"Could not fetch from exchange: {e}")
        logger.info("Using synthetic data for demonstration")
        data = generate_synthetic_data(200)
    
    # Create strategy
    logger.info("Creating multi-agent strategy...")
    strategy = MultiAgentStrategy(
        use_rl=False,  # Set to True if you have trained RL models
        confidence_threshold=0.6
    )
    
    # Create risk manager
    risk_manager = RiskManager(
        max_risk_per_trade=0.01,
        max_portfolio_risk=0.05
    )
    
    # Create backtester
    logger.info("Initializing backtester...")
    backtester = EnhancedBacktester(
        strategy=strategy,
        initial_balance=10000,
        risk_manager=risk_manager
    )
    
    # Run backtest
    logger.info("Running backtest...")
    results = backtester.run(data)
    
    # Display results
    logger.info("=" * 60)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"Initial Balance: ${results['initial_balance']:,.2f}")
    logger.info(f"Final Balance: ${results['final_balance']:,.2f}")
    logger.info(f"Total Return: {results['total_return_pct']:.2f}%")
    logger.info(f"Total Trades: {results['total_trades']}")
    logger.info(f"Win Rate: {results['win_rate_pct']:.1f}%")
    logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    logger.info(f"Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    logger.info(f"Profit Factor: {results['profit_factor']:.2f}")
    
    # Generate report
    logger.info("Generating visual report...")
    report_gen = ReportGenerator(output_dir="../reports")
    report_dir = report_gen.generate_full_report(
        results=results,
        strategy_name="BasicMultiAgentStrategy"
    )
    
    logger.info(f"Report generated at: {report_dir}")
    logger.info("Open report.html in your browser to see detailed results")
    
    return results

if __name__ == '__main__':
    results = run_basic_backtest()
    
    # Simple assertion for demonstration
    assert results['initial_balance'] == 10000
    print("\n✅ Basic backtest completed successfully!")
