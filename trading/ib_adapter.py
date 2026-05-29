"""
Interactive Brokers (IB) adapter implementing the Exchange interface.
Uses the ib_insync library to connect to TWS/IB Gateway.

Installation:
    pip install ib_insync

Prerequisites:
    - TWS (Trader Workstation) or IB Gateway running
    - API connections enabled in TWS/Gateway settings
    - Port: 7497 (paper trading) or 7496 (live) for TWS
    - Port: 4002 (paper) or 4001 (live) for IB Gateway
    - Client ID: unique integer per connection
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from .exchange import Exchange
from utils.logger import logger


class IBAdapter(Exchange):
    """
    Interactive Brokers adapter implementing the Exchange interface.
    
    Supports both paper trading (TWS/Gateway) and live trading environments.
    Provides access to stocks, ETFs, forex, futures, and options across
    multiple exchanges worldwide.
    
    Args:
        host: TWS/Gateway host (default: '127.0.0.1')
        port: TWS/Gateway port (default: 7497 for TWS paper)
        client_id: Unique client identifier (default: 1)
        account: Account number (optional, uses default if not specified)
    """

    def __init__(
        self,
        api_key: str = "",
        secret: str = "",
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        account: Optional[str] = None,
    ):
        """
        Initialize IB adapter with connection parameters.
        
        Note: api_key and secret are not used for IB API authentication;
        the connection is authorized via TWS/Gateway session.
        These parameters are accepted for interface compatibility.
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.account = account
        self._connected = False
        self._ib = None  # ib_insync.IB instance

        logger.info(
            f"IBAdapter initialized: {host}:{port} (client_id={client_id})"
        )

    # ------------------------------------------------------------------
    # Internal connection management (stub for mock/testing)
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> bool:
        """
        Ensure the adapter has a live connection to TWS/Gateway.
        
        In production, this would call ib.connect(). In this stub
        implementation, we simulate connection status.
        
        Returns:
            True if connected (or simulated as connected)
        """
        if self._connected:
            return True

        # --- Production code (commented out, requires ib_insync) ---
        # from ib_insync import IB
        # self._ib = IB()
        # try:
        #     self._ib.connect(self.host, self.port, clientId=self.client_id)
        #     self._connected = True
        #     logger.info(f"Connected to IB at {self.host}:{self.port}")
        #     return True
        # except ConnectionRefusedError:
        #     logger.error(
        #         "Cannot connect to TWS/IB Gateway. "
        #         "Ensure TWS or IB Gateway is running with API enabled."
        #     )
        #     return False

        # --- Stub: simulate connection ---
        logger.warning(
            "IBAdapter running in stub mode (no ib_insync connection). "
            "Install ib_insync and start TWS/Gateway for live trading."
        )
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from TWS/IB Gateway."""
        if self._ib is not None:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self._connected = False
        logger.info("Disconnected from IB Gateway")

    # ------------------------------------------------------------------
    # Exchange interface implementation
    # ------------------------------------------------------------------

    def get_balance(self) -> Dict[str, float]:
        """
        Get account balance.
        
        Returns:
            Dictionary mapping currency codes -> available balances.
            Includes base currency cash, buying power, and settled cash.
        """
        if not self._ensure_connected():
            return {}

        # --- Production code ---
        # account_summary = self._ib.accountSummary()
        # balance = {}
        # for entry in account_summary:
        #     if entry.tag in ('TotalCashValue', 'BuyingPower', 'SettledCash'):
        #         balance[entry.currency] = float(entry.value)
        # return balance

        # --- Stub ---
        logger.info("IBAdapter.get_balance() → stub data")
        return {
            "USD": 100000.00,
            "EUR": 50000.00,
            "GBP": 25000.00,
        }

    def get_market_data(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> List[Dict]:
        """
        Get historical market data (OHLCV).
        
        Args:
            symbol: IB contract identifier (e.g., 'AAPL', 'EUR.USD', 'ES')
            timeframe: Bar size ('1 min', '5 mins', '1 hour', '1 day')
            limit: Number of bars to fetch
            
        Returns:
            List of OHLCV dictionaries
            
        Note:
            IB uses bar size strings like '1 min', '5 mins', '1 hour',
            '1 day' instead of the standard '1m', '5m', '1h', '1d'.
        """
        if not self._ensure_connected():
            return []

        # Map standard timeframe to IB bar size
        ib_bar_size = self._map_timeframe(timeframe)

        # --- Production code ---
        # from ib_insync import Stock, Forex, Contract
        # contract = self._resolve_contract(symbol)
        # if contract is None:
        #     logger.error(f"Cannot resolve contract for {symbol}")
        #     return []
        # bars = self._ib.reqHistoricalData(
        #     contract,
        #     endDateTime='',
        #     durationStr=f'{limit} D',
        #     barSizeSetting=ib_bar_size,
        #     whatToShow='TRADES',
        #     useRTH=True,
        #     formatDate=1,
        # )
        # return [{
        #     'timestamp': int(bar.date.timestamp() * 1000),
        #     'open': float(bar.open),
        #     'high': float(bar.high),
        #     'low': float(bar.low),
        #     'close': float(bar.close),
        #     'volume': int(bar.volume),
        # } for bar in bars]

        # --- Stub ---
        logger.info(
            f"IBAdapter.get_market_data({symbol}, {timeframe}, {limit}) "
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
        Place an order via IB.
        
        Args:
            symbol: IB contract identifier
            side: 'buy' or 'sell'
            amount: Number of shares/contracts (or currency units for forex)
            price: Limit price (required for limit orders)
            order_type: 'market' or 'limit'
            
        Returns:
            Dictionary with order information
            
        Note:
            IB order types include MKT, LMT, STP, STP LMT, TRAIL,
            and many more advanced types.
        """
        if not self._ensure_connected():
            return {}

        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side: {side}")
        if order_type not in ("market", "limit"):
            raise ValueError(f"Invalid order type: {order_type}")
        if order_type == "limit" and price is None:
            raise ValueError("Price is required for limit orders")

        # --- Production code ---
        # from ib_insync import MarketOrder, LimitOrder
        # contract = self._resolve_contract(symbol)
        # if contract is None:
        #     return {}
        # 
        # if order_type == 'market':
        #     ib_order = MarketOrder(side, amount)
        # else:
        #     ib_order = LimitOrder(side, amount, price)
        # 
        # trade = self._ib.placeOrder(contract, ib_order)
        # return {
        #     'id': str(trade.order.orderId),
        #     'symbol': symbol,
        #     'side': side,
        #     'type': order_type,
        #     'amount': amount,
        #     'price': price,
        #     'filled': 0.0,
        #     'remaining': amount,
        #     'status': str(trade.orderStatus.status),
        #     'timestamp': int(time.time() * 1000),
        # }

        # --- Stub ---
        logger.info(
            f"IBAdapter.place_order({side} {amount} {symbol} "
            f"{order_type}) → stub order"
        )
        order_id = f"ib_{int(time.time() * 1000)}"
        return {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
            "price": price,
            "filled": 0.0,
            "remaining": amount,
            "status": "Submitted",
            "timestamp": int(time.time() * 1000),
        }

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: IB order ID (integer as string)
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        if not self._ensure_connected():
            return False

        # --- Production code ---
        # order_id_int = int(order_id)
        # trade = self._ib.cancelOrder(order_id_int)
        # return trade is not None and trade.orderStatus.status == 'Cancelled'

        # --- Stub ---
        logger.info(f"IBAdapter.cancel_order({order_id}) → stub: success")
        return True

    # ------------------------------------------------------------------
    # IB-specific helpers
    # ------------------------------------------------------------------

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current portfolio positions.
        
        Returns:
            List of position dictionaries with symbol, quantity,
            market price, and P&L information.
        """
        if not self._ensure_connected():
            return []

        # --- Production code ---
        # positions = self._ib.positions()
        # return [{
        #     'symbol': pos.contract.symbol,
        #     'sec_type': pos.contract.secType,
        #     'currency': pos.contract.currency,
        #     'quantity': float(pos.position),
        #     'avg_cost': float(pos.avgCost),
        #     'market_price': float(pos.marketPrice),
        #     'market_value': float(pos.marketValue),
        #     'unrealized_pnl': float(pos.unrealizedPNL),
        #     'realized_pnl': float(pos.realizedPNL),
        #     'account': pos.account,
        # } for pos in positions]

        # --- Stub ---
        logger.info("IBAdapter.get_positions() → stub data")
        return [
            {
                "symbol": "AAPL",
                "sec_type": "STK",
                "currency": "USD",
                "quantity": 100,
                "avg_cost": 175.50,
                "market_price": 182.30,
                "market_value": 18230.00,
                "unrealized_pnl": 680.00,
                "realized_pnl": 0.0,
                "account": self.account or "DU1234567",
            },
        ]

    def check_connection(self) -> bool:
        """
        Check if the IB connection is healthy.
        
        Returns:
            True if connected and responsive, False otherwise
        """
        if not self._connected:
            return False

        # --- Production code ---
        # try:
        #     self._ib.reqCurrentTime()
        #     return True
        # except Exception:
        #     return False

        # --- Stub ---
        return True

    def get_supported_symbols(self) -> List[str]:
        """
        IB supports virtually all exchange-traded symbols globally.
        This method returns a representative sample.
        
        Returns:
            List of supported symbol patterns
        """
        return [
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "TSLA",
            "EUR.USD",
            "GBP.USD",
            "USD.JPY",
            "ES",
            "NQ",
            "CL",
            "GC",
        ]

    def get_next_order_id(self) -> int:
        """
        Get the next valid order ID from TWS.
        
        Returns:
            Next order ID integer
        """
        if self._ib is not None:
            try:
                return self._ib.client.getReqId()
            except Exception:
                pass
        # Fallback: use timestamp
        return int(time.time() * 1000) % 1000000

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_timeframe(timeframe: str) -> str:
        """Map standard timeframe notation to IB bar size strings."""
        mapping = {
            "1m": "1 min",
            "5m": "5 mins",
            "15m": "15 mins",
            "30m": "30 mins",
            "1h": "1 hour",
            "4h": "4 hours",
            "1d": "1 day",
            "1w": "1 week",
        }
        return mapping.get(timeframe, timeframe)

    @staticmethod
    def _generate_stub_ohlcv(symbol: str, limit: int) -> List[Dict]:
        """Generate mock OHLCV data for testing."""
        import math

        data = []
        base_price = 100.0
        now = datetime.now()

        for i in range(limit):
            ts = int((now - timedelta(hours=(limit - i) * 1)).timestamp() * 1000)
            phase = i * 0.1
            close = base_price + 10 * math.sin(phase) + (i * 0.05)
            high = close * 1.02
            low = close * 0.98
            open_ = low + (high - low) * 0.3
            volume = int(1000 + 500 * abs(math.sin(phase)))

            data.append({
                "timestamp": ts,
                "open": round(open_, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume,
            })

        return data

    def __repr__(self) -> str:
        return (
            f"IBAdapter(host={self.host}, port={self.port}, "
            f"client_id={self.client_id}, account={self.account})"
        )