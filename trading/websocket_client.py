import asyncio
import websockets
import json
import time
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from utils.logger import logger


@dataclass
class WebSocketConfig:
    """Configuration for WebSocket connection"""
    reconnect_attempts: int = 5
    reconnect_delay: float = 1.0
    heartbeat_interval: int = 30
    ping_timeout: int = 10
    max_message_size: int = 10 * 1024 * 1024  # 10MB


class WebSocketClient(ABC):
    """
    Abstract base class for WebSocket clients.
    Provides common functionality for exchange WebSocket connections.
    """
    
    def __init__(self, exchange_name: str, symbols: List[str], config: Optional[WebSocketConfig] = None):
        self.exchange_name = exchange_name
        self.symbols = symbols
        self.config = config or WebSocketConfig()
        
        self.websocket: Optional[Any] = None
        self.running = False
        self.connected = False
        self.reconnect_count = 0
        
        # Callbacks
        self._ticker_callbacks: List[Callable] = []
        self._orderbook_callbacks: List[Callable] = []
        self._trade_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        
        # Data cache
        self._price_cache: Dict[str, float] = {}
        self._last_update: Dict[str, datetime] = {}
        
        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        
    @abstractmethod
    def _get_ws_url(self) -> str:
        """Get WebSocket URL for the exchange"""
        pass
    
    @abstractmethod
    def _subscribe_message(self) -> str:
        """Get subscription message"""
        pass
    
    @abstractmethod
    def _parse_message(self, message: Dict) -> Optional[Dict]:
        """Parse WebSocket message into standardized format"""
        pass
    
    async def connect(self) -> bool:
        """
        Connect to WebSocket server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            ws_url = self._get_ws_url()
            logger.info(f"Connecting to {self.exchange_name} WebSocket: {ws_url}")
            
            self.websocket = await websockets.connect(
                ws_url,
                ping_interval=self.config.heartbeat_interval,
                ping_timeout=self.config.ping_timeout,
                max_size=self.config.max_message_size
            )
            
            self.connected = True
            self.reconnect_count = 0
            logger.info(f"Connected to {self.exchange_name} WebSocket")
            
            # Send subscription message
            subscribe_msg = self._subscribe_message()
            await self.websocket.send(subscribe_msg)
            logger.info(f"Subscribed to: {self.symbols}")
            
            # Start receive loop
            self.running = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket server"""
        logger.info("Disconnecting WebSocket...")
        self.running = False
        
        # Cancel tasks
        if self._receive_task:
            self._receive_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        # Close connection
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        self.connected = False
        self.websocket = None
        logger.info("WebSocket disconnected")
    
    async def _receive_loop(self) -> None:
        """Main message receive loop"""
        try:
            while self.running and self.websocket:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=60.0
                    )
                    
                    # Parse message
                    data = json.loads(message)
                    parsed_data = self._parse_message(data)
                    
                    if parsed_data:
                        await self._handle_message(parsed_data)
                    
                except asyncio.TimeoutError:
                    logger.warning("WebSocket receive timeout, checking connection...")
                    if not await self._check_connection():
                        await self._reconnect()
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    await self._reconnect()
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except asyncio.CancelledError:
            logger.info("Receive loop cancelled")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Keep connection alive with periodic messages"""
        try:
            while self.running and self.websocket:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                if self.connected and self.websocket:
                    try:
                        # Send ping or heartbeat
                        ping_msg = json.dumps({'ping': int(time.time() * 1000)})
                        await self.websocket.send(ping_msg)
                        logger.debug("Sent heartbeat")
                    except Exception as e:
                        logger.warning(f"Heartbeat failed: {e}")
                        
        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}")
    
    async def _handle_message(self, data: Dict) -> None:
        """Handle parsed message and trigger callbacks"""
        try:
            msg_type = data.get('type')
            symbol = data.get('symbol')
            
            if msg_type == 'ticker' and symbol:
                # Update price cache
                self._price_cache[symbol] = data.get('price', 0)
                self._last_update[symbol] = datetime.now()
                
                # Trigger ticker callbacks
                for callback in self._ticker_callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Ticker callback error: {e}")
                        
            elif msg_type == 'orderbook':
                for callback in self._orderbook_callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Orderbook callback error: {e}")
                        
            elif msg_type == 'trade':
                for callback in self._trade_callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Trade callback error: {e}")
                        
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _check_connection(self) -> bool:
        """Check if WebSocket connection is alive"""
        if not self.websocket:
            return False
        
        try:
            # Try to send a ping
            ping_msg = json.dumps({'ping': int(time.time() * 1000)})
            await asyncio.wait_for(self.websocket.send(ping_msg), timeout=5.0)
            return True
        except Exception:
            return False
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect to WebSocket"""
        if self.reconnect_count >= self.config.reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.config.reconnect_attempts}) reached")
            self.running = False
            return
        
        self.reconnect_count += 1
        delay = self.config.reconnect_delay * (2 ** (self.reconnect_count - 1))  # Exponential backoff
        
        logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_count}/{self.config.reconnect_attempts})...")
        
        await asyncio.sleep(delay)
        
        try:
            await self.disconnect()
            success = await self.connect()
            
            if success:
                logger.info("Reconnection successful")
                self.reconnect_count = 0
            else:
                logger.error("Reconnection failed")
                
        except Exception as e:
            logger.error(f"Reconnection error: {e}")
    
    def on_ticker(self, callback: Callable[[Dict], None]) -> None:
        """Register ticker data callback"""
        self._ticker_callbacks.append(callback)
        logger.debug(f"Registered ticker callback: {callback.__name__}")
    
    def on_orderbook(self, callback: Callable[[Dict], None]) -> None:
        """Register orderbook data callback"""
        self._orderbook_callbacks.append(callback)
        logger.debug(f"Registered orderbook callback: {callback.__name__}")
    
    def on_trade(self, callback: Callable[[Dict], None]) -> None:
        """Register trade data callback"""
        self._trade_callbacks.append(callback)
        logger.debug(f"Registered trade callback: {callback.__name__}")
    
    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register error callback"""
        self._error_callbacks.append(callback)
        logger.debug(f"Registered error callback: {callback.__name__}")
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Get latest cached price for symbol"""
        return self._price_cache.get(symbol)
    
    def get_last_update(self, symbol: str) -> Optional[datetime]:
        """Get last update time for symbol"""
        return self._last_update.get(symbol)
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.connected and self.websocket is not None
    
    def __repr__(self) -> str:
        return f"WebSocketClient({self.exchange_name}, connected={self.connected})"


class BinanceWebSocket(WebSocketClient):
    """Binance WebSocket client implementation"""
    
    def __init__(self, symbols: List[str], config: Optional[WebSocketConfig] = None):
        super().__init__('binance', symbols, config)
        self.base_url = "wss://stream.binance.com:9443/ws"
        
    def _get_ws_url(self) -> str:
        """Get combined stream URL for all symbols"""
        if len(self.symbols) == 1:
            # Single symbol stream
            symbol = self.symbols[0].lower().replace('/', '')
            return f"{self.base_url}/{symbol}@ticker"
        else:
            # Multiple symbols - use combined stream
            streams = self._build_streams()
            return f"wss://stream.binance.com:9443/stream?streams={streams}"
    
    def _build_streams(self) -> str:
        """Build stream names for all symbols"""
        streams = []
        for symbol in self.symbols:
            normalized = symbol.lower().replace('/', '')
            streams.append(f"{normalized}@ticker")
        return '/'.join(streams)
    
    def _subscribe_message(self) -> str:
        """Build subscription message for Binance"""
        if len(self.symbols) == 1:
            # Single stream - no subscription needed for URL-based streams
            return json.dumps({})
        else:
            # Combined stream - subscription via URL, empty message
            return json.dumps({})
    
    def _parse_message(self, message: Dict) -> Optional[Dict]:
        """Parse Binance WebSocket message"""
        try:
            # Handle combined stream message
            if 'stream' in message and 'data' in message:
                stream = message['stream']
                data = message['data']
                
                if stream.endswith('@ticker'):
                    symbol = self._extract_symbol_from_stream(stream)
                    return self._parse_ticker(data, symbol)
                    
            # Handle single stream message
            elif 'e' in message:
                event_type = message['e']
                
                if event_type == '24hrTicker':
                    return self._parse_ticker(message, message.get('s'))
                    
            return None
            
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None
    
    def _extract_symbol_from_stream(self, stream: str) -> str:
        """Extract symbol from stream name"""
        # stream format: btcusdt@ticker
        symbol_part = stream.replace('@ticker', '')
        # Convert back to standard format: BTC/USDT
        for i in range(len(symbol_part) - 1, 0, -1):
            if symbol_part[i:].upper() in ['USDT', 'USD', 'BUSD', 'USDC']:
                base = symbol_part[:i]
                quote = symbol_part[i:]
                return f"{base.upper()}/{quote.upper()}"
        return symbol_part.upper()
    
    def _parse_ticker(self, data: Dict, symbol: Optional[str] = None) -> Dict:
        """Parse ticker data into standard format"""
        if not symbol:
            symbol = data.get('s', 'UNKNOWN')
            symbol = f"{symbol[:-4]}/{symbol[-4:]}" if len(symbol) > 4 else symbol
        
        return {
            'type': 'ticker',
            'symbol': symbol,
            'price': float(data.get('c', 0)),  # Last price
            'bid': float(data.get('b', 0)),     # Best bid
            'ask': float(data.get('a', 0)),     # Best ask
            'high': float(data.get('h', 0)),    # 24h high
            'low': float(data.get('l', 0)),     # 24h low
            'volume': float(data.get('v', 0)),  # 24h volume
            'change': float(data.get('p', 0)),  # Price change
            'change_percent': float(data.get('P', 0)),  # Price change percent
            'timestamp': data.get('E', int(time.time() * 1000))
        }


class OKXWebSocket(WebSocketClient):
    """OKX WebSocket client implementation"""
    
    def __init__(self, symbols: List[str], config: Optional[WebSocketConfig] = None):
        super().__init__('okx', symbols, config)
        self.base_url = "wss://ws.okex.com:8443/ws/v5/public"
        
    def _get_ws_url(self) -> str:
        return self.base_url
    
    def _subscribe_message(self) -> str:
        """Build OKX subscription message"""
        channels = []
        for symbol in self.symbols:
            # OKX format: BTC-USDT
            okx_symbol = symbol.replace('/', '-')
            channels.append(f"tickers:{okx_symbol}")
        
        return json.dumps({
            "op": "subscribe",
            "args": [{"channel": ch} for ch in channels]
        })
    
    def _parse_message(self, message: Dict) -> Optional[Dict]:
        """Parse OKX WebSocket message"""
        try:
            if message.get('event') == 'subscribe':
                logger.info(f"Subscribed to: {message}")
                return None
                
            if 'data' in message:
                data = message['data'][0]
                okx_symbol = data.get('instId', '')
                symbol = okx_symbol.replace('-', '/')
                
                return {
                    'type': 'ticker',
                    'symbol': symbol,
                    'price': float(data.get('last', 0)),
                    'bid': float(data.get('bidPx', 0)),
                    'ask': float(data.get('askPx', 0)),
                    'high': float(data.get('high24h', 0)),
                    'low': float(data.get('low24h', 0)),
                    'volume': float(data.get('vol24h', 0)),
                    'change': float(data.get('change24h', 0)),
                    'change_percent': float(data.get('change24hPct', 0)),
                    'timestamp': int(data.get('ts', time.time() * 1000))
                }
                
            return None
            
        except Exception as e:
            logger.error(f"Error parsing OKX message: {e}")
            return None
