"""
Unit tests for WebSocketClient and implementations.
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncio
import json
import sys
import websockets
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


class TestWebSocketAsyncLifecycle(unittest.IsolatedAsyncioTestCase):
    """Async lifecycle: connect/disconnect, reconnect, heartbeat, message routing"""

    def make_client(self, **config_kwargs):
        return MockWebSocket('mock', ['BTC/USDT'], WebSocketConfig(**config_kwargs))

    async def test_connect_success(self):
        client = self.make_client()
        ws = AsyncMock()

        with patch('trading.websocket_client.websockets.connect',
                   new=AsyncMock(return_value=ws)) as connect, \
                patch.object(client, '_receive_loop', new=AsyncMock()), \
                patch.object(client, '_heartbeat_loop', new=AsyncMock()):
            ok = await client.connect()

        self.assertTrue(ok)
        self.assertTrue(client.connected)
        self.assertTrue(client.running)
        ws.send.assert_awaited_once_with('{"subscribe": true}')
        connect.assert_awaited_once()

    async def test_connect_failure(self):
        client = self.make_client()

        with patch('trading.websocket_client.websockets.connect',
                   new=AsyncMock(side_effect=RuntimeError('refused'))):
            ok = await client.connect()

        self.assertFalse(ok)
        self.assertFalse(client.connected)

    async def test_disconnect_cancels_tasks_and_closes(self):
        client = self.make_client()
        client.websocket = AsyncMock()
        client.connected = True
        client.running = True
        recv_task = asyncio.create_task(asyncio.sleep(10))
        hb_task = asyncio.create_task(asyncio.sleep(10))
        client._receive_task = recv_task
        client._heartbeat_task = hb_task

        await client.disconnect()
        await asyncio.gather(recv_task, hb_task, return_exceptions=True)

        self.assertFalse(client.connected)
        self.assertFalse(client.running)
        self.assertIsNone(client.websocket)
        self.assertFalse(client.is_connected())

    async def test_disconnect_swallows_close_errors(self):
        client = self.make_client()
        client.websocket = AsyncMock()
        client.websocket.close.side_effect = RuntimeError('close failed')
        client.connected = True

        await client.disconnect()  # must not raise

        self.assertFalse(client.connected)

    async def test_check_connection_without_socket(self):
        client = self.make_client()
        self.assertFalse(await client._check_connection())

    async def test_check_connection_true(self):
        client = self.make_client()
        client.websocket = AsyncMock()
        self.assertTrue(await client._check_connection())
        client.websocket.send.assert_awaited_once()

    async def test_check_connection_false_on_send_error(self):
        client = self.make_client()
        client.websocket = AsyncMock()
        client.websocket.send.side_effect = RuntimeError('dead')
        self.assertFalse(await client._check_connection())

    async def test_heartbeat_sends_pings(self):
        client = self.make_client(heartbeat_interval=0)
        client.websocket = AsyncMock()
        client.connected = True
        client.running = True

        task = asyncio.create_task(client._heartbeat_loop())
        await asyncio.sleep(0.02)
        client.running = False
        task.cancel()
        await task  # loop swallows CancelledError and exits

        self.assertGreaterEqual(client.websocket.send.await_count, 1)

    async def test_heartbeat_swallows_send_errors(self):
        client = self.make_client(heartbeat_interval=0)
        client.websocket = AsyncMock()
        client.websocket.send.side_effect = RuntimeError('nope')
        client.connected = True
        client.running = True

        task = asyncio.create_task(client._heartbeat_loop())
        await asyncio.sleep(0.02)
        client.running = False
        task.cancel()
        await task  # must not raise

        self.assertGreaterEqual(client.websocket.send.await_count, 1)

    async def test_receive_loop_dispatches_messages(self):
        client = self.make_client()
        client.websocket = AsyncMock()
        client.websocket.recv.side_effect = [json.dumps({'raw': True}), asyncio.CancelledError()]
        client.running = True

        await client._receive_loop()

        self.assertEqual(client.get_price('BTC/USDT'), 50000.0)

    async def test_receive_loop_reconnects_on_timeout(self):
        client = self.make_client()
        client.websocket = AsyncMock()
        client.websocket.recv.side_effect = [asyncio.TimeoutError(), asyncio.CancelledError()]
        client.running = True
        client._check_connection = AsyncMock(return_value=False)
        client._reconnect = AsyncMock()

        await client._receive_loop()

        client._reconnect.assert_awaited_once()

    async def test_receive_loop_reconnects_on_connection_closed(self):
        client = self.make_client()
        client.websocket = AsyncMock()
        client.websocket.recv.side_effect = [
            websockets.exceptions.ConnectionClosed(None, None),
            asyncio.CancelledError(),
        ]
        client.running = True
        client._reconnect = AsyncMock()

        await client._receive_loop()

        client._reconnect.assert_awaited_once()

    async def test_receive_loop_ignores_invalid_json(self):
        client = self.make_client()
        client.websocket = AsyncMock()
        client.websocket.recv.side_effect = ['not-json', asyncio.CancelledError()]
        client.running = True

        await client._receive_loop()  # must not raise

        self.assertIsNone(client.get_price('BTC/USDT'))

    async def test_reconnect_success_resets_counter(self):
        client = self.make_client(reconnect_attempts=3, reconnect_delay=0)
        client.disconnect = AsyncMock()
        client.connect = AsyncMock(return_value=True)
        client.reconnect_count = 2

        await client._reconnect()

        client.disconnect.assert_awaited_once()
        client.connect.assert_awaited_once()
        self.assertEqual(client.reconnect_count, 0)

    async def test_reconnect_gives_up_after_max_attempts(self):
        client = self.make_client(reconnect_attempts=1, reconnect_delay=0)
        client.connect = AsyncMock()
        client.reconnect_count = 1

        await client._reconnect()

        self.assertFalse(client.running)
        client.connect.assert_not_awaited()

    async def test_reconnect_failure_keeps_attempt_count(self):
        client = self.make_client(reconnect_attempts=3, reconnect_delay=0)
        client.disconnect = AsyncMock()
        client.connect = AsyncMock(return_value=False)

        await client._reconnect()

        self.assertEqual(client.reconnect_count, 1)

    async def test_reconnect_swallows_errors(self):
        client = self.make_client(reconnect_attempts=3, reconnect_delay=0)
        client.disconnect = AsyncMock(side_effect=RuntimeError('boom'))
        client.connect = AsyncMock(return_value=True)

        await client._reconnect()  # must not raise

    async def test_handle_message_ticker_updates_cache_and_callbacks(self):
        client = self.make_client()
        received = []

        def callback(data):
            received.append(data)

        client.on_ticker(callback)

        await client._handle_message({'type': 'ticker', 'symbol': 'BTC/USDT', 'price': 123.0})

        self.assertEqual(client.get_price('BTC/USDT'), 123.0)
        self.assertIsNotNone(client.get_last_update('BTC/USDT'))
        self.assertEqual(len(received), 1)

    async def test_handle_message_orderbook_and_trade_callbacks(self):
        client = self.make_client()
        orderbook = []
        trades = []

        def on_orderbook(data):
            orderbook.append(data)

        def on_trade(data):
            trades.append(data)

        client.on_orderbook(on_orderbook)
        client.on_trade(on_trade)

        await client._handle_message({'type': 'orderbook'})
        await client._handle_message({'type': 'trade'})

        self.assertEqual(len(orderbook), 1)
        self.assertEqual(len(trades), 1)

    async def test_handle_message_swallows_callback_errors(self):
        client = self.make_client()

        def broken(data):
            raise RuntimeError('cb boom')

        client.on_ticker(broken)

        await client._handle_message({'type': 'ticker', 'symbol': 'BTC/USDT', 'price': 1.0})

        self.assertEqual(client.get_price('BTC/USDT'), 1.0)

    async def test_handle_message_ignores_unknown_type(self):
        client = self.make_client()
        await client._handle_message({'type': 'unknown'})
        self.assertIsNone(client.get_price('BTC/USDT'))

    async def test_is_connected_true(self):
        client = self.make_client()
        client.connected = True
        client.websocket = AsyncMock()
        self.assertTrue(client.is_connected())


if __name__ == '__main__':
    unittest.main()
