"""
Unit tests for TradingBot class.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, '..')

from trading_bot import TradingBot
from trading import CCXTExchange
from strategies import RiskManager, MultiAgentStrategy


class TestTradingBot(unittest.TestCase):
    """Test cases for TradingBot class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbols = ['BTC/USDT', 'ETH/USDT']
        
    def test_init_minimal(self):
        """Test minimal initialization"""
        bot = TradingBot(symbols=self.symbols)
        
        self.assertEqual(bot.symbols, self.symbols)
        self.assertIsNone(bot.exchange)
        self.assertFalse(bot.running)
        self.assertEqual(bot.total_trades, 0)
        self.assertIsNotNone(bot.risk_manager)
        self.assertIsNotNone(bot.decision_tower)
        
    def test_init_with_exchange(self):
        """Test initialization with exchange"""
        mock_exchange = Mock(spec=CCXTExchange)
        mock_exchange.check_connection.return_value = True
        
        bot = TradingBot(
            exchange=mock_exchange,
            symbols=self.symbols
        )
        
        self.assertEqual(bot.exchange, mock_exchange)
        
    def test_get_trading_stats_initial(self):
        """Test getting initial trading stats"""
        bot = TradingBot(symbols=self.symbols)
        
        stats = bot.get_trading_stats()
        
        self.assertFalse(stats['running'])
        self.assertEqual(stats['total_trades'], 0)
        self.assertEqual(stats['total_pnl'], 0.0)
        self.assertEqual(len(stats['current_positions']), 0)
        
    @patch('trading_bot.CCXTExchange')
    def test_run_live_no_exchange(self, mock_exchange):
        """Test run_live without exchange fails"""
        bot = TradingBot(symbols=self.symbols)
        # exchange is None by default
        
        # Should return early without error
        bot.run_live(test_mode=True)
        self.assertFalse(bot.running)
        
    @patch('trading_bot.CCXTExchange')
    def test_run_live_connection_failed(self, mock_exchange):
        """Test run_live with failed connection"""
        mock_exchange.check_connection.return_value = False
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        bot.run_live(test_mode=True)
        
        self.assertFalse(bot.running)
        
    def test_stop(self):
        """Test stopping the bot"""
        bot = TradingBot(symbols=self.symbols)
        bot.running = True
        
        bot.stop()
        
        self.assertFalse(bot.running)
        
    def test_calculate_drawdown(self):
        """Test drawdown calculation"""
        bot = TradingBot(symbols=self.symbols)
        
        # No PnL
        self.assertEqual(bot._calculate_drawdown(), 0.0)
        
        # Positive PnL, no drawdown
        bot.total_pnl = 100.0
        self.assertEqual(bot._calculate_drawdown(), 0.0)
        
        # PnL decreased (drawdown)
        bot.total_pnl = 50.0
        drawdown = bot._calculate_drawdown()
        self.assertGreater(drawdown, 0)
        
    def test_get_account_balance(self):
        """Test account balance retrieval"""
        mock_exchange = Mock(spec=CCXTExchange)
        mock_exchange.get_balance.return_value = {
            'USDT': 1000.0,
            'BTC': 0.5,
            'USD': 500.0
        }
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        balance = bot._get_account_balance()
        
        self.assertEqual(balance, 1500.0)  # 1000 USDT + 500 USD
        
    def test_get_account_balance_error(self):
        """Test account balance with error"""
        mock_exchange = Mock(spec=CCXTExchange)
        mock_exchange.get_balance.side_effect = Exception("API Error")
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        balance = bot._get_account_balance()
        
        self.assertEqual(balance, 0.0)
        
    def test_check_risk_limits_pass(self):
        """Test risk limits check passing"""
        bot = TradingBot(symbols=self.symbols)
        
        decision = {'BTC/USDT': {'action': 'BUY', 'strength': 0.8}}
        result = bot._check_risk_limits(decision)
        
        self.assertTrue(result)
        
    def test_check_risk_limits_drawdown(self):
        """Test risk limits check with high drawdown"""
        bot = TradingBot(symbols=self.symbols)
        bot.total_pnl = 100.0
        
        # Set high drawdown
        bot.total_pnl = 50.0
        
        decision = {'BTC/USDT': {'action': 'BUY', 'strength': 0.8}}
        result = bot._check_risk_limits(decision)
        
        # Should fail due to drawdown
        self.assertFalse(result)
        
    def test_fetch_market_data(self):
        """Test market data fetching"""
        mock_exchange = Mock(spec=CCXTExchange)
        mock_exchange.get_ticker.return_value = {
            'price': 50000.0,
            'bid': 49999.0,
            'ask': 50001.0
        }
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        data = bot._fetch_market_data()
        
        self.assertIn('BTC/USDT', data)
        self.assertIn('ETH/USDT', data)
        self.assertEqual(data['BTC/USDT']['price'], 50000.0)
        
    def test_fetch_market_data_error(self):
        """Test market data fetching with error"""
        mock_exchange = Mock(spec=CCXTExchange)
        mock_exchange.get_ticker.side_effect = Exception("API Error")
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        data = bot._fetch_market_data()
        
        self.assertEqual(len(data), 0)
        
    def test_execute_trade_buy(self):
        """Test executing buy trade"""
        mock_exchange = Mock(spec=CCXTExchange)
        mock_exchange.get_ticker.return_value = {'price': 50000.0}
        mock_exchange.place_order.return_value = {
            'id': '12345',
            'amount': 0.1,
            'price': 50000.0,
            'status': 'closed'
        }
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        bot.current_positions = {}
        
        signal = {'action': 'BUY', 'strength': 0.8}
        result = bot._execute_trade('BTC/USDT', signal)
        
        self.assertTrue(result)
        self.assertEqual(bot.total_trades, 1)
        
    def test_execute_trade_sell_no_position(self):
        """Test executing sell trade with no position"""
        mock_exchange = Mock(spec=CCXTExchange)
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        bot.current_positions = {}
        
        signal = {'action': 'SELL', 'strength': 0.8}
        result = bot._execute_trade('BTC/USDT', signal)
        
        self.assertFalse(result)
        
    def test_execute_trade_hold(self):
        """Test executing hold signal"""
        mock_exchange = Mock(spec=CCXTExchange)
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        
        signal = {'action': 'HOLD', 'strength': 0.5}
        result = bot._execute_trade('BTC/USDT', signal)
        
        self.assertFalse(result)
        
    def test_update_positions(self):
        """Test position update"""
        mock_exchange = Mock(spec=CCXTExchange)
        mock_exchange.get_balance.return_value = {
            'BTC': 0.5,
            'ETH': 1.0,
            'USDT': 1000.0
        }
        mock_exchange.get_ticker.return_value = {
            'price': 50000.0,
            'bid': 49999.0,
            'ask': 50001.0
        }
        
        bot = TradingBot(exchange=mock_exchange, symbols=self.symbols)
        bot._update_positions()
        
        self.assertIn('BTC/USDT', bot.current_positions)
        self.assertEqual(bot.current_positions['BTC/USDT']['size'], 0.5)
        
    def test_record_trade(self):
        """Test trade recording"""
        bot = TradingBot(symbols=self.symbols)
        
        order = {
            'id': '12345',
            'amount': 0.1,
            'price': 50000.0,
            'status': 'closed'
        }
        
        bot._record_trade('BTC/USDT', 'BUY', order)
        
        self.assertEqual(bot.total_trades, 1)
        self.assertEqual(len(bot.trade_history), 1)
        self.assertEqual(bot.trade_history[0]['symbol'], 'BTC/USDT')
        self.assertEqual(bot.trade_history[0]['action'], 'BUY')
        
    def test_repr(self):
        """Test string representation"""
        bot = TradingBot(symbols=self.symbols)
        
        repr_str = repr(bot)
        self.assertIn("TradingBot", repr_str)
        self.assertIn(str(self.symbols), repr_str)
        self.assertIn("False", repr_str)  # running=False


if __name__ == '__main__':
    unittest.main()
