"""
Unit tests for monitoring and alert management modules.
Tests TradeMonitor, AlertManager, and their data structures.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from trading.monitor import (
    TradeMonitor, MonitorEvent, EventType, PnLSnapshot
)
from trading.alert_channel import (
    AlertManager, Alert, AlertSeverity, AlertChannel,
    ConsoleAlertChannel, FileAlertChannel
)
from trading.order_manager import Order, OrderStatus, OrderType, OrderSide
from trading.position_tracker import Position, PositionStatus


# ============================================================
# MonitorEvent Tests
# ============================================================

class TestMonitorEvent:
    """Tests for MonitorEvent data class"""

    def test_default_creation(self):
        """Test creating a MonitorEvent with defaults"""
        event = MonitorEvent(event_type=EventType.ORDER_FILLED)
        assert event.event_type == EventType.ORDER_FILLED
        assert event.severity == "info"
        assert event.source == "system"
        assert event.message == ""
        assert isinstance(event.timestamp, datetime)

    def test_to_dict(self):
        """Test MonitorEvent to_dict serialization"""
        event = MonitorEvent(
            event_type=EventType.ORDER_FILLED,
            data={'order_id': '123', 'symbol': 'BTC/USDT'},
            severity='info',
            source='order_manager',
            message='Order filled: buy 1.0 BTC/USDT'
        )
        result = event.to_dict()
        assert result['event_type'] == 'order_filled'
        assert result['data']['order_id'] == '123'
        assert result['severity'] == 'info'
        assert result['source'] == 'order_manager'
        assert 'timestamp' in result


# ============================================================
# PnLSnapshot Tests
# ============================================================

class TestPnLSnapshot:
    """Tests for PnLSnapshot data class"""

    def test_default_creation(self):
        """Test creating a PnLSnapshot with defaults"""
        snapshot = PnLSnapshot()
        assert snapshot.unrealized_pnl == 0.0
        assert snapshot.realized_pnl == 0.0
        assert snapshot.total_pnl == 0.0
        assert snapshot.portfolio_value == 0.0
        assert snapshot.active_positions == 0
        assert isinstance(snapshot.timestamp, datetime)

    def test_to_dict(self):
        """Test PnLSnapshot to_dict serialization"""
        snapshot = PnLSnapshot(
            unrealized_pnl=100.0,
            realized_pnl=50.0,
            total_pnl=150.0,
            portfolio_value=10000.0,
            active_positions=2
        )
        result = snapshot.to_dict()
        assert result['unrealized_pnl'] == 100.0
        assert result['total_pnl'] == 150.0
        assert result['portfolio_value'] == 10000.0
        assert result['active_positions'] == 2


# ============================================================
# TradeMonitor Tests
# ============================================================

class TestTradeMonitor:
    """Tests for TradeMonitor class"""

    def test_initialization(self):
        """Test TradeMonitor initialization with defaults"""
        monitor = TradeMonitor()
        assert monitor.pnl_snapshot_interval == 60
        assert monitor.max_events_in_memory == 1000
        assert monitor.max_drawdown_threshold == 0.2
        stats = monitor.get_statistics()
        assert stats['total_events'] == 0
        assert stats['total_warnings'] == 0
        assert stats['total_errors'] == 0

    def test_custom_initialization(self):
        """Test TradeMonitor with custom parameters"""
        monitor = TradeMonitor(
            pnl_snapshot_interval=30,
            max_events_in_memory=100,
            max_drawdown_threshold=0.1
        )
        assert monitor.pnl_snapshot_interval == 30
        assert monitor.max_events_in_memory == 100
        assert monitor.max_drawdown_threshold == 0.1

    def test_order_created_event(self):
        """Test emitting order created event"""
        monitor = TradeMonitor()
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=50000.0
        )
        event = monitor.on_order_created(order)
        assert event.event_type == EventType.ORDER_CREATED
        assert event.data['symbol'] == 'BTC/USDT'
        assert event.data['order_id'] == 'test_1'

    def test_order_filled_event(self):
        """Test emitting order filled event"""
        monitor = TradeMonitor()
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=50000.0,
            status=OrderStatus.FILLED,
            filled=1.0,
            fee=0.001
        )
        event = monitor.on_order_filled(order)
        assert event.event_type == EventType.ORDER_FILLED
        assert event.data['filled'] == 1.0

    def test_order_rejected_event(self):
        """Test emitting order rejected event"""
        monitor = TradeMonitor()
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            status=OrderStatus.REJECTED,
            reject_reason="Insufficient funds"
        )
        event = monitor.on_order_rejected(order)
        assert event.event_type == EventType.ORDER_REJECTED
        assert event.data['reason'] == 'Insufficient funds'
        assert event.severity == 'error'

    def test_order_status_change_monitoring(self):
        """Test monitoring order status transitions"""
        monitor = TradeMonitor()
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=50000.0,
            status=OrderStatus.FILLED,
            filled=1.0
        )
        # No change should return None
        result = monitor.monitor_order_status_change(
            OrderStatus.FILLED, OrderStatus.FILLED, order
        )
        assert result is None

        # Status change should emit event
        result = monitor.monitor_order_status_change(
            OrderStatus.OPEN, OrderStatus.FILLED, order
        )
        assert result is not None
        assert result.event_type == EventType.ORDER_FILLED

    def test_position_opened_event(self):
        """Test emitting position opened event"""
        monitor = TradeMonitor()
        position = Position(
            symbol="BTC/USDT",
            side="long",
            size=1.0,
            entry_price=50000.0
        )
        event = monitor.on_position_opened(position)
        assert event.event_type == EventType.POSITION_OPENED
        assert event.data['symbol'] == 'BTC/USDT'
        assert event.data['size'] == 1.0

    def test_position_closed_event(self):
        """Test emitting position closed event"""
        monitor = TradeMonitor()
        position = Position(
            symbol="BTC/USDT",
            side="long",
            size=0.0,
            entry_price=50000.0,
            realized_pnl=1000.0,
            total_pnl=1000.0,
            status=PositionStatus.CLOSED,
            closed_at=datetime.now()
        )
        event = monitor.on_position_closed(position)
        assert event.event_type == EventType.POSITION_CLOSED
        assert event.data['realized_pnl'] == 1000.0

    def test_stop_loss_triggered(self):
        """Test stop loss triggered event"""
        monitor = TradeMonitor()
        position = Position(
            symbol="BTC/USDT",
            side="long",
            size=1.0,
            entry_price=50000.0,
            realized_pnl=-500.0
        )
        event = monitor.on_stop_loss_triggered(
            symbol="BTC/USDT",
            price=45000.0,
            position=position
        )
        assert event.event_type == EventType.STOP_LOSS_TRIGGERED
        assert event.severity == 'warning'
        assert event.data['trigger_price'] == 45000.0

    def test_take_profit_triggered(self):
        """Test take profit triggered event"""
        monitor = TradeMonitor()
        event = monitor.on_take_profit_triggered(
            symbol="BTC/USDT",
            price=55000.0
        )
        assert event.event_type == EventType.TAKE_PROFIT_TRIGGERED
        assert event.severity == 'info'

    def test_event_listener_registration(self):
        """Test adding and removing event listeners"""
        monitor = TradeMonitor()
        callback = MagicMock()

        # Add listener
        monitor.add_event_listener(EventType.ORDER_FILLED, callback)
        
        # Emit event - callback should be called
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=50000.0,
            status=OrderStatus.FILLED,
            filled=1.0
        )
        monitor.on_order_filled(order)
        callback.assert_called_once()

        # Remove listener
        result = monitor.remove_event_listener(EventType.ORDER_FILLED, callback)
        assert result is True

        # Emit again - callback should NOT be called again
        monitor.on_order_filled(order)
        callback.assert_called_once()  # Still 1

    def test_remove_nonexistent_listener(self):
        """Test removing a listener that wasn't registered"""
        monitor = TradeMonitor()
        callback = MagicMock()
        result = monitor.remove_event_listener(EventType.ORDER_FILLED, callback)
        assert result is False

    def test_pnl_snapshot_without_tracker(self):
        """Test P&L snapshot when no position tracker is set"""
        monitor = TradeMonitor()
        snapshot = monitor.record_pnl_snapshot()
        assert snapshot is None

    def test_pnl_snapshot_with_tracker(self):
        """Test P&L snapshot with a mock position tracker"""
        monitor = TradeMonitor()
        
        # Mock position tracker
        mock_tracker = MagicMock()
        mock_tracker.calculate_portfolio_value.return_value = {
            'total_unrealized_pnl': 100.0,
            'total_realized_pnl': 50.0,
            'total_pnl': 150.0,
            'total_position_value': 10000.0,
            'active_positions': 2
        }
        monitor.position_tracker = mock_tracker

        snapshot = monitor.record_pnl_snapshot()
        assert snapshot is not None
        assert snapshot.total_pnl == 150.0
        assert snapshot.portfolio_value == 10000.0
        assert snapshot.active_positions == 2

    def test_pnl_snapshot_triggers_drawdown_alert(self):
        """Test that max drawdown event is emitted when threshold exceeded"""
        monitor = TradeMonitor(max_drawdown_threshold=0.1)
        
        mock_tracker = MagicMock()
        
        # First snapshot: peak
        mock_tracker.calculate_portfolio_value.return_value = {
            'total_unrealized_pnl': 0.0,
            'total_realized_pnl': 1000.0,  # peak = 1000
            'total_pnl': 1000.0,
            'total_position_value': 10000.0,
            'active_positions': 1
        }
        monitor.position_tracker = mock_tracker
        monitor.record_pnl_snapshot()

        # Second snapshot: 20% drawdown (exceeds 10% threshold)
        mock_tracker.calculate_portfolio_value.return_value = {
            'total_unrealized_pnl': 0.0,
            'total_realized_pnl': 750.0,  # drawdown = (1000-750)/1000 = 25%
            'total_pnl': 750.0,
            'total_position_value': 9000.0,
            'active_positions': 1
        }
        
        # The record should trigger the drawdown alert
        snapshot = monitor.record_pnl_snapshot()
        assert snapshot.total_pnl == 750.0

        # Check that the drawdown event was emitted
        events = monitor.get_recent_events(severity='critical')
        assert len(events) >= 1
        assert events[-1].event_type == EventType.MAX_DRAWDOWN_EXCEEDED

    def test_check_snapshot_due(self):
        """Test checking if snapshot is due"""
        monitor = TradeMonitor(pnl_snapshot_interval=60)
        
        # Without tracker, should return None
        result = monitor.check_snapshot_due()
        assert result is None

        # With tracker but just recorded, should return None
        mock_tracker = MagicMock()
        mock_tracker.calculate_portfolio_value.return_value = {
            'total_unrealized_pnl': 0.0,
            'total_realized_pnl': 0.0,
            'total_pnl': 0.0,
            'total_position_value': 0.0,
            'active_positions': 0
        }
        monitor.position_tracker = mock_tracker

        # Force update last_snapshot_time to now
        from unittest.mock import patch as mock_patch
        with mock_patch.object(monitor, '_last_snapshot_time', datetime.now()):
            result = monitor.check_snapshot_due()
            assert result is None

    def test_error_tracking(self):
        """Test consecutive error tracking"""
        monitor = TradeMonitor(max_events_in_memory=100)
        
        # Emit multiple errors
        for i in range(6):
            monitor.on_error_occurred(
                source="test",
                error=Exception(f"Error {i}")
            )

        # Check warning was emitted after max consecutive errors
        stats = monitor.get_statistics()
        assert stats['consecutive_errors'] >= 0

    def test_reset_error_counters(self):
        """Test resetting error counters"""
        monitor = TradeMonitor()
        monitor.on_error_occurred(
            source="test",
            error=Exception("Test error")
        )
        monitor.reset_error_counters()
        stats = monitor.get_statistics()
        assert stats['consecutive_errors'] == 0

    def test_get_recent_events(self):
        """Test retrieving recent events"""
        monitor = TradeMonitor(max_events_in_memory=10)
        
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=50000.0
        )
        
        # Emit a few events
        monitor.on_order_created(order)
        monitor.on_system_warning("Test warning")
        
        events = monitor.get_recent_events(count=5)
        assert len(events) >= 2
        
        # Filter by severity
        warnings = monitor.get_recent_events(severity='warning')
        assert len(warnings) >= 1
        assert warnings[-1].severity == 'warning'

    def test_get_recent_events_dict(self):
        """Test retrieving recent events as dictionaries"""
        monitor = TradeMonitor()
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=50000.0
        )
        monitor.on_order_created(order)
        
        events_dict = monitor.get_recent_events_dict(count=5)
        assert len(events_dict) >= 1
        assert isinstance(events_dict[0], dict)
        assert 'event_type' in events_dict[0]

    def test_max_events_limit(self):
        """Test that events exceeding max_in_memory are dropped"""
        max_events = 5
        monitor = TradeMonitor(max_events_in_memory=max_events)
        
        # Emit more events than max
        for i in range(10):
            monitor.on_system_warning(f"Test warning {i}")
        
        events = monitor.get_recent_events(count=100)
        assert len(events) <= max_events

    def test_clear_events(self):
        """Test clearing all events"""
        monitor = TradeMonitor()
        monitor.on_system_warning("Test warning")
        monitor.on_error_occurred("test", Exception("Test error"))
        
        cleared = monitor.clear_events()
        assert cleared >= 2
        assert len(monitor.get_recent_events()) == 0

    def test_get_current_drawdown(self):
        """Test getting current drawdown"""
        monitor = TradeMonitor()
        assert monitor.get_current_drawdown() == 0.0

    def test_multiple_listeners_same_event(self):
        """Test multiple callbacks for the same event type"""
        monitor = TradeMonitor()
        callback1 = MagicMock()
        callback2 = MagicMock()
        
        monitor.add_event_listener(EventType.ORDER_FILLED, callback1)
        monitor.add_event_listener(EventType.ORDER_FILLED, callback2)
        
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=50000.0,
            status=OrderStatus.FILLED,
            filled=1.0
        )
        monitor.on_order_filled(order)
        
        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_listener_exception_handling(self):
        """Test that a failing listener doesn't break other listeners"""
        monitor = TradeMonitor()
        failing_callback = MagicMock(side_effect=Exception("Listener failed"))
        working_callback = MagicMock()
        
        monitor.add_event_listener(EventType.ORDER_FILLED, failing_callback)
        monitor.add_event_listener(EventType.ORDER_FILLED, working_callback)
        
        order = Order(
            id="test_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=50000.0,
            status=OrderStatus.FILLED,
            filled=1.0
        )
        # Should not raise
        monitor.on_order_filled(order)
        working_callback.assert_called_once()


