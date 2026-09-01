import ccxt
import time
from typing import Dict, Any, List, Optional
from .exchange import Exchange
from utils.logger import logger


class CCXTExchange(Exchange):
    """
    CCXT-based exchange implementation for cryptocurrency trading.
    Supports major exchanges like Binance, OKX, KuCoin, etc.
    """
    
    def __init__(self, api_key: str, secret: str, exchange_name: str = 'binance', sandbox: bool = True):
        """
        Initialize CCXT exchange connection.
        
        Args:
            api_key: Exchange API key
            secret: Exchange API secret
            exchange_name: Name of exchange (binance, okx, kucoin, etc.)
            sandbox: Use testnet/sandbox mode (recommended for development)
        """
        self.exchange_name = exchange_name
        self.sandbox = sandbox
        
        # Initialize CCXT exchange
        try:
            exchange_class = getattr(ccxt, exchange_name)
            self.exchange = exchange_class({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
                'sandbox': sandbox,
                'options': {
                    'defaultType': 'spot',  # Spot trading
                }
            })
            
            # Test connection
            self.exchange.load_markets()
            logger.info(f"Connected to {exchange_name} {'sandbox' if sandbox else 'live'}")
            
        except Exception as e:
            logger.error(f"Failed to initialize {exchange_name}: {e}")
            raise
    
    def get_balance(self) -> Dict[str, float]:
        """
        Get account balance for all assets.
        
        Returns:
            Dictionary with asset symbols as keys and balances as values
        """
        try:
            balance = self.exchange.fetch_balance()
            
            # Format balance to simple dict
            formatted_balance = {}
            for currency, info in balance['free'].items():
                amount = float(info)
                if amount > 0:  # Only include non-zero balances
                    formatted_balance[currency] = amount
            
            logger.debug(f"Retrieved balance: {formatted_balance}")
            return formatted_balance
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get current ticker information for a symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            
        Returns:
            Dictionary with ticker information including price, volume, etc.
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            
            formatted_ticker = {
                'symbol': symbol,
                'price': float(ticker['last']),
                'bid': float(ticker['bid']),
                'ask': float(ticker['ask']),
                'high': float(ticker['high']),
                'low': float(ticker['low']),
                'volume': float(ticker['baseVolume']),
                'change': float(ticker.get('change', 0)),
                'change_percent': float(ticker.get('percentage', 0)),
                'timestamp': ticker['timestamp']
            }
            
            logger.debug(f"Ticker for {symbol}: {formatted_ticker['price']}")
            return formatted_ticker
            
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")
            return {}
    
    def place_order(self, symbol: str, side: str, amount: float, 
                   price: float = None, order_type: str = 'market') -> Dict[str, Any]:
        """
        Place a trading order.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Amount to trade
            price: Price for limit orders (ignored for market orders)
            order_type: 'market' or 'limit'
            
        Returns:
            Dictionary with order information
        """
        try:
            # Validate parameters
            if side not in ['buy', 'sell']:
                raise ValueError(f"Invalid side: {side}")
            
            if order_type not in ['market', 'limit']:
                raise ValueError(f"Invalid order type: {order_type}")
            
            if order_type == 'limit' and price is None:
                raise ValueError("Price is required for limit orders")
            
            # Check balance
            if side == 'buy':
                # For buy orders, check quote currency balance
                quote_currency = symbol.split('/')[1]
                
                # For market orders, estimate order cost using current price
                if price is None:
                    ticker = self.get_ticker(symbol)
                    price = ticker.get('price')
                
                required_balance = amount * (price or 0)
                balance = self.get_balance()
                available_balance = balance.get(quote_currency, 0)
                
                if available_balance < required_balance:
                    raise ValueError(f"Insufficient {quote_currency} balance")
            
            else:
                # For sell orders, check base currency balance
                base_currency = symbol.split('/')[0]
                balance = self.get_balance()
                available_balance = balance.get(base_currency, 0)
                
                if available_balance < amount:
                    raise ValueError(f"Insufficient {base_currency} balance")
            
            # Place order
            logger.info(f"Placing {order_type} {side} order for {amount} {symbol}")
            
            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price
            )
            
            formatted_order = {
                'id': order['id'],
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'amount': float(order['amount']),
                'price': float(order['price']) if order['price'] else None,
                'filled': float(order.get('filled', 0)),
                'remaining': float(order.get('remaining', order['amount'])),
                'status': order['status'],
                'timestamp': order['timestamp']
            }
            
            logger.info(f"Order placed successfully: {formatted_order['id']}")
            return formatted_order
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        try:
            logger.info(f"Cancelling order {order_id}")
            
            result = self.exchange.cancel_order(order_id)
            
            if result['status'] == 'canceled':
                logger.info(f"Order {order_id} cancelled successfully")
                return True
            else:
                logger.warning(f"Order {order_id} cancellation status: {result['status']}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status and details of an order.
        
        Args:
            order_id: ID of order to check
            
        Returns:
            Dictionary with order information
        """
        try:
            order = self.exchange.fetch_order(order_id)
            
            formatted_order = {
                'id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'type': order['type'],
                'amount': float(order['amount']),
                'price': float(order['price']) if order['price'] else None,
                'filled': float(order.get('filled', 0)),
                'remaining': float(order.get('remaining', order['amount'])),
                'status': order['status'],
                'fee': order.get('fee', {}),
                'timestamp': order['timestamp']
            }
            
            logger.debug(f"Order {order_id} status: {formatted_order['status']}")
            return formatted_order
            
        except Exception as e:
            logger.error(f"Failed to get order status for {order_id}: {e}")
            return {}
    
    def get_market_data(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict]:
        """
        Get OHLCV market data for analysis.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to fetch
            
        Returns:
            List of OHLCV dictionaries
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            formatted_data = []
            for candle in ohlcv:
                formatted_data.append({
                    'timestamp': candle[0],
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                })
            
            logger.debug(f"Fetched {len(formatted_data)} candles for {symbol}")
            return formatted_data
            
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            return []
    
    def get_trading_fees(self) -> Dict[str, float]:
        """
        Get trading fees for the exchange.
        
        Returns:
            Dictionary with fee information
        """
        try:
            fees = self.exchange.fetch_trading_fees()
            
            formatted_fees = {
                'trading': {
                    'maker': float(fees['trading']['maker']),
                    'taker': float(fees['trading']['taker'])
                },
                'funding': {
                    'withdraw': fees.get('funding', {}).get('withdraw', {}),
                    'deposit': fees.get('funding', {}).get('deposit', {})
                }
            }
            
            logger.debug(f"Trading fees: {formatted_fees}")
            return formatted_fees
            
        except Exception as e:
            logger.error(f"Failed to get trading fees: {e}")
            return {}
    
    def check_connection(self) -> bool:
        """
        Check if exchange connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            # Try to fetch server time
            server_time = self.exchange.fetch_time()
            current_time = int(time.time() * 1000)
            
            # Check if time difference is reasonable (within 5 seconds)
            time_diff = abs(server_time - current_time)
            
            if time_diff > 5000:  # 5 seconds
                logger.warning(f"Large time difference: {time_diff}ms")
                return False
            
            logger.debug("Exchange connection healthy")
            return True
            
        except Exception as e:
            logger.error(f"Exchange connection check failed: {e}")
            return False
    
    def get_supported_symbols(self) -> List[str]:
        """
        Get list of supported trading symbols.
        
        Returns:
            List of supported symbols
        """
        try:
            symbols = list(self.exchange.symbols)
            logger.debug(f"Supported symbols: {len(symbols)}")
            return symbols
            
        except Exception as e:
            logger.error(f"Failed to get supported symbols: {e}")
            return []
    
    def __repr__(self) -> str:
        return f"CCXTExchange({self.exchange_name}, sandbox={self.sandbox})"
