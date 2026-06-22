"""
Unit tests for WebSocketClient and implementations.
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncio
import sys
sys.path.insert(0, '..')

from trading.websocket_client import WebSocketClient, BinanceWebSocket, OKXWebSocket, WebSocketConfig
from datetime import datetime


class MockWebSocket(WebSocketClient):
    """Mock WebSocket client for testing"""
    
    def _get_ws_url(self) -> str:
        return "wss://test.example.com/ws"
    
    def _subscribe_message(self) -> str:
        return "{\"subscribe\": true}"
    
    def _parse_message(self, message):
        return {
            'type': 'ticker',
            'symbol': 'BTC/USDT',
            'price': 50000.0
        }


class TestWebSocketClient(unittest.TestCase):
    """Test cases for WebSocketClient base class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.exchange_name = 'mock'
        self.symbols = ['BTC/USDT', 'ETH/USDT']
        self.config = WebSocketConfig()
        
    def test_websocket_config(self):
        """Test WebSocketConfig dataclass"""
        config = WebSocketConfig(
            reconnect_attempts=3,
            reconnect_delay=2.0,
            heartbeat_interval=15
        )
        
        self.assertEqual(config.reconnect_attempts, 3)
        self.assertEqual(config.reconnect_delay, 2.0)
        self.assertEqual(config.heartbeat_interval, 15)
        
    def test_init(self):
        """Test WebSocketClient initialization"""
        client = MockWebSocket(self.exchange_name, self.symbols, self.config)
        
        self.assertEqual(client.exchange_name, 'mock')
        self.assertEqual(client.symbols, self.symbols)
        self.assertEqual(client.config, self.config)
        self.assertFalse(client.connected)
        self.assertFalse(client.running)
        self.assertIsNone(client.websocket)
        
    def test_on_ticker(self):
        """Test ticker callback registration"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        
        def callback(data):
            pass
        
        client.on_ticker(callback)
        
        self.assertEqual(len(client._ticker_callbacks), 1)
        self.assertIn(callback, client._ticker_callbacks)
        
    def test_on_orderbook(self):
        """Test orderbook callback registration"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        
        def callback(data):
            pass
        
        client.on_orderbook(callback)
        
        self.assertEqual(len(client._orderbook_callbacks), 1)
        
    def test_on_trade(self):
        """Test trade callback registration"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        
        def callback(data):
            pass
        
        client.on_trade(callback)
        
        self.assertEqual(len(client._trade_callbacks), 1)
        
    def test_on_error(self):
        """Test error callback registration"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        
        def callback(error):
            pass
        
        client.on_error(callback)
        
        self.assertEqual(len(client._error_callbacks), 1)
        
    def test_get_price_empty(self):
        """Test getting price when cache is empty"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        
        price = client.get_price('BTC/USDT')
        
        self.assertIsNone(price)
        
    def test_get_price_cached(self):
        """Test getting cached price"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        client._price_cache['BTC/USDT'] = 50000.0
        
        price = client.get_price('BTC/USDT')
        
        self.assertEqual(price, 50000.0)
        
    def test_get_last_update(self):
        """Test getting last update time"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        now = datetime.now()
        client._last_update['BTC/USDT'] = now
        
        update_time = client.get_last_update('BTC/USDT')
        
        self.assertEqual(update_time, now)
        
    def test_is_connected_false(self):
        """Test is_connected when not connected"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        
        self.assertFalse(client.is_connected())
        
    def test_repr(self):
        """Test string representation"""
        client = MockWebSocket(self.exchange_name, self.symbols)
        
        repr_str = repr(client)
        
        self.assertIn('WebSocketClient', repr_str)
        self.assertIn('mock', repr_str)
        self.assertIn('connected=False', repr_str)