# ============================================================
# Alert Tests
# ============================================================

class TestAlert:
    """Tests for Alert data class"""

    def test_default_creation(self):
        """Test creating an Alert with defaults"""
        alert = Alert(
            title="Test Alert",
            message="This is a test",
            severity=AlertSeverity.INFO
        )
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test"
        assert alert.severity == AlertSeverity.INFO
        assert alert.source == "system"
        assert isinstance(alert.timestamp, datetime)

    def test_from_monitor_event(self):
        """Test creating Alert from MonitorEvent"""
        event = MonitorEvent(
            event_type=EventType.ORDER_FILLED,
            data={'order_id': '123'},
            severity='warning',
            source='order_manager',
            message='Order filled: buy 1.0 BTC/USDT'
        )
        alert = Alert.from_monitor_event(event)
        assert alert.title == 'Order Filled'
        assert alert.message == 'Order filled: buy 1.0 BTC/USDT'
        assert alert.severity == AlertSeverity.WARNING
        assert alert.source == 'order_manager'
        assert alert.event_type == 'order_filled'

    def test_to_dict(self):
        """Test Alert to_dict serialization"""
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.ERROR,
            source="trading",
            event_type="order_rejected"
        )
        result = alert.to_dict()
        assert result['title'] == 'Test Alert'
        assert result['severity'] == 'error'
        assert result['source'] == 'trading'

    def test_format_for_console(self):
        """Test console formatting"""
        alert = Alert(
            title="Order Error",
            message="Order rejected: insufficient funds",
            severity=AlertSeverity.ERROR,
            source="order_manager"
        )
        formatted = alert.format_for_console()
        assert "[ERROR]" in formatted
        assert "Order Error" in formatted
        assert "insufficient funds" in formatted

    def test_format_for_file(self):
        """Test file formatting"""
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
            source="trading"
        )
        formatted = alert.format_for_file()
        assert "[WARNING]" in formatted
        assert "Test Alert" in formatted

    def test_format_for_webhook(self):
        """Test webhook formatting"""
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.CRITICAL,
            source="system"
        )
        result = alert.format_for_webhook()
        assert isinstance(result, dict)
        assert result['severity'] == 'critical'


