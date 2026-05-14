"""
Trade monitoring system for tracking trading execution status.
Listens to order status changes, position changes, and exception events.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import RLock
from collections import deque

from trading.order_manager import Order, OrderStatus, OrderManager
from trading.position_tracker import Position, PositionTracker
from utils.logger import logger


class EventType(Enum):
    """Types of events that can be monitored"""
    ORDER_CREATED = "order_created"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIALLY_FILLED = "order_partially_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_PARTIALLY_CLOSED = "position_partially_closed"
    POSITION_UPDATED = "position_updated"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"
    MAX_DRAWDOWN_EXCEEDED = "max_drawdown_exceeded"
    ERROR_OCCURRED = "error_occurred"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_INFO = "system_info"


@dataclass
class MonitorEvent:
    """Represents a monitored event with metadata"""
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # 'info', 'warning', 'error', 'critical'
    source: str = "system"
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'severity': self.severity,
            'source': self.source,
            'message': self.message
        }


@dataclass
class PnLSnapshot:
    """P&L snapshot at a point in time for tracking performance"""
    timestamp: datetime = field(default_factory=datetime.now)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    portfolio_value: float = 0.0
    active_positions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': self.total_pnl,
            'portfolio_value': self.portfolio_value,
            'active_positions': self.active_positions
        }


class TradeMonitor:
    """
    Monitors trading execution status by listening to order and position changes.

    Acts as the central event hub that:
    - Tracks order status changes and emits events
    - Records P&L snapshots at configurable intervals
    - Detects abnormal conditions (max drawdown, etc.)
    - Forwards critical events to AlertManager
    """

    def __init__(
        self,
        order_manager: Optional[OrderManager] = None,
        position_tracker: Optional[PositionTracker] = None,
        pnl_snapshot_interval: int = 60,  # seconds
        max_events_in_memory: int = 1000,
        max_drawdown_threshold: float = 0.2  # 20% max drawdown alert
    ):
        """
        Initialize TradeMonitor.

        Args:
            order_manager: OrderManager instance to monitor
            position_tracker: PositionTracker instance to monitor
            pnl_snapshot_interval: Interval (seconds) between automatic P&L snapshots
            max_events_in_memory: Maximum number of events to keep in memory
            max_drawdown_threshold: Maximum drawdown threshold before alert (0.0 - 1.0)
        """
        self.order_manager = order_manager
        self.position_tracker = position_tracker
        self.pnl_snapshot_interval = pnl_snapshot_interval
        self.max_events_in_memory = max_events_in_memory
        self.max_drawdown_threshold = max_drawdown_threshold

        # Event storage
        self._events: deque = deque(maxlen=max_events_in_memory)
        self._pnl_snapshots: deque = deque(maxlen=max_events_in_memory)
        self._alert_manager = None  # Will be set by register_alert_manager

        # Event listeners registry: {EventType: [callbacks]}
        self._listeners: Dict[EventType, List[Callable]] = {}

        # State tracking
        self._is_running: bool = False
        self._last_snapshot_time: Optional[datetime] = None
        self._peak_portfolio_value: float = 0.0
        self._current_drawdown: float = 0.0
        self._lock = RLock()

        # Error tracking
        self._error_count: int = 0
        self._consecutive_errors: int = 0
        self._max_consecutive_errors: int = 5

        # Statistics
        self._total_events: int = 0
        self._total_warnings: int = 0
        self._total_errors: int = 0
        self._total_critical: int = 0

        logger.info("TradeMonitor initialized")

    # ── Registration ──────────────────────────────────────────────

    def register_alert_manager(self, alert_manager) -> None:
        """Register AlertManager to forward critical events"""
        self._alert_manager = alert_manager
        logger.debug("AlertManager registered with TradeMonitor")

    def add_event_listener(self, event_type: EventType, callback: Callable) -> None:
        """
        Register a callback for a specific event type.

        Args:
            event_type: EventType to listen for
            callback: Callable(event: MonitorEvent) -> None
        """
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)
            logger.debug(f"Listener added for event: {event_type.value}")

    def remove_event_listener(self, event_type: EventType, callback: Callable) -> bool:
        """
        Remove a previously registered event listener.

        Args:
            event_type: EventType to stop listening for
            callback: The callback to remove

        Returns:
            True if removed successfully, False otherwise
        """
        with self._lock:
            if event_type in self._listeners and callback in self._listeners[event_type]:
                self._listeners[event_type].remove(callback)
                logger.debug(f"Listener removed for event: {event_type.value}")
                return True
            return False

    # ── Event Emission ────────────────────────────────────────────

    def _emit_event(self, event_type: EventType, data: Dict[str, Any],
                    severity: str = "info", source: str = "monitor",
                    message: str = "") -> MonitorEvent:
        """
        Create and emit a monitor event to all registered listeners.

        Args:
            event_type: Type of event
            data: Event data payload
            severity: Severity level ('info', 'warning', 'error', 'critical')
            source: Source component name
            message: Human-readable event description

        Returns:
            The created MonitorEvent
        """
        event = MonitorEvent(
            event_type=event_type,
            data=data,
            severity=severity,
            source=source,
            message=message or event_type.value
        )

        # Store event in memory
        with self._lock:
            self._events.append(event)
            self._total_events += 1

            # Track severity counts
            if severity == 'warning':
                self._total_warnings += 1
            elif severity == 'error':
                self._total_errors += 1
            elif severity == 'critical':
                self._total_critical += 1

            # Track consecutive errors
            if severity in ('error', 'critical'):
                self._consecutive_errors += 1
                self._error_count += 1
                if self._consecutive_errors >= self._max_consecutive_errors:
                    self._emit_event(
                        EventType.SYSTEM_WARNING,
                        {'consecutive_errors': self._consecutive_errors},
                        severity='warning',
                        source='monitor',
                        message=f"Too many consecutive errors ({self._consecutive_errors})"
                    )
            else:
                self._consecutive_errors = 0

        # Notify registered listeners
        with self._lock:
            listeners = list(self._listeners.get(event_type, []))

        for callback in listeners:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event listener callback failed: {e}")

        # Forward critical/warning events to AlertManager
        if self._alert_manager and severity in ('warning', 'error', 'critical'):
            try:
                self._alert_manager.handle_event(event)
            except Exception as e:
                logger.error(f"AlertManager notification failed: {e}")

        return event

    # ── Order Monitoring ──────────────────────────────────────────

    def on_order_created(self, order: Order) -> MonitorEvent:
        """
        Called when a new order is created.

        Args:
            order: The created Order object

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.ORDER_CREATED,
            data={
                'order_id': order.id,
                'symbol': order.symbol,
                'side': order.side.value,
                'order_type': order.order_type.value,
                'amount': order.amount,
                'price': order.price
            },
            severity='info',
            source='order_manager',
            message=f"Order created: {order.side.value} {order.amount} {order.symbol}"
        )

    def on_order_filled(self, order: Order) -> MonitorEvent:
        """
        Called when an order is fully filled.

        Args:
            order: The filled Order object

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.ORDER_FILLED,
            data={
                'order_id': order.id,
                'symbol': order.symbol,
                'side': order.side.value,
                'filled': order.filled,
                'price': order.price,
                'fee': order.fee,
                'exchange_id': order.exchange_id
            },
            severity='info',
            source='order_manager',
            message=f"Order filled: {order.side.value} {order.filled}/{order.amount} {order.symbol} @ {order.price}"
        )

    def on_order_partially_filled(self, order: Order) -> MonitorEvent:
        """
        Called when an order is partially filled.

        Args:
            order: The partially filled Order object

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.ORDER_PARTIALLY_FILLED,
            data={
                'order_id': order.id,
                'symbol': order.symbol,
                'side': order.side.value,
                'filled': order.filled,
                'remaining': order.remaining,
                'fill_percentage': order.fill_percentage,
                'price': order.price
            },
            severity='info',
            source='order_manager',
            message=f"Order partially filled: {order.fill_percentage:.1f}% ({order.filled}/{order.amount})"
        )

    def on_order_rejected(self, order: Order) -> MonitorEvent:
        """
        Called when an order is rejected by the exchange.

        Args:
            order: The rejected Order object

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.ORDER_REJECTED,
            data={
                'order_id': order.id,
                'symbol': order.symbol,
                'reason': order.reject_reason or 'unknown'
            },
            severity='error',
            source='order_manager',
            message=f"Order rejected: {order.id} (reason: {order.reject_reason or 'unknown'})"
        )

    def on_order_cancelled(self, order: Order) -> MonitorEvent:
        """
        Called when an order is cancelled.

        Args:
            order: The cancelled Order object

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.ORDER_CANCELLED,
            data={
                'order_id': order.id,
                'symbol': order.symbol,
                'filled': order.filled
            },
            severity='info',
            source='order_manager',
            message=f"Order cancelled: {order.id}"
        )

    def monitor_order_status_change(self, old_status: OrderStatus,
                                    new_status: OrderStatus, order: Order) -> Optional[MonitorEvent]:
        """
        Monitor and react to order status changes.

        Args:
            old_status: Previous order status
            new_status: New order status
            order: The order that changed

        Returns:
            The emitted MonitorEvent, or None if no handler for the transition
        """
        if old_status == new_status:
            return None

        # Determine event based on new status
        if new_status == OrderStatus.FILLED:
            return self.on_order_filled(order)
        elif new_status == OrderStatus.PARTIALLY_FILLED:
            return self.on_order_partially_filled(order)
        elif new_status == OrderStatus.REJECTED:
            return self.on_order_rejected(order)
        elif new_status == OrderStatus.CANCELLED:
            return self.on_order_cancelled(order)

        return None

    # ── Position Monitoring ───────────────────────────────────────

    def on_position_opened(self, position: Position) -> MonitorEvent:
        """
        Called when a new position is opened.

        Args:
            position: The opened Position object

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.POSITION_OPENED,
            data={
                'symbol': position.symbol,
                'side': position.side,
                'size': position.size,
                'entry_price': position.entry_price
            },
            severity='info',
            source='position_tracker',
            message=f"Position opened: {position.side} {position.size} {position.symbol} @ {position.entry_price}"
        )

    def on_position_closed(self, position: Position) -> MonitorEvent:
        """
        Called when a position is fully closed.

        Args:
            position: The closed Position object

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.POSITION_CLOSED,
            data={
                'symbol': position.symbol,
                'side': position.side,
                'realized_pnl': position.realized_pnl,
                'total_pnl': position.total_pnl,
                'pnl_percentage': position.pnl_percentage,
                'duration': str(position.closed_at - position.created_at) if position.closed_at else None
            },
            severity='info',
            source='position_tracker',
            message=f"Position closed: {position.symbol} PnL={position.total_pnl:.2f} ({position.pnl_percentage:.2f}%)"
        )

    def on_position_updated(self, position: Position) -> MonitorEvent:
        """
        Called when a position is updated (price change, partial close).

        Args:
            position: The updated Position object

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.POSITION_UPDATED,
            data={
                'symbol': position.symbol,
                'current_price': position.current_price,
                'unrealized_pnl': position.unrealized_pnl,
                'pnl_percentage': position.pnl_percentage,
                'size': position.size
            },
            severity='info',
            source='position_tracker',
            message=f"Position updated: {position.symbol} unrealized PnL={position.unrealized_pnl:.2f}"
        )

    def on_stop_loss_triggered(self, symbol: str, price: float,
                               position: Optional[Position] = None) -> MonitorEvent:
        """
        Called when a stop loss is triggered.

        Args:
            symbol: Trading pair symbol
            price: Price at which stop loss triggered
            position: The associated position (if available)

        Returns:
            The emitted MonitorEvent
        """
        data = {
            'symbol': symbol,
            'trigger_price': price
        }
        if position:
            data.update({
                'entry_price': position.entry_price,
                'realized_pnl': position.realized_pnl,
                'side': position.side
            })

        return self._emit_event(
            EventType.STOP_LOSS_TRIGGERED,
            data=data,
            severity='warning',
            source='risk_manager',
            message=f"Stop loss triggered for {symbol} at {price}"
        )

    def on_take_profit_triggered(self, symbol: str, price: float,
                                 position: Optional[Position] = None) -> MonitorEvent:
        """
        Called when a take profit is triggered.

        Args:
            symbol: Trading pair symbol
            price: Price at which take profit triggered
            position: The associated position (if available)

        Returns:
            The emitted MonitorEvent
        """
        data = {
            'symbol': symbol,
            'trigger_price': price
        }
        if position:
            data.update({
                'entry_price': position.entry_price,
                'realized_pnl': position.realized_pnl,
                'side': position.side
            })

        return self._emit_event(
            EventType.TAKE_PROFIT_TRIGGERED,
            data=data,
            severity='info',
            source='risk_manager',
            message=f"Take profit triggered for {symbol} at {price}"
        )

    # ── P&L Snapshot ─────────────────────────────────────────────

    def record_pnl_snapshot(self) -> Optional[PnLSnapshot]:
        """
        Record a P&L snapshot at the current time.

        Returns:
            PnLSnapshot if position_tracker available, None otherwise
        """
        if not self.position_tracker:
            return None

        try:
            portfolio = self.position_tracker.calculate_portfolio_value()

            snapshot = PnLSnapshot(
                unrealized_pnl=portfolio['total_unrealized_pnl'],
                realized_pnl=portfolio['total_realized_pnl'],
                total_pnl=portfolio['total_pnl'],
                portfolio_value=portfolio['total_position_value'],
                active_positions=portfolio['active_positions']
            )

            with self._lock:
                self._pnl_snapshots.append(snapshot)
                self._last_snapshot_time = snapshot.timestamp

                # Track peak portfolio value and drawdown
                total_pnl = portfolio['total_pnl']
                if total_pnl > self._peak_portfolio_value:
                    self._peak_portfolio_value = total_pnl

                if self._peak_portfolio_value > 0:
                    self._current_drawdown = (
                        self._peak_portfolio_value - total_pnl
                    ) / self._peak_portfolio_value

            # Check max drawdown threshold
            if self._current_drawdown >= self.max_drawdown_threshold:
                self._emit_event(
                    EventType.MAX_DRAWDOWN_EXCEEDED,
                    data={
                        'current_drawdown': self._current_drawdown,
                        'threshold': self.max_drawdown_threshold,
                        'peak_value': self._peak_portfolio_value
                    },
                    severity='critical',
                    source='monitor',
                    message=(
                        f"Max drawdown exceeded: {self._current_drawdown:.2%} "
                        f"(threshold: {self.max_drawdown_threshold:.2%})"
                    )
                )

            logger.debug(f"P&L snapshot recorded: total_pnl={snapshot.total_pnl:.2f}")
            return snapshot

        except Exception as e:
            logger.error(f"Failed to record P&L snapshot: {e}")
            return None

    def check_snapshot_due(self) -> Optional[PnLSnapshot]:
        """
        Check if a new P&L snapshot is due based on the configured interval.

        Returns:
            PnLSnapshot if recorded, None if not due yet
        """
        if not self._last_snapshot_time:
            return self.record_pnl_snapshot()

        elapsed = (datetime.now() - self._last_snapshot_time).total_seconds()
        if elapsed >= self.pnl_snapshot_interval:
            return self.record_pnl_snapshot()

        return None

    # ── Error and Warning Handling ────────────────────────────────

    def on_error_occurred(self, source: str, error: Exception,
                          context: Optional[Dict[str, Any]] = None) -> MonitorEvent:
        """
        Called when an error occurs in the trading system.

        Args:
            source: Component where the error occurred
            error: The exception that occurred
            context: Optional context data about the error

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.ERROR_OCCURRED,
            data={
                'source': source,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'context': context or {}
            },
            severity='error',
            source=source,
            message=f"Error in {source}: {type(error).__name__}: {error}"
        )

    def on_system_warning(self, message: str, data: Optional[Dict[str, Any]] = None) -> MonitorEvent:
        """
        Called for system warnings.

        Args:
            message: Warning description
            data: Optional warning data

        Returns:
            The emitted MonitorEvent
        """
        return self._emit_event(
            EventType.SYSTEM_WARNING,
            data=data or {},
            severity='warning',
            source='system',
            message=message
        )

    # ── Data Access ───────────────────────────────────────────────

    def get_recent_events(self, count: int = 10,
                          severity: Optional[str] = None) -> List[MonitorEvent]:
        """
        Get recent events, optionally filtered by severity.

        Args:
            count: Maximum number of events to return
            severity: Optional severity filter ('info', 'warning', 'error', 'critical')

        Returns:
            List of recent MonitorEvent objects
        """
        with self._lock:
            events = list(self._events)

        if severity:
            events = [e for e in events if e.severity == severity]

        return events[-count:]

    def get_recent_events_dict(self, count: int = 10,
                               severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent events as dictionaries for serialization"""
        return [e.to_dict() for e in self.get_recent_events(count, severity)]

    def get_pnl_snapshots(self, count: int = 10) -> List[PnLSnapshot]:
        """Get recent P&L snapshots"""
        with self._lock:
            snapshots = list(self._pnl_snapshots)
        return snapshots[-count:]

    def get_pnl_snapshots_dict(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent P&L snapshots as dictionaries"""
        return [s.to_dict() for s in self.get_pnl_snapshots(count)]

    def get_current_drawdown(self) -> float:
        """Get current drawdown percentage (0.0 - 1.0)"""
        with self._lock:
            return self._current_drawdown

    def get_statistics(self) -> Dict[str, Any]:
        """Get monitor statistics"""
        with self._lock:
            return {
                'total_events': self._total_events,
                'total_warnings': self._total_warnings,
                'total_errors': self._total_errors,
                'total_critical': self._total_critical,
                'error_count': self._error_count,
                'consecutive_errors': self._consecutive_errors,
                'current_drawdown': self._current_drawdown,
                'peak_portfolio_value': self._peak_portfolio_value,
                'events_in_memory': len(self._events),
                'pnl_snapshots_in_memory': len(self._pnl_snapshots),
                'last_snapshot_time': (
                    self._last_snapshot_time.isoformat() if self._last_snapshot_time else None
                )
            }

    def reset_error_counters(self) -> None:
        """Reset error tracking counters"""
        with self._lock:
            self._error_count = 0
            self._consecutive_errors = 0
        logger.info("Error counters reset")

    def clear_events(self) -> int:
        """Clear all stored events. Returns number of events cleared."""
        with self._lock:
            count = len(self._events)
            self._events.clear()
        logger.info(f"Cleared {count} events")
        return count

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (
            f"TradeMonitor(events={stats['total_events']}, "
            f"errors={stats['total_errors']}, "
            f"drawdown={stats['current_drawdown']:.2%})"
        )