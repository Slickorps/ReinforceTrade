import unittest
import math
import numpy as np
from backtesting import Backtester, EnhancedBacktester
from strategies import MultiAgentStrategy, RiskManager


def make_trend_data(n=300, start=100.0, drift=0.004):
    """Deterministic uptrend OHLCV series (no RNG) for regression tests."""
    data = []
    price = start
    for i in range(n):
        price *= 1 + drift + 0.0005 * ((i % 3) - 1)
        data.append({
            'timestamp': i,
            'open': price,
            'high': price * 1.001,
            'low': price * 0.999,
            'close': price,
            'volume': 1000.0,
        })
    return data

class TestBacktester(unittest.TestCase):
    def setUp(self):
        self.strategy = MultiAgentStrategy(use_rl=False)
        self.backtester = Backtester(self.strategy, initial_balance=10000)
    
    def test_initialization(self):
        """Test backtester initialization"""
        self.assertEqual(self.backtester.initial_balance, 10000)
        self.assertEqual(self.backtester.balance, 10000)
        self.assertEqual(len(self.backtester.positions), 0)
        self.assertEqual(len(self.backtester.trades), 0)
    
    def test_open_position(self):
        """Test position opening"""
        data = {'close': 50000, 'timestamp': 1234567890}
        self.backtester.open_position(data)
        
        self.assertEqual(len(self.backtester.positions), 1)
        self.assertEqual(self.backtester.positions[0]['entry_price'], 50000)
        self.assertEqual(self.backtester.positions[0]['side'], 'long')
    
    def test_close_position(self):
        """Test position closing"""
        # Open position first
        self.backtester.open_position({'close': 50000, 'timestamp': 1234567890})
        
        # Close position at profit
        position = self.backtester.positions[0]
        self.backtester.close_position(position, 51000)
        
        self.assertEqual(len(self.backtester.positions), 0)
        self.assertEqual(len(self.backtester.trades), 1)
        self.assertGreater(self.backtester.trades[0]['pnl'], 0)
    
    def test_calculate_results(self):
        """Test results calculation"""
        # Add some trades
        self.backtester.trades = [
            {'pnl': 1000, 'entry_price': 50000, 'exit_price': 51000},
            {'pnl': -500, 'entry_price': 51000, 'exit_price': 50500},
            {'pnl': 800, 'entry_price': 50500, 'exit_price': 51300}
        ]
        
        results = self.backtester.calculate_results()
        
        self.assertEqual(results['total_trades'], 3)
        self.assertEqual(results['total_pnl'], 1300)
        self.assertGreater(results['win_rate'], 0)

    def test_run_generates_trades_on_trend(self):
        """Regression: backtest must feed price history so strategies can enter trades"""
        results = self.backtester.run(make_trend_data())
        self.assertGreater(results['total_trades'], 0)
        self.assertGreater(results['win_rate'], 0)

class TestEnhancedBacktester(unittest.TestCase):
    def setUp(self):
        self.strategy = MultiAgentStrategy(use_rl=False)
        self.risk_manager = RiskManager()
        self.backtester = EnhancedBacktester(
            self.strategy,
            initial_balance=10000,
            risk_manager=self.risk_manager
        )
    
    def test_enhanced_initialization(self):
        """Test enhanced backtester initialization"""
        self.assertIsNotNone(self.backtester.risk_manager)
        self.assertEqual(len(self.backtester.equity_curve), 0)
    
    def test_equity_calculation(self):
        """Test equity calculation with open positions"""
        # Open a position
        self.backtester.open_position({'close': 50000}, position_size=1000)
        
        # Calculate equity at current price
        equity = self.backtester._calculate_equity(51000)
        
        # Should be balance + position value at current price
        self.assertGreater(equity, self.backtester.balance)
    
    def test_unrealized_pnl_calculation(self):
        """Test unrealized PnL calculation"""
        position = {
            'entry_price': 50000,
            'amount': 0.02,  # $1000 position
            'side': 'long'
        }
        
        # Price increased by 2%
        unrealized = self.backtester._calculate_unrealized_pnl(position, 51000)
        expected_pnl = (51000 - 50000) * 0.02
        self.assertAlmostEqual(unrealized, expected_pnl, places=2)
    
    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation"""
        # Simulate equity curve with drawdown
        self.backtester.equity_curve = [
            {'equity': 10000},  # Start
            {'equity': 11000},  # Peak
            {'equity': 10500},  # Drawdown
            {'equity': 10200},  # Deeper drawdown
            {'equity': 10800},  # Recovery
        ]
        
        max_dd = self.backtester._calculate_max_drawdown()
        
        # Max drawdown from 11000 to 10200 = 800/11000 = 7.27%
        expected_dd = (11000 - 10200) / 11000
        self.assertAlmostEqual(max_dd, expected_dd, places=4)

    def test_run_generates_trades_on_trend(self):
        """Regression: enhanced backtest must enter/exit positions on trending data"""
        backtester = EnhancedBacktester(
            MultiAgentStrategy(use_rl=False),
            initial_balance=10000,
        )
        results = backtester.run(make_trend_data())
        self.assertGreater(results['total_trades'], 0)
        self.assertGreater(results['win_rate'], 0)
        self.assertNotEqual(results['sharpe_ratio'], 0)

if __name__ == '__main__':
    unittest.main()