# ============================================================
# ConsoleAlertChannel Tests
# ============================================================

class TestConsoleAlertChannel:
    """Tests for ConsoleAlertChannel"""

    def test_send_info_alert(self):
        """Test sending an info alert to console"""
        channel = ConsoleAlertChannel()
        alert = Alert(
            title="Info Alert",
            message="Test info",
            severity=AlertSeverity.INFO
        )
        result = channel.send_alert(alert)
        assert result is True

    def test_send_warning_alert(self):
        """Test sending a warning alert"""
        channel = ConsoleAlertChannel()
        alert = Alert(
            title="Warning Alert",
            message="Test warning",
            severity=AlertSeverity.WARNING
        )
        result = channel.send_alert(alert)
        assert result is True

    def test_send_error_alert(self):
        """Test sending an error alert"""
        channel = ConsoleAlertChannel()
        alert = Alert(
            title="Error Alert",
            message="Test error",
            severity=AlertSeverity.ERROR
        )
        result = channel.send_alert(alert)
        assert result is True

    def test_channel_enable_disable(self):
        """Test enabling and disabling channel"""
        channel = ConsoleAlertChannel(enabled=True)
        assert channel.enabled is True
        
        channel.disable()
        assert channel.enabled is False
        
        channel.enable()
        assert channel.enabled is True

    def test_channel_statistics(self):
        """Test channel statistics tracking"""
        channel = ConsoleAlertChannel()
        alert = Alert(
            title="Test Alert",
            message="Test",
            severity=AlertSeverity.INFO
        )
        
        channel.send_alert(alert)
        channel.send_alert(alert)
        
        stats = channel.get_statistics()
        assert stats['sent_count'] == 2
        assert stats['error_count'] == 0
        assert stats['name'] == 'console'

    def test_channel_name(self):
        """Test custom channel name"""
        channel = ConsoleAlertChannel(name="custom_console")
        assert channel.name == "custom_console"


