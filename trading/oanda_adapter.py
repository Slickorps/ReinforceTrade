"""
OANDA adapter implementing the Exchange interface.
Uses the oandapyV20 library to connect to OANDA's REST API for forex trading.

Installation:
    pip install oandapyV20

Prerequisites:
    - OANDA practice (demo) or live account
    - API token from OANDA (https://www.oanda.com/demo-account/)
    - Account ID from OANDA account settings
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import math

from .exchange import Exchange
from utils.logger import logger


class OANDAdapter(Exchange):
    """
    OANDA adapter implementing the Exchange interface.
    
    Supports both practice (demo) and live trading environments for forex,
    metals, and CFDs trading.
    
    Args:
        api_key: OANDA API token (bearer token)
        secret: Not used for OANDA (accepts for interface compatibility)
        environment: 'practice' (default) or 'live'
        account_id: OANDA account ID (e.g., '101-001-1234567-001')
    """

    def __init__(
        self,
        api_key: str,
        secret: str = "",
        environment: str = "practice",
        account_id: Optional[str] = None,
    ):
        """
        Initialize OANDA adapter.
        
        Args:
            api_key: OANDA API token
            secret: Not used (interface compatibility)
            environment: 'practice' (demo) or 'live'
            account_id: OANDA account ID
        """
        self.api_key = api_key
        self.environment = environment
        self.account_id = account_id
        self._connected = False
        self._api = None  # oandapyV20.API instance

        # API endpoints
        if environment == "practice":
            self.api_url = "https://api-fxpractice.oanda.com"
        else:
            self.api_url = "https://api-fxtrade.oanda.com"

        logger.info(
            f"OANDAdapter initialized: {environment} environment "
            f"(account={account_id})"
        )

    # ------------------------------------------------------------------
    # Internal connection management (stub for mock/testing)
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> bool:
        """
        Ensure the adapter has a live connection to OANDA API.
        
        In production, this would initialize the oandapyV20 API client.
        
        Returns:
            True if connection is available
        """
        if self._connected:
            return True

        # --- Production code (commented out, requires oandapyV20) ---
        # import oandapyV20
        # if not self.api_key:
        #     logger.error("OANDA API key is required")
        #     return False
        # self._api = oandapyV20.API(
        #     access_token=self.api_key,
        #     environment=self.environment,
        # )
        # self._connected = True
        # return True

        # --- Stub: simulate connection ---
        if not self.api_key:
            logger.warning(
                "OANDA API key not provided. "
                "Stub mode will return mock data."
            )
        else:
            logger.info(
                "OANDA adapter ready (stub mode). "
                "Install oandapyV20 for live trading."
            )
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from OANDA API."""
        self._api = None
        self._connected = False
        logger.info("Disconnected from OANDA API")

    # ------------------------------------------------------------------
    # Exchange interface implementation
    # ------------------------------------------------------------------

    def get_balance(self) -> Dict[str, float]:
        """
        Get account balance from OANDA.
        
        Returns:
            Dictionary with account currency -> available balance.
            OANDA typically uses a single base currency account.
        """
        if not self._ensure_connected():
            return {}

        # --- Production code ---
        # from oandapyV20.endpoints.accounts import AccountSummary
        # if not self.account_id:
        #     logger.error("Account ID required for OANDA")
        #     return {}
        # 
        # params = {"accountID": self.account_id}
        # request = AccountSummary(self.account_id)
        # response = self._api.request(request)
        # account = response.get('account', {})
        # 
        # return {
        #     account.get('currency', 'USD'): float(account.get('balance', 0)),
        # }

        # --- Stub ---
        logger.info("OANDAdapter.get_balance() → stub data")
        return {"USD": 50000.00}

    def get_market_data(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> List[Dict]:
        """
        Get historical OHLCV data from OANDA.
        
        Args:
            symbol: OANDA instrument name (e.g., 'EUR_USD', 'GBP_JPY')
            timeframe: Granularity ('M1', 'M5', 'M15', 'M30',
                       'H1', 'H4', 'D')
            limit: Number of candles to fetch (max 5000)
            
        Returns:
            List of OHLCV dictionaries
            
        Note:
            OANDA uses instrument names with underscore separator
            (e.g., 'EUR_USD' not 'EUR/USD') and different granularity
            strings than standard timeframe notation.
        """
        if not self._ensure_connected():
            return []

        # Map standard timeframe to OANDA granularity
        oanda_granularity = self._map_timeframe(timeframe)

        # --- Production code ---
        # from oandapyV20.endpoints.instruments import InstrumentCandles
        # 
        # params = {
        #     "granularity": oanda_granularity,
        #     "count": limit,
        #     "price": "M",  # Midpoint candles
        # }
        # 
        # request = InstrumentCandles(symbol, params=params)
        # response = self._api.request(request)
        # 
        # candles = response.get('candles', [])
        # return [{
        #     'timestamp': int(
        #         datetime.fromisoformat(c['time'].replace('Z', '+00:00'))
        #         .timestamp() * 1000
        #     ),
        #     'open': float(c['mid']['o']),
        #     'high': float(c['mid']['h']),
        #     'low': float(c['mid']['l']),
        #     'close': float(c['mid']['c']),
        #     'volume': int(c['volume']),
        #     'complete': c.get('complete', True),
        # } for c in candles]

        # --- Stub ---
        logger.info(
            f"OANDAdapter.get_market_data({symbol}, {timeframe}, {limit}) "
            "→ stub data"
        )
        return self._generate_stub_ohlcv(symbol, limit)

    def place_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> Dict[str, Any]:
        """
        Place a forex trade order via OANDA.
        
        Args:
            symbol: OANDA instrument (e.g., 'EUR_USD')
            side: 'buy' or 'sell' (maps to 'long'/'short')
            amount: Trade size in units (e.g., 1000 for micro lot)
            price: Price for limit orders
            order_type: 'market' or 'limit'
            
        Returns:
            Dictionary with order/trade information
            
        Note:
            OANDA distinguishes between Orders (unfilled) and Trades
            (filled). Market orders immediately become trades.
        """
        if not self._ensure_connected():
            return {}

        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side: {side}")
        if order_type not in ("market", "limit"):
            raise ValueError(f"Invalid order type: {order_type}")
        if order_type == "limit" and price is None:
            raise ValueError("Price is required for limit orders")

        oanda_side = "buy" if side == "buy" else "sell"

        # --- Production code ---
        # import oandapyV20.endpoints.orders as orders
        # 
        # order_data = {
        #     "order": {
        #         "type": "MARKET" if order_type == "market" else "LIMIT",
        #         "instrument": symbol,
        #         "units": str(amount) if oanda_side == "buy" else str(-amount),
        #         "timeInForce": "FOK" if order_type == "market" else "GTC",
        #     }
        # }
        # 
        # if order_type == "limit" and price is not None:
        #     order_data["order"]["price"] = str(price)
        # 
        # request = orders.OrderCreate(self.account_id, data=order_data)
        # response = self._api.request(request)
        # 
        # # Handle order fill or creation
        # order_fill = response.get('orderFillTransaction', {})
        # return {
        #     'id': order_fill.get('id', ''),
        #     'symbol': symbol,
        #     'side': side,
        #     'type': order_type,
        #     'amount': amount,
        #     'price': float(order_fill.get('price', price or 0)),
        #     'filled': amount if order_type == 'market' else 0,
        #     'remaining': 0 if order_type == 'market' else amount,
        #     'status': 'FILLED' if order_type == 'market' else 'PENDING',
        #     'timestamp': int(time.time() * 1000),
        # }

        # --- Stub ---
        logger.info(
            f"OANDAdapter.place_order({side} {amount} {symbol} "
            f"{order_type}) → stub order"
        )
        order_id = f"oanda_{int(time.time() * 1000)}"
        return {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
            "price": price,
            "filled": 0.0 if order_type == "limit" else amount,
            "remaining": amount,
            "status": "FILLED" if order_type == "market" else "PENDING",
            "timestamp": int(time.time() * 1000),
        }

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: OANDA order ID
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        if not self._ensure_connected():
            return False

        # --- Production code ---
        # from oandapyV20.endpoints.orders import OrderCancel
        # 
        # request = OrderCancel(self.account_id, order_id)
        # try:
        #     self._api.request(request)
        #     logger.info(f"OANDA order {order_id} cancelled")
        #     return True
        # except Exception as e:
        #     logger.error(f"Failed to cancel OANDA order {order_id}: {e}")
        #     return False

        # --- Stub ---
        logger.info(f"OANDAdapter.cancel_order({order_id}) → stub: success")
        return True

    # ------------------------------------------------------------------
    # OANDA-specific helpers
    # ------------------------------------------------------------------

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """
        Get all open trades/positions.
        
        Returns:
            List of open trade dictionaries with instrument, units,
            price, and P&L information.
        """
        if not self._ensure_connected():
            return []

        # --- Production code ---
        # from oandapyV20.endpoints.trades import OpenTrades
        # 
        # request = OpenTrades(self.account_id)
        # response = self._api.request(request)
        # 
        # trades = response.get('trades', [])
        # return [{
        #     'id': t['id'],
        #     'instrument': t['instrument'],
        #     'units': int(t['currentUnits']),
        #     'side': 'buy' if int(t['currentUnits']) > 0 else 'sell',
        #     'open_time': t['openTime'],
        #     'price': float(t['price']),
        #     'unrealized_pnl': float(t.get('unrealizedPL', 0)),
        #     'financing': float(t.get('financing', 0)),
        # } for t in trades]

        # --- Stub ---
        logger.info("OANDAdapter.get_open_trades() → stub data")
        return [
            {
                "id": "12345",
                "instrument": "EUR_USD",
                "units": 10000,
                "side": "buy",
                "open_time": datetime.now().isoformat(),
                "price": 1.08750,
                "unrealized_pnl": 45.20,
                "financing": -0.85,
            },
        ]

    def get_instrument_details(self, instrument: str) -> Dict[str, Any]:
        """
        Get instrument details including pip location, minimum trade size,
        and margin rate.
        
        Args:
            instrument: OANDA instrument name
            
        Returns:
            Instrument details dictionary
        """
        if not self._ensure_connected():
            return {}

        # --- Production code ---
        # from oandapyV20.endpoints.instruments import InstrumentCandles
        # from oandapyV20.endpoints.accounts import AccountInstruments
        # 
        # request = AccountInstruments(self.account_id)
        # response = self._api.request(request)
        # 
        # for instr in response.get('instruments', []):
        #     if instr['name'] == instrument:
        #         return {
        #             'name': instr['name'],
        #             'type': instr['type'],
        #             'display_name': instr['displayName'],
        #             'pip_location': instr['pipLocation'],
        #             'minimum_trade_size': instr['minimumTradeSize'],
        #             'margin_rate': float(instr['marginRate']),
        #         }
        # return {}

        # --- Stub ---
        logger.info(
            f"OANDAdapter.get_instrument_details({instrument}) → stub data"
        )
        return {
            "name": instrument,
            "type": "CURRENCY",
            "display_name": instrument.replace("_", "/"),
            "pip_location": -4,
            "minimum_trade_size": 1,
            "margin_rate": 0.02,
        }

    def check_connection(self) -> bool:
        """
        Check OANDA API connection health.
        
        Returns:
            True if connected, False otherwise
        """
        if not self._connected:
            return False

        # --- Production code ---
        # from oandapyV20.endpoints.accounts import AccountSummary
        # try:
        #     request = AccountSummary(self.account_id)
        #     self._api.request(request)
        #     return True
        # except Exception:
        #     return False

        # --- Stub ---
        return True

    def get_supported_symbols(self) -> List[str]:
        """
        Get list of supported forex instruments.
        
        Returns:
            List of OANDA instrument names
        """
        return [
            "EUR_USD",
            "GBP_USD",
            "USD_JPY",
            "USD_CHF",
            "AUD_USD",
            "USD_CAD",
            "NZD_USD",
            "EUR_JPY",
            "GBP_JPY",
            "EUR_GBP",
            "XAU_USD",  # Gold
            "XAG_USD",  # Silver
            "BTC_USD",  # Bitcoin
            "DE30_EUR",  # Germany 30
            "UK100_GBP",  # UK 100
            "US30_USD",  # US Wall Street 30
            "SPX500_USD",  # US SPX 500
            "NAS100_USD",  # US Tech 100
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_timeframe(timeframe: str) -> str:
        """Map standard timeframe notation to OANDA granularity."""
        mapping = {
            "1m": "M1",
            "5m": "M5",
            "15m": "M15",
            "30m": "M30",
            "1h": "H1",
            "4h": "H4",
            "1d": "D",
            "1w": "W",
        }
        return mapping.get(timeframe, timeframe)

    @staticmethod
    def _generate_stub_ohlcv(symbol: str, limit: int) -> List[Dict]:
        """Generate mock OHLCV data for testing."""
        data = []
        base_price = 1.0800 if "USD" in symbol else 150.00
        now = datetime.now()

        for i in range(limit):
            ts = int(
                (now - timedelta(hours=(limit - i) * 1)).timestamp() * 1000
            )
            phase = i * 0.15
            close = base_price + 0.02 * math.sin(phase) + (i * 0.0001)
            high = close * 1.001
            low = close * 0.999
            open_ = low + (high - low) * 0.3
            volume = int(10000 + 5000 * abs(math.sin(phase)))

            data.append({
                "timestamp": ts,
                "open": round(open_, 5),
                "high": round(high, 5),
                "low": round(low, 5),
                "close": round(close, 5),
                "volume": volume,
            })

        return data

    def __repr__(self) -> str:
        return (
            f"OANDAdapter(environment={self.environment}, "
            f"account_id={self.account_id})"
        )