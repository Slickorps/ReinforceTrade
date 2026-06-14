"""
Trading execution system — multi-broker exchange adapters and real-time trading.

Provides:
  - **Exchange adapters**: CCXTExchange (Binance, Coinbase, etc.), IBAdapter
    (Interactive Brokers TWS/Gateway), OANDAdapter (OANDA REST API).
  - **BrokerFactory**: Unified broker adapter instantiation from config.
  - **Real-time modules**: WebSocketClient for market data streams,
    OrderManager for order lifecycle, PositionTracker for P&L tracking.
  - **Monitoring**: TradeMonitor, AlertManager, MetricsCollector,
    PerformanceTracker for trade surveillance and alerting.

Usage::

    from trading.broker_factory import create_exchange, list_supported_brokers
    from trading import CCXTExchange, IBAdapter, OANDAdapter
"""

from .exchange import Exchange
from .ccxt_exchange import CCXTExchange
from .ib_adapter import IBAdapter
from .oanda_adapter import OANDAdapter
from .broker_factory import create_exchange, list_supported_brokers
from .websocket_client import WebSocketClient, BinanceWebSocket, OKXWebSocket, WebSocketConfig
from .order_manager import OrderManager, Order, OrderStatus, OrderType, OrderSide
from .position_tracker import PositionTracker, Position, PositionStatus
from .monitor import TradeMonitor, MonitorEvent, EventType, PnLSnapshot
from .alert_channel import AlertManager, Alert, AlertSeverity, AlertChannel, ConsoleAlertChannel, FileAlertChannel
from .performance_tracker import MetricsCollector, PerformanceTracker, TradeRecord