# ============================================================
# FileAlertChannel Tests
# ============================================================

class TestFileAlertChannel:
    """Tests for FileAlertChannel"""

    def test_send_alert_creates_file(self, tmp_path):
        """Test that sending alert creates log file"""
        log_file = tmp_path / "alerts.log"
        channel = FileAlertChannel(file_path=str(log_file))
        
        alert = Alert(
            title="File Alert",
            message="Test file writing",
            severity=AlertSeverity.INFO
        )
        result = channel.send_alert(alert)
        assert result is True
        assert log_file.exists()

    def test_send_alert_writes_content(self, tmp_path):
        """Test that alert content is written to file"""
        log_file = tmp_path / "alerts.log"
        channel = FileAlertChannel(file_path=str(log_file))
        
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.INFO
        )
        channel.send_alert(alert)
        
        content = log_file.read_text(encoding='utf-8')
        assert "Test Alert" in content
        assert "Test message" in content
        assert "[INFO]" in content

    def test_append_to_existing_file(self, tmp_path):
        """Test appending to an existing log file"""
        log_file = tmp_path / "alerts.log"
        log_file.write_text("", encoding='utf-8')
        
        channel = FileAlertChannel(file_path=str(log_file))
        
        alert1 = Alert(title="Alert 1", message="First", severity=AlertSeverity.INFO)
        alert2 = Alert(title="Alert 2", message="Second", severity=AlertSeverity.WARNING)
        
        channel.send_alert(alert1)
        channel.send_alert(alert2)
        
        lines = log_file.read_text(encoding='utf-8').strip().split('\n')
        assert len(lines) == 2

    def test_multiple_alerts(self, tmp_path):
        """Test sending multiple alerts"""
        log_file = tmp_path / "alerts.log"
        channel = FileAlertChannel(file_path=str(log_file))
        
        for i in range(5):
            alert = Alert(
                title=f"Alert {i}",
                message=f"Message {i}",
                severity=AlertSeverity.INFO
            )
            channel.send_alert(alert)
        
        with open(str(log_file), 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 5


# ============================================================
# AlertManager Tests
# ============================================================

class TestAlertManager:
    """Tests for AlertManager class"""

    def test_initialization(self):
        """Test AlertManager initialization"""
        mgr = AlertManager()
        stats = mgr.get_statistics()
        assert stats['total_alerts'] == 0
        assert stats['active_channels'] == 0

    def test_add_and_remove_channel(self):
        """Test adding and removing alert channels"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test_channel")
        
        mgr.add_channel(channel)
        assert mgr.get_channel("test_channel") is channel
        
        result = mgr.remove_channel("test_channel")
        assert result is True
        assert mgr.get_channel("test_channel") is None

    def test_remove_nonexistent_channel(self):
        """Test removing a channel that doesn't exist"""
        mgr = AlertManager()
        result = mgr.remove_channel("nonexistent")
        assert result is False

    def test_enable_disable_channel(self):
        """Test enabling and disabling channels"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        assert mgr.disable_channel("test") is True
        assert channel.enabled is False
        
        assert mgr.enable_channel("test") is True
        assert channel.enabled is True

    def test_send_alert_to_multiple_channels(self):
        """Test sending alert to multiple channels"""
        mgr = AlertManager()
        ch1 = ConsoleAlertChannel(name="ch1")
        ch2 = ConsoleAlertChannel(name="ch2")
        mgr.add_channel(ch1)
        mgr.add_channel(ch2)
        
        alert = Alert(
            title="Multi Channel",
            message="Test",
            severity=AlertSeverity.INFO
        )
        
        sent = mgr.send_alert(alert)
        assert sent == 2

    def test_send_alert_with_disabled_channels(self):
        """Test that disabled channels don't receive alerts"""
        mgr = AlertManager()
        ch1 = ConsoleAlertChannel(name="enabled")
        ch2 = ConsoleAlertChannel(name="disabled", enabled=False)
        mgr.add_channel(ch1)
        mgr.add_channel(ch2)
        
        alert = Alert(
            title="Selective",
            message="Test",
            severity=AlertSeverity.INFO
        )
        
        sent = mgr.send_alert(alert)
        assert sent == 1

    def test_handle_event(self):
        """Test handling a MonitorEvent"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        event = MonitorEvent(
            event_type=EventType.ORDER_FILLED,
            data={'order_id': '123'},
            severity='warning',
            source='order_manager',
            message='Order filled'
        )
        
        sent = mgr.handle_event(event)
        assert sent == 1

    def test_severity_shortcuts(self):
        """Test severity-specific alert methods"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        assert mgr.alert_info("Info", "Test") == 1
        assert mgr.alert_warning("Warning", "Test") == 1
        assert mgr.alert_error("Error", "Test") == 1
        assert mgr.alert_critical("Critical", "Test") == 1

    def test_alert_history(self):
        """Test alert history tracking"""
        mgr = AlertManager(max_alert_history=10)
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        for i in range(5):
            mgr.alert_info(f"Alert {i}", f"Message {i}")
        
        history = mgr.get_alert_history(count=10)
        assert len(history) == 5

    def test_alert_history_filter_by_severity(self):
        """Test filtering alert history by severity"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        mgr.alert_info("Info", "Test")
        mgr.alert_error("Error", "Test")
        mgr.alert_warning("Warning", "Test")
        
        errors = mgr.get_alert_history(count=10, severity='error')
        assert len(errors) == 1
        assert errors[0].severity == AlertSeverity.ERROR

    def test_alert_history_max_limit(self):
        """Test alert history max limit"""
        max_history = 3
        mgr = AlertManager(max_alert_history=max_history)
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        for i in range(10):
            mgr.alert_info(f"Alert {i}", f"Message {i}")
        
        history = mgr.get_alert_history(count=100)
        assert len(history) <= max_history

    def test_alert_history_as_dict(self):
        """Test retrieving alert history as dictionaries"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        mgr.alert_info("Test", "Message")
        
        history_dict = mgr.get_alert_history_dict(count=10)
        assert len(history_dict) >= 1
        assert isinstance(history_dict[0], dict)
        assert 'title' in history_dict[0]

    def test_clear_history(self):
        """Test clearing alert history"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        mgr.alert_info("Test", "Message")
        cleared = mgr.clear_history()
        assert cleared >= 1
        
        history = mgr.get_alert_history()
        assert len(history) == 0

    def test_statistics_tracking(self):
        """Test alert statistics are tracked correctly"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        
        mgr.alert_info("Info", "Info message")
        mgr.alert_warning("Warning", "Warning message")
        mgr.alert_error("Error", "Error message")
        mgr.alert_critical("Critical", "Critical message")
        
        stats = mgr.get_statistics()
        assert stats['total_alerts'] == 4
        assert stats['total_sent'] >= 4
        assert stats['severity_counts']['info'] == 1
        assert stats['severity_counts']['warning'] == 1
        assert stats['severity_counts']['error'] == 1
        assert stats['severity_counts']['critical'] == 1

    def test_integration_monitor_to_alert(self):
        """Full integration: TradeMonitor emits event -> AlertManager dispatches alert"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="console")
        mgr.add_channel(channel)
        
        monitor = TradeMonitor()
        monitor.register_alert_manager(mgr)
        
        # Emit an error event (severity='error' -> forwarded to AlertManager)
        error = ValueError("API connection timeout")
        monitor.on_error_occurred(source="exchange", error=error)
        
        # Verify alert was dispatched
        alert_history = mgr.get_alert_history()
        assert len(alert_history) >= 1
        assert alert_history[-1].title == 'Error Occurred'
        assert alert_history[-1].event_type == 'error_occurred'

    def test_repr(self):
        """Test string representation"""
        mgr = AlertManager()
        channel = ConsoleAlertChannel(name="test")
        mgr.add_channel(channel)
        mgr.alert_info("Test", "Message")
        
        repr_str = repr(mgr)
        assert "AlertManager" in repr_str
        assert "alerts=1" in repr_str or "alerts = 1" in repr_str


if __name__ == "__main__":
    pytest.main(["-v", __file__])