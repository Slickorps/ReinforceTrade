import unittest
from unittest.mock import Mock, patch, MagicMock
import time
import pytest
from trading import CCXTExchange


class TestCCXTExchange(unittest.TestCase):
    """Test cases for CCXTExchange class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api_key = "test_api_key"
        self.secret = "test_secret"
        self.exchange_name = "binance"
        
    @patch('trading.ccxt_exchange.ccxt')
    def test_init_success(self, mock_ccxt):
        """Test successful initialization"""
        # Mock CCXT exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_ccxt.binance.return_value = mock_exchange
        
        # Create CCXTExchange instance
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        
        # Verify initialization
        self.assertEqual(exchange.exchange_name, self.exchange_name)
        self.assertTrue(exchange.sandbox)
        mock_exchange.load_markets.assert_called_once()
        
    @patch('trading.ccxt_exchange.ccxt')
    def test_init_failure(self, mock_ccxt):
        """Test initialization failure"""
        mock_ccxt.binance.side_effect = Exception("Connection failed")
        
        with self.assertRaises(Exception):
            CCXTExchange(self.api_key, self.secret, self.exchange_name)
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_get_balance_success(self, mock_ccxt):
        """Test successful balance retrieval"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_balance.return_value = {
            'free': {'BTC': 1.5, 'USDT': 1000.0, 'ETH': 0.0},
            'used': {'BTC': 0.5, 'USDT': 0.0, 'ETH': 0.0},
            'total': {'BTC': 2.0, 'USDT': 1000.0, 'ETH': 0.0}
        }
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        balance = exchange.get_balance()
        
        # Verify balance formatting
        expected = {'BTC': 1.5, 'USDT': 1000.0}
        self.assertEqual(balance, expected)
        mock_exchange.fetch_balance.assert_called_once()
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_get_balance_failure(self, mock_ccxt):
        """Test balance retrieval failure"""
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_balance.side_effect = Exception("API Error")
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        balance = exchange.get_balance()
        
        # Should return empty dict on failure
        self.assertEqual(balance, {})
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_get_ticker_success(self, mock_ccxt):
        """Test successful ticker retrieval"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_ticker.return_value = {
            'symbol': 'BTC/USDT',
            'last': 50000.0,
            'bid': 49999.0,
            'ask': 50001.0,
            'high': 51000.0,
            'low': 49000.0,
            'baseVolume': 100.0,
            'change': 1000.0,
            'percentage': 2.0,
            'timestamp': 1234567890000
        }
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        ticker = exchange.get_ticker('BTC/USDT')
        
        # Verify ticker formatting
        expected_keys = ['symbol', 'price', 'bid', 'ask', 'high', 'low', 'volume', 'change', 'change_percent', 'timestamp']
        for key in expected_keys:
            self.assertIn(key, ticker)
        
        self.assertEqual(ticker['price'], 50000.0)
        self.assertEqual(ticker['symbol'], 'BTC/USDT')
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_place_market_order_success(self, mock_ccxt):
        """Test successful market order placement"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_balance.return_value = {'free': {'USDT': 10000.0}}
        mock_exchange.create_order.return_value = {
            'id': '12345',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'type': 'market',
            'amount': 0.1,
            'price': None,
            'filled': 0.1,
            'remaining': 0.0,
            'status': 'closed',
            'timestamp': 1234567890000
        }
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        order = exchange.place_order('BTC/USDT', 'buy', 0.1, order_type='market')
        
        # Verify order formatting
        self.assertEqual(order['id'], '12345')
        self.assertEqual(order['symbol'], 'BTC/USDT')
        self.assertEqual(order['side'], 'buy')
        self.assertEqual(order['amount'], 0.1)
        self.assertEqual(order['status'], 'closed')
        
        # Verify API call
        mock_exchange.create_order.assert_called_once_with(
            symbol='BTC/USDT',
            type='market',
            side='buy',
            amount=0.1,
            price=None
        )
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_place_limit_order_success(self, mock_ccxt):
        """Test successful limit order placement"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_balance.return_value = {'free': {'USDT': 10000.0}}
        mock_exchange.create_order.return_value = {
            'id': '12346',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'type': 'limit',
            'amount': 0.1,
            'price': 49000.0,
            'filled': 0.0,
            'remaining': 0.1,
            'status': 'open',
            'timestamp': 1234567890000
        }
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        order = exchange.place_order('BTC/USDT', 'buy', 0.1, price=49000.0, order_type='limit')
        
        # Verify order formatting
        self.assertEqual(order['id'], '12346')
        self.assertEqual(order['price'], 49000.0)
        self.assertEqual(order['status'], 'open')
        
        # Verify API call
        mock_exchange.create_order.assert_called_once_with(
            symbol='BTC/USDT',
            type='limit',
            side='buy',
            amount=0.1,
            price=49000.0
        )
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_place_order_insufficient_balance(self, mock_ccxt):
        """Test order placement with insufficient balance"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_balance.return_value = {'free': {'USDT': 100.0}}  # Not enough
        mock_exchange.fetch_ticker.return_value = {
            'symbol': 'BTC/USDT',
            'last': 50000.0,
            'bid': 49999.0,
            'ask': 50001.0,
            'high': 51000.0,
            'low': 49000.0,
            'baseVolume': 100.0,
            'change': 1000.0,
            'percentage': 2.0,
            'timestamp': 1234567890000
        }
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        
        with self.assertRaises(ValueError) as context:
            exchange.place_order('BTC/USDT', 'buy', 0.1, order_type='market')
        
        self.assertIn("Insufficient USDT balance", str(context.exception))
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_place_order_invalid_parameters(self, mock_ccxt):
        """Test order placement with invalid parameters"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_balance.return_value = {'free': {'USDT': 10000.0}}
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        
        # Test invalid side
        with self.assertRaises(ValueError):
            exchange.place_order('BTC/USDT', 'invalid', 0.1)
        
        # Test invalid order type
        with self.assertRaises(ValueError):
            exchange.place_order('BTC/USDT', 'buy', 0.1, order_type='invalid')
        
        # Test limit order without price
        with self.assertRaises(ValueError):
            exchange.place_order('BTC/USDT', 'buy', 0.1, order_type='limit')
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_cancel_order_success(self, mock_ccxt):
        """Test successful order cancellation"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.cancel_order.return_value = {
            'id': '12345',
            'status': 'canceled'
        }
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        result = exchange.cancel_order('12345')
        
        self.assertTrue(result)
        mock_exchange.cancel_order.assert_called_once_with('12345')
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_cancel_order_failure(self, mock_ccxt):
        """Test order cancellation failure"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.cancel_order.side_effect = Exception("Cancel failed")
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        result = exchange.cancel_order('12345')
        
        self.assertFalse(result)
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_get_order_status_success(self, mock_ccxt):
        """Test successful order status retrieval"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_order.return_value = {
            'id': '12345',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'type': 'market',
            'amount': 0.1,
            'price': None,
            'filled': 0.1,
            'remaining': 0.0,
            'status': 'closed',
            'fee': {'cost': 1.0, 'currency': 'USDT'},
            'timestamp': 1234567890000
        }
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        order = exchange.get_order_status('12345')
        
        # Verify order formatting
        self.assertEqual(order['id'], '12345')
        self.assertEqual(order['status'], 'closed')
        self.assertEqual(order['filled'], 0.1)
        self.assertIn('fee', order)
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_get_market_data_success(self, mock_ccxt):
        """Test successful market data retrieval"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_ohlcv.return_value = [
            [1234567890000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0],
            [1234567950000, 50500.0, 51500.0, 49500.0, 51000.0, 120.0]
        ]
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        data = exchange.get_market_data('BTC/USDT', '1h', limit=2)
        
        # Verify data formatting
        self.assertEqual(len(data), 2)
        self.assertIn('timestamp', data[0])
        self.assertIn('open', data[0])
        self.assertIn('high', data[0])
        self.assertIn('low', data[0])
        self.assertIn('close', data[0])
        self.assertIn('volume', data[0])
        
        self.assertEqual(data[0]['open'], 50000.0)
        self.assertEqual(data[0]['close'], 50500.0)
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_check_connection_success(self, mock_ccxt):
        """Test successful connection check"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_time.return_value = int(time.time() * 1000)
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        result = exchange.check_connection()
        
        self.assertTrue(result)
        mock_exchange.fetch_time.assert_called_once()
    
    @patch('trading.ccxt_exchange.ccxt')
    def test_check_connection_failure(self, mock_ccxt):
        """Test connection check failure"""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_time.side_effect = Exception("Connection failed")
        mock_ccxt.binance.return_value = mock_exchange
        
        exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
        result = exchange.check_connection()
        
        self.assertFalse(result)
    
    def test_repr(self):
        """Test string representation"""
        with patch('trading.ccxt_exchange.ccxt'):
            exchange = CCXTExchange(self.api_key, self.secret, self.exchange_name)
            repr_str = repr(exchange)
            self.assertIn("CCXTExchange", repr_str)
            self.assertIn(self.exchange_name, repr_str)
            self.assertIn("sandbox=True", repr_str)


if __name__ == '__main__':
    unittest.main()