class TestBinanceWebSocket(unittest.TestCase):
    """Test cases for BinanceWebSocket"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbols = ['BTC/USDT', 'ETH/USDT']
        
    def test_init(self):
        """Test BinanceWebSocket initialization"""
        client = BinanceWebSocket(self.symbols)
        
        self.assertEqual(client.exchange_name, 'binance')
        self.assertEqual(client.symbols, self.symbols)
        self.assertEqual(client.base_url, "wss://stream.binance.com:9443/ws")
        
    def test_get_ws_url_single(self):
        """Test WebSocket URL generation for single symbol"""
        client = BinanceWebSocket(['BTC/USDT'])
        
        url = client._get_ws_url()
        
        self.assertIn('btcusdt@ticker', url.lower())
        
    def test_get_ws_url_multiple(self):
        """Test WebSocket URL generation for multiple symbols"""
        client = BinanceWebSocket(['BTC/USDT', 'ETH/USDT'])
        
        url = client._get_ws_url()
        
        self.assertIn('stream', url)
        self.assertIn('btcusdt@ticker', url.lower())
        self.assertIn('ethusdt@ticker', url.lower())
        
    def test_build_streams(self):
        """Test stream name building"""
        client = BinanceWebSocket(['BTC/USDT', 'ETH/USDT'])
        
        streams = client._build_streams()
        
        self.assertIn('btcusdt@ticker', streams.lower())
        self.assertIn('ethusdt@ticker', streams.lower())
        self.assertIn('/', streams)  # streams are separated by /
        
    def test_extract_symbol_from_stream(self):
        """Test symbol extraction from stream name"""
        client = BinanceWebSocket(self.symbols)
        
        symbol = client._extract_symbol_from_stream('btcusdt@ticker')
        
        self.assertEqual(symbol, 'BTC/USDT')
        
    def test_parse_ticker(self):
        """Test ticker data parsing"""
        client = BinanceWebSocket(self.symbols)
        
        raw_data = {
            's': 'BTCUSDT',
            'c': '50000.00',
            'b': '49999.00',
            'a': '50001.00',
            'h': '51000.00',
            'l': '49000.00',
            'v': '1000.00',
            'p': '1000.00',
            'P': '2.00',
            'E': 1234567890000
        }
        
        result = client._parse_ticker(raw_data, 'BTC/USDT')
        
        self.assertEqual(result['type'], 'ticker')
        self.assertEqual(result['symbol'], 'BTC/USDT')
        self.assertEqual(result['price'], 50000.00)
        self.assertEqual(result['bid'], 49999.00)
        self.assertEqual(result['ask'], 50001.00)
        
    def test_parse_combined_message(self):
        """Test parsing combined stream message"""
        client = BinanceWebSocket(self.symbols)
        
        message = {
            'stream': 'btcusdt@ticker',
            'data': {
                'c': '50000.00',
                'b': '49999.00',
                'a': '50001.00',
                'h': '51000.00',
                'l': '49000.00',
                'v': '1000.00',
                'p': '1000.00',
                'P': '2.00',
                'E': 1234567890000
            }
        }
        
        result = client._parse_message(message)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'ticker')
        self.assertEqual(result['symbol'], 'BTC/USDT')
        
    def test_parse_single_stream_message(self):
        """Test parsing single stream message"""
        client = BinanceWebSocket(self.symbols)
        
        message = {
            'e': '24hrTicker',
            's': 'BTCUSDT',
            'c': '50000.00',
            'b': '49999.00',
            'a': '50001.00',
            'h': '51000.00',
            'l': '49000.00',
            'v': '1000.00',
            'p': '1000.00',
            'P': '2.00',
            'E': 1234567890000
        }
        
        result = client._parse_message(message)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'ticker')
        
    def test_parse_unsupported_message(self):
        """Test parsing unsupported message type"""
        client = BinanceWebSocket(self.symbols)
        
        message = {
            'e': 'unknownEvent',
            'data': {}
        }
        
        result = client._parse_message(message)
        
        self.assertIsNone(result)
        
    def test_parse_error(self):
        """Test parsing with error"""
        client = BinanceWebSocket(self.symbols)
        
        message = None  # Invalid message
        
        result = client._parse_message(message)
        
        self.assertIsNone(result)


class TestOKXWebSocket(unittest.TestCase):
    """Test cases for OKXWebSocket"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbols = ['BTC/USDT', 'ETH/USDT']
        
    def test_init(self):
        """Test OKXWebSocket initialization"""
        client = OKXWebSocket(self.symbols)
        
        self.assertEqual(client.exchange_name, 'okx')
        self.assertEqual(client.symbols, self.symbols)
        self.assertEqual(client.base_url, "wss://ws.okex.com:8443/ws/v5/public")
        
    def test_get_ws_url(self):
        """Test WebSocket URL generation"""
        client = OKXWebSocket(self.symbols)
        
        url = client._get_ws_url()
        
        self.assertEqual(url, "wss://ws.okex.com:8443/ws/v5/public")
        
    def test_subscribe_message(self):
        """Test subscription message generation"""
        client = OKXWebSocket(['BTC/USDT'])
        
        import json
        msg = client._subscribe_message()
        data = json.loads(msg)
        
        self.assertEqual(data['op'], 'subscribe')
        self.assertEqual(len(data['args']), 1)
        self.assertEqual(data['args'][0]['channel'], 'tickers:BTC-USDT')
        
    def test_parse_subscribe_response(self):
        """Test parsing subscription response"""
        client = OKXWebSocket(self.symbols)
        
        message = {
            'event': 'subscribe',
            'channel': 'tickers:BTC-USDT'
        }
        
        result = client._parse_message(message)
        
        self.assertIsNone(result)  # Subscribe response returns None
        
    def test_parse_ticker_data(self):
        """Test parsing OKX ticker data"""
        client = OKXWebSocket(self.symbols)
        
        message = {
            'data': [{
                'instId': 'BTC-USDT',
                'last': '50000.00',
                'bidPx': '49999.00',
                'askPx': '50001.00',
                'high24h': '51000.00',
                'low24h': '49000.00',
                'vol24h': '1000.00',
                'change24h': '1000.00',
                'change24hPct': '2.00',
                'ts': '1234567890000'
            }]
        }
        
        result = client._parse_message(message)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'ticker')
        self.assertEqual(result['symbol'], 'BTC/USDT')
        self.assertEqual(result['price'], 50000.00)


if __name__ == '__main__':
    unittest.main()
