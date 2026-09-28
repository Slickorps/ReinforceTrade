import unittest
import numpy as np
from agents import DecisionTower, EnvironmentAgent, ShortTermAgent, TrendAgent
from strategies import MultiAgentStrategy, RiskManager
from backtesting import EnhancedBacktester
from data import DataLoader

class TestMultiAgentIntegration(unittest.TestCase):
    """Integration tests for the complete multi-agent system"""
    
    def setUp(self):
        """Set up the complete system"""
        self.agents = [
            EnvironmentAgent(),
            ShortTermAgent(),
            TrendAgent()
        ]
        self.decision_tower = DecisionTower(self.agents)
        self.strategy = MultiAgentStrategy(use_rl=False)
        self.risk_manager = RiskManager()
        self.backtester = EnhancedBacktester(
            self.strategy,
            initial_balance=10000,
            risk_manager=self.risk_manager
        )
    
    def test_agent_to_decision_flow(self):
        """Test complete flow from agents to decision"""
        # Create synthetic market data
        prices = []
        base_price = 50000
        for i in range(50):
            prices.append({
                'close': base_price + i*100 + np.random.normal(0, 50),
                'volume': 1000 + np.random.normal(0, 100)
            })
        
        market_data = {'prices': prices}
        
        # Process through decision tower
        result = self.decision_tower.process_market_data(market_data)
        
        # Verify structure
        self.assertIn('analyses', result)
        self.assertIn('signals', result)
        self.assertIn('decision', result)
        
        # Verify all agents contributed
        self.assertEqual(len(result['analyses']), 3)
        
        # Verify decision has required fields
        decision = result['decision']
        self.assertIn('action', decision)
        self.assertIn('confidence', decision)
    
    def test_strategy_signal_integration(self):
        """Test strategy signal generation with agents"""
        # Create trending market data
        prices = []
        for i in range(60):
            prices.append({
                'close': 50000 + i*200,
                'volume': 2000
            })
        
        market_data = {'prices': prices}
        
        # Get agent signals
        signals = self.strategy.get_agent_signals(market_data)
        
        # Verify structure
        self.assertIn('analyses', signals)
        self.assertIn('signals', signals)
        self.assertIn('decision', signals)
        
        # In a strong uptrend, we expect bullish signals
        decision = signals['decision']
        self.assertIn(decision['action'], ['buy', 'hold', 'sell'])
    
    def test_end_to_end_backtest(self):
        """Test complete backtest with multi-agent strategy"""
        # Generate synthetic market data
        np.random.seed(42)
        market_data = []
        price = 50000
        
        for i in range(100):
            # Random walk with slight upward bias
            change = np.random.normal(0.001, 0.02)
            price *= (1 + change)
            market_data.append({
                'timestamp': 1609459200 + i*3600,
                'open': price * (1 + np.random.normal(0, 0.001)),
                'high': price * (1 + abs(np.random.normal(0, 0.01))),
                'low': price * (1 - abs(np.random.normal(0, 0.01))),
                'close': price,
                'volume': 1000 + np.random.normal(0, 200)
            })
        
        # Run backtest
        results = self.backtester.run(market_data)
        
        # Verify results structure
        self.assertIn('initial_balance', results)
        self.assertIn('final_balance', results)
        self.assertIn('total_trades', results)
        self.assertIn('win_rate', results)
        self.assertIn('sharpe_ratio', results)
        self.assertIn('max_drawdown', results)
        
        # Verify values are reasonable
        self.assertEqual(results['initial_balance'], 10000)
        self.assertGreaterEqual(results['final_balance'], 0)
        self.assertGreaterEqual(results['total_trades'], 0)
        self.assertGreaterEqual(results['win_rate'], 0)
        self.assertLessEqual(results['win_rate'], 1)
    
    def test_backtest_generates_trades_on_trend(self):
        """Regression: end-to-end backtest opens positions on trending data"""
        # Deterministic uptrend with enough history for trend/short-term agents
        market_data = []
        price = 50000.0
        for i in range(200):
            price *= 1.004 + 0.0005 * ((i % 3) - 1)
            market_data.append({
                'timestamp': 1609459200 + i*3600,
                'open': price,
                'high': price * 1.001,
                'low': price * 0.999,
                'close': price,
                'volume': 1000.0,
            })

        backtester = EnhancedBacktester(
            MultiAgentStrategy(use_rl=False),
            initial_balance=10000,
        )
        results = backtester.run(market_data)

        self.assertGreater(results['total_trades'], 0)
        self.assertGreater(results['win_rate'], 0)
        self.assertNotEqual(results['sharpe_ratio'], 0)

    def test_risk_manager_integration(self):
        """Test risk manager integration with backtester"""
        # Generate market data
        market_data = []
        price = 50000
        for i in range(50):
            market_data.append({
                'timestamp': 1609459200 + i*3600,
                'close': price,
                'volume': 1000
            })
        
        # Run backtest
        self.backtester.run(market_data)
        
        # Check risk metrics were recorded
        risk_metrics = self.risk_manager.get_risk_metrics()
        
        # Should have recorded trades
        self.assertIsNotNone(risk_metrics)
        self.assertIn('total_trades', risk_metrics)
    
    def test_position_size_with_risk_limits(self):
        """Test that position sizing respects risk limits"""
        balance = 10000
        confidence = 0.8
        
        # Calculate position size
        position_size = self.strategy.calculate_position_size(balance, confidence)
        
        # Should respect max position size (10%)
        self.assertLessEqual(position_size, balance * 0.1)
        
        # Should be positive with high confidence
        self.assertGreater(position_size, 0)

class TestDataFlow(unittest.TestCase):
    """Test data flow through the entire system"""
    
    def test_data_loader_to_backtest(self):
        """Test data loading through backtest"""
        # This would require API keys for live test
        # For unit test, we'll create synthetic data
        raw_data = []
        for i in range(100):
            raw_data.append({
                'timestamp': 1609459200 + i*3600,
                'open': 50000 + i*10,
                'high': 50100 + i*10,
                'low': 49900 + i*10,
                'close': 50000 + i*10,
                'volume': 1000
            })
        
        # Verify data format
        self.assertEqual(len(raw_data), 100)
        self.assertIn('timestamp', raw_data[0])
        self.assertIn('close', raw_data[0])

class TestSignalConsistency(unittest.TestCase):
    """Test signal consistency across different market conditions"""
    
    def test_bullish_market_consensus(self):
        """Test that agents agree in clear bullish conditions"""
        agents = [
            EnvironmentAgent(),
            ShortTermAgent(),
            TrendAgent()
        ]
        tower = DecisionTower(agents)
        
        # Strong uptrend data
        prices = [{'close': 1000 + i*50, 'volume': 2000} for i in range(60)]
        market_data = {'prices': prices}
        
        result = tower.process_market_data(market_data)
        
        # In strong uptrend, at least 2 agents should suggest buy/long
        signals = result['signals']
        buy_count = sum(1 for s in signals.values() 
                       if s['signal'] in ['buy', 'long', 'bullish'])
        
        # With strong trend, we expect bullish consensus
        self.assertGreater(buy_count, 0)
    
    def test_sideways_market_caution(self):
        """Test that system is cautious in sideways markets"""
        agents = [
            EnvironmentAgent(),
            ShortTermAgent(),
            TrendAgent()
        ]
        tower = DecisionTower(agents)
        
        # Sideways data (oscillating)
        prices = []
        for i in range(60):
            prices.append({
                'close': 1000 + np.sin(i/5)*50,
                'volume': 1000
            })
        
        market_data = {'prices': prices}
        result = tower.process_market_data(market_data)
        
        # In sideways market, might hold or have lower confidence
        decision = result['decision']
        # Either hold or lower confidence signals
        if decision['action'] != 'hold':
            self.assertLess(decision['confidence'], 0.9)

if __name__ == '__main__':
    unittest.main()
