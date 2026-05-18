"""Unit tests for trading/performance_tracker.py"""
import math
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from trading.performance_tracker import (
    TradeRecord, MetricsCollector, PerformanceTracker
)
from trading.monitor import MonitorEvent, EventType
from trading.position_tracker import Position, PositionTracker, PositionStatus


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_position():
    """Create a sample Position for testing."""
    return Position(
        symbol="BTC/USDT",
        side="long",
        size=0.1,
        entry_price=50000.0,
        current_price=51000.0,
        unrealized_pnl=100.0,
        realized_pnl=0.0,
        total_pnl=100.0,
        status=PositionStatus.OPEN,
        created_at=datetime.now() - timedelta(hours=1)
    )


@pytest.fixture
def mock_position_tracker():
    """Create a mock PositionTracker."""
    tracker = Mock(spec=PositionTracker)
    tracker.calculate_portfolio_value.return_value = {
        'total_unrealized_pnl': 200.0,
        'total_realized_pnl': 150.0,
        'total_pnl': 350.0,
        'total_position_value': 10000.0,
        'active_positions': 2,
        'closed_positions': 5
    }
    tracker.get_position.return_value = Position(
        symbol="BTC/USDT",
        side="long",
        size=0.1,
        entry_price=50000.0,
        created_at=datetime.now() - timedelta(hours=2)
    )
    return tracker


@pytest.fixture
def mock_trade_monitor():
    """Create a mock TradeMonitor."""
    monitor = Mock()
    return monitor


# ──────────────────────────────────────────────────────────────────────
# TradeRecord Tests
# ──────────────────────────────────────────────────────────────────────

class TestTradeRecord:
    """Tests for TradeRecord dataclass."""

    def test_holding_duration(self):
        """Test holding_duration calculates correctly."""
        entry = datetime(2026, 1, 1, 10, 0, 0)
        exit_time = datetime(2026, 1, 1, 12, 30, 0)
        trade = TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000.0, exit_price=51000.0,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=entry, exit_time=exit_time
        )
        assert trade.holding_duration == timedelta(hours=2, minutes=30)

    def test_is_winning_positive(self):
        """Test is_winning when PnL > 0."""
        trade = TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000.0, exit_price=51000.0,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        )
        assert trade.is_winning is True

    def test_is_winning_negative(self):
        """Test is_winning when PnL < 0."""
        trade = TradeRecord(
            symbol="ETH/USDT", side="long",
            entry_price=3000.0, exit_price=2800.0,
            size=1.0, pnl=-200.0, pnl_percentage=-6.67,
            entry_time=datetime.now(), exit_time=datetime.now()
        )
        assert trade.is_winning is False

    def test_is_winning_zero(self):
        """Test is_winning when PnL == 0."""
        trade = TradeRecord(
            symbol="ADA/USDT", side="long",
            entry_price=1.0, exit_price=1.0,
            size=100.0, pnl=0.0, pnl_percentage=0.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        )
        assert trade.is_winning is False  # strictly > 0

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        entry = datetime(2026, 5, 1, 10, 0, 0)
        exit_time = datetime(2026, 5, 1, 14, 0, 0)
        trade = TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000.0, exit_price=51000.0,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=entry, exit_time=exit_time,
            fees=1.5, slippage=0.001
        )
        d = trade.to_dict()
        assert d['symbol'] == "BTC/USDT"
        assert d['side'] == "long"
        assert d['entry_price'] == 50000.0
        assert d['exit_price'] == 51000.0
        assert d['pnl'] == 100.0
        assert d['holding_duration_seconds'] == 4 * 3600  # 4 hours
        assert d['fees'] == 1.5
        assert d['slippage'] == 0.001
        assert d['is_winning'] is True


# ──────────────────────────────────────────────────────────────────────
# MetricsCollector Tests
# ──────────────────────────────────────────────────────────────────────

class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_initialization_defaults(self):
        """Test default initialization."""
        collector = MetricsCollector()
        assert collector.get_win_rate() == 0.0
        assert collector.get_profit_factor() == 0.0
        assert collector.get_sharpe_ratio() == 0.0
        assert collector.get_max_drawdown() == 0.0

    def test_initialization_with_dependencies(self, mock_trade_monitor, mock_position_tracker):
        """Test initialization with TradeMonitor and PositionTracker."""
        collector = MetricsCollector(
            trade_monitor=mock_trade_monitor,
            position_tracker=mock_position_tracker
        )
        assert collector.trade_monitor == mock_trade_monitor
        assert collector.position_tracker == mock_position_tracker

    def test_record_trade(self):
        """Test manual trade recording."""
        collector = MetricsCollector()
        trade = TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000.0, exit_price=51000.0,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now()
        )
        collector.record_trade(trade)
        assert len(collector._completed_trades) == 1
        assert collector._total_realized_pnl == 100.0

    def test_win_rate_all_wins(self):
        """Test win rate when all trades are winning."""
        collector = MetricsCollector()
        for i in range(5):
            collector.record_trade(TradeRecord(
                symbol="BTC/USDT", side="long",
                entry_price=50000, exit_price=51000,
                size=0.1, pnl=100.0, pnl_percentage=2.0,
                entry_time=datetime.now() - timedelta(hours=i+1),
                exit_time=datetime.now()
            ))
        assert collector.get_win_rate() == 100.0

    def test_win_rate_mixed(self):
        """Test win rate with mixed winning/losing trades."""
        collector = MetricsCollector()
        # 6 wins, 4 losses
        for _ in range(6):
            collector.record_trade(TradeRecord(
                symbol="BTC/USDT", side="long",
                entry_price=50000, exit_price=51000,
                size=0.1, pnl=100.0, pnl_percentage=2.0,
                entry_time=datetime.now(), exit_time=datetime.now()
            ))
        for _ in range(4):
            collector.record_trade(TradeRecord(
                symbol="ETH/USDT", side="short",
                entry_price=3000, exit_price=3100,
                size=1.0, pnl=-100.0, pnl_percentage=-3.3,
                entry_time=datetime.now(), exit_time=datetime.now()
            ))
        assert collector.get_win_rate() == 60.0

    def test_profit_factor_balanced(self):
        """Test profit factor with equal wins and losses."""
        collector = MetricsCollector()
        # Win: +200, Loss: -100
        collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=52000,
            size=0.1, pnl=200.0, pnl_percentage=4.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        collector.record_trade(TradeRecord(
            symbol="ETH/USDT", side="short",
            entry_price=3000, exit_price=3100,
            size=1.0, pnl=-100.0, pnl_percentage=-3.3,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        assert collector.get_profit_factor() == 2.0

    def test_profit_factor_only_wins(self):
        """Test profit factor when there are no losses."""
        collector = MetricsCollector()
        collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        assert collector.get_profit_factor() == float('inf')

    def test_profit_factor_only_losses(self):
        """Test profit factor when there are only losses."""
        collector = MetricsCollector()
        collector.record_trade(TradeRecord(
            symbol="ETH/USDT", side="long",
            entry_price=3000, exit_price=2900,
            size=1.0, pnl=-100.0, pnl_percentage=-3.3,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        assert collector.get_profit_factor() == 0.0

    def test_average_win_and_loss(self):
        """Test average win and average loss calculations."""
        collector = MetricsCollector()
        collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            size=0.1, pnl=300.0, pnl_percentage=6.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        collector.record_trade(TradeRecord(
            symbol="ETH/USDT", side="long",
            entry_price=3000, exit_price=3100,
            size=1.0, pnl=100.0, pnl_percentage=3.3,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        collector.record_trade(TradeRecord(
            symbol="ADA/USDT", side="short",
            entry_price=1.0, exit_price=1.1,
            size=1000, pnl=-100.0, pnl_percentage=-10.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        assert collector.get_average_win() == 200.0  # (300+100)/2
        assert collector.get_average_loss() == 100.0  # | -100 |

    def test_expectancy(self):
        """Test expectancy calculation."""
        collector = MetricsCollector()
        # 10 wins of +100 each, 10 losses of -50 each
        for _ in range(10):
            collector.record_trade(TradeRecord(
                symbol="BTC/USDT", side="long",
                entry_price=50000, exit_price=51000,
                size=0.1, pnl=100.0, pnl_percentage=2.0,
                entry_time=datetime.now(), exit_time=datetime.now()
            ))
            collector.record_trade(TradeRecord(
                symbol="ETH/USDT", side="short",
                entry_price=3000, exit_price=3050,
                size=1.0, pnl=-50.0, pnl_percentage=-1.67,
                entry_time=datetime.now(), exit_time=datetime.now()
            ))
        # win_rate=50%, avg_win=100, avg_loss=50
        # E = 0.5*100 - 0.5*50 = 50 - 25 = 25
        assert collector.get_expectancy() == pytest.approx(25.0)

    def test_max_drawdown_tracked(self):
        """Test max drawdown tracking via PnL snapshots."""
        collector = MetricsCollector()
        # Starting value 10000
        collector.record_pnl_snapshot(pnl=0, portfolio_value=10000)

        # Rise to 12000
        collector.record_pnl_snapshot(pnl=2000, portfolio_value=12000)

        # Drop to 9000 (drawdown = (12000-9000)/12000 = 25%)
        collector.record_pnl_snapshot(pnl=-1000, portfolio_value=9000)

        # Rise back to 11000
        collector.record_pnl_snapshot(pnl=1000, portfolio_value=11000)

        assert collector.get_max_drawdown() == pytest.approx(0.25, rel=0.01)

    def test_max_drawdown_no_data(self):
        """Test max drawdown with no data returns 0."""
        collector = MetricsCollector()
        assert collector.get_max_drawdown() == 0.0

    def test_sharpe_ratio_basic(self):
        """Test Sharpe ratio calculation with simple data."""
        collector = MetricsCollector(
            risk_free_rate=0.0  # Simplify for testing
        )
        # Steady growth: PnL grows from 0 to 250
        for i in range(50):
            collector.record_pnl_snapshot(
                pnl=i * 5, portfolio_value=10000 + i * 5
            )
        # Should get a reasonable Sharpe ratio
        sharpe = collector.get_sharpe_ratio(annualize=True)
        assert sharpe > 0  # Should be positive for steady growth

    def test_sharpe_ratio_insufficient_data(self):
        """Test Sharpe ratio returns 0 with insufficient data."""
        collector = MetricsCollector()
        collector.record_pnl_snapshot(pnl=0, portfolio_value=10000)
        assert collector.get_sharpe_ratio() == 0.0

    def test_sortino_ratio(self):
        """Test Sortino ratio calculation."""
        collector = MetricsCollector(risk_free_rate=0.0)
        # Simulate fluctuating PnL with both up and down movements
        values = [10000, 10200, 10100, 10300, 10250, 10500, 10400, 10600,
                  10500, 10700, 10650, 10800, 10700, 10900, 10850, 11000,
                  10900, 11100, 11050, 11200, 11100, 11300, 11250, 11400,
                  11300, 11500, 11450, 11600, 11500, 11700]
        for portfolio_value in values:
            collector.record_pnl_snapshot(
                pnl=portfolio_value - 10000,
                portfolio_value=portfolio_value
            )
        sortino = collector.get_sortino_ratio(annualize=True)
        assert sortino > 0

    def test_slippage_recording(self):
        """Test slippage recording and retrieval."""
        collector = MetricsCollector()
        collector.record_slippage(0.001)
        collector.record_slippage(0.002)
        collector.record_slippage(0.003)
        assert collector.get_average_slippage() == pytest.approx(0.002)
        assert collector.get_max_slippage() == 0.003

    def test_slippage_no_data(self):
        """Test slippage with no data returns 0."""
        collector = MetricsCollector()
        assert collector.get_average_slippage() == 0.0
        assert collector.get_max_slippage() == 0.0

    def test_get_summary(self):
        """Test get_summary returns complete dictionary."""
        collector = MetricsCollector()
        collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        collector.record_pnl_snapshot(pnl=100, portfolio_value=10100)

        summary = collector.get_summary()
        assert 'win_rate' in summary
        assert 'profit_factor' in summary
        assert 'sharpe_ratio' in summary
        assert 'sortino_ratio' in summary
        assert 'max_drawdown' in summary
        assert 'total_trades' in summary
        assert 'winning_trades' in summary
        assert 'losing_trades' in summary
        assert summary['total_trades'] == 1
        assert summary['winning_trades'] == 1

    def test_get_completed_trades(self):
        """Test get_completed_trades returns correct number."""
        collector = MetricsCollector()
        for _ in range(10):
            collector.record_trade(TradeRecord(
                symbol="BTC/USDT", side="long",
                entry_price=50000, exit_price=51000,
                size=0.1, pnl=100.0, pnl_percentage=2.0,
                entry_time=datetime.now(), exit_time=datetime.now()
            ))
        trades = collector.get_completed_trades(5)
        assert len(trades) == 5

    def test_get_completed_trades_dict(self):
        """Test get_completed_trades_dict returns list of dicts."""
        collector = MetricsCollector()
        collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        trades = collector.get_completed_trades_dict()
        assert len(trades) == 1
        assert isinstance(trades[0], dict)
        assert trades[0]['symbol'] == "BTC/USDT"

    def test_reset(self):
        """Test reset clears all data."""
        collector = MetricsCollector()
        collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now(), exit_time=datetime.now()
        ))
        collector.record_pnl_snapshot(pnl=100, portfolio_value=10100)
        collector.record_slippage(0.001)

        collector.reset()
        assert len(collector._completed_trades) == 0
        assert len(collector._pnl_series) == 0
        assert len(collector._slippage_samples) == 0
        assert collector._total_realized_pnl == 0.0
        assert collector.get_max_drawdown() == 0.0

    def test_event_handler_position_closed(self):
        """Test _on_position_closed captures trade from event."""
        collector = MetricsCollector(
            position_tracker=Mock(spec=PositionTracker)
        )
        collector.position_tracker.get_position.return_value = Position(
            symbol="BTC/USDT", side="long", size=0.1,
            entry_price=48000.0,
            created_at=datetime.now() - timedelta(hours=1)
        )

        event = MonitorEvent(
            event_type=EventType.POSITION_CLOSED,
            timestamp=datetime.now(),
            data={
                'symbol': 'BTC/USDT',
                'side': 'long',
                'realized_pnl': 150.0,
                'pnl_percentage': 3.0,
                'size': 0.1,
                'entry_price': 48000.0,
                'exit_price': 49500.0,
                'fees': 1.0
            }
        )
        collector._on_position_closed(event)
        assert len(collector._completed_trades) == 1
        assert collector._total_realized_pnl == 150.0

    def test_event_handler_order_filled_slippage(self):
        """Test _on_order_filled tracks slippage."""
        collector = MetricsCollector()
        event = MonitorEvent(
            event_type=EventType.ORDER_FILLED,
            data={
                'price': 50100.0,
                'expected_price': 50000.0
            }
        )
        collector._on_order_filled(event)
        # Slippage = |50100 - 50000| / 50000 = 0.002
        assert len(collector._slippage_samples) == 1
        assert collector._slippage_samples[0] == pytest.approx(0.002)

    def test_get_calmar_ratio(self):
        """Test Calmar ratio calculation."""
        collector = MetricsCollector()
        now = datetime.now()
        collector.record_pnl_snapshot(
            pnl=0, portfolio_value=10000, timestamp=now
        )
        # Simulate 90 days: growth → drawdown → recovery
        portfolio_values = [10000]
        # Days 1-30: steady growth to 13000
        for i in range(1, 31):
            portfolio_values.append(10000 + i * 100)
        # Days 31-45: drawdown to 11000
        for i in range(31, 46):
            portfolio_values.append(13000 - (i - 30) * 133.3)
        # Days 46-90: recovery to 14000
        for i in range(46, 91):
            portfolio_values.append(11000 + (i - 45) * 68.2)

        for i, pv in enumerate(portfolio_values):
            collector.record_pnl_snapshot(
                pnl=pv - 10000, portfolio_value=pv,
                timestamp=now + timedelta(days=i)
            )
        # Should have positive Calmar ratio
        calmar = collector.get_calmar_ratio()
        assert calmar > 0


# ──────────────────────────────────────────────────────────────────────
# PerformanceTracker Tests
# ──────────────────────────────────────────────────────────────────────

class TestPerformanceTracker:
    """Tests for PerformanceTracker class."""

    def test_initialization(self, mock_trade_monitor, mock_position_tracker):
        """Test basic initialization."""
        tracker = PerformanceTracker(
            trade_monitor=mock_trade_monitor,
            position_tracker=mock_position_tracker,
            snapshot_interval_seconds=30
        )
        assert tracker.trade_monitor == mock_trade_monitor
        assert tracker.position_tracker == mock_position_tracker
        assert tracker.snapshot_interval_seconds == 30
        assert tracker._running is False

    def test_start_stop(self, mock_trade_monitor, mock_position_tracker):
        """Test start and stop lifecycle."""
        tracker = PerformanceTracker(
            trade_monitor=mock_trade_monitor,
            position_tracker=mock_position_tracker
        )
        tracker.start()
        assert tracker._running is True
        tracker.stop()
        assert tracker._running is False

    def test_record_snapshot(self, mock_position_tracker):
        """Test manual snapshot recording."""
        tracker = PerformanceTracker(
            position_tracker=mock_position_tracker
        )
        tracker.record_snapshot()
        mock_position_tracker.calculate_portfolio_value.assert_called_once()

    def test_record_snapshot_no_position_tracker(self):
        """Test snapshot recording without PositionTracker returns early."""
        tracker = PerformanceTracker()
        tracker.record_snapshot()  # Should not raise

    def test_tick_records_snapshot(self, mock_position_tracker):
        """Test tick method records snapshot at intervals."""
        tracker = PerformanceTracker(
            position_tracker=mock_position_tracker,
            snapshot_interval_seconds=60
        )
        tracker.start()

        # First tick should record
        tracker.tick(timestamp=datetime.now())
        mock_position_tracker.calculate_portfolio_value.assert_called_once()

        # Reset mock
        mock_position_tracker.calculate_portfolio_value.reset_mock()

        # Second tick immediately — should skip (interval not elapsed)
        tracker.tick(timestamp=datetime.now())
        mock_position_tracker.calculate_portfolio_value.assert_not_called()

    def test_tick_not_running(self, mock_position_tracker):
        """Test tick does nothing when not running."""
        tracker = PerformanceTracker(
            position_tracker=mock_position_tracker
        )
        tracker.tick(timestamp=datetime.now())
        mock_position_tracker.calculate_portfolio_value.assert_not_called()

    def test_trade_frequency_recording(self):
        """Test trade frequency tracking."""
        tracker = PerformanceTracker()
        # Record trades at various hours
        for hour in [9, 9, 9, 14, 14]:
            ts = datetime(2026, 5, 1, hour, 0, 0)
            tracker.record_trade_time(ts)

        assert tracker.get_trades_per_hour() == 5.0 / 24.0
        assert tracker.get_most_active_hour() == 9
        dist = tracker.get_hourly_distribution()
        assert dist[9] == 3
        assert dist[14] == 2

    def test_trades_per_day(self):
        """Test trades per day calculation."""
        tracker = PerformanceTracker()
        today = datetime.now()
        # Record 10 trades today
        for _ in range(10):
            tracker.record_trade_time(today)
        assert tracker.get_trades_per_day(days=1) == pytest.approx(10.0)

    def test_most_active_hour_no_data(self):
        """Test most_active_hour returns None with no data."""
        tracker = PerformanceTracker()
        assert tracker.get_most_active_hour() is None

    def test_slippage_summary(self):
        """Test slippage summary returns correct structure."""
        tracker = PerformanceTracker()
        tracker.collector.record_slippage(0.001)
        tracker.collector.record_slippage(0.003)

        summary = tracker.get_slippage_summary()
        assert summary['average_slippage'] == pytest.approx(0.002)
        assert summary['max_slippage'] == 0.003
        assert summary['slippage_samples'] == 2

    def test_get_performance_summary(self, mock_position_tracker):
        """Test comprehensive performance summary."""
        tracker = PerformanceTracker(
            position_tracker=mock_position_tracker
        )
        tracker.record_snapshot()
        tracker.collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now()
        ))

        summary = tracker.get_performance_summary()
        assert summary['total_trades'] == 1
        assert summary['winning_trades'] == 1
        assert 'unrealized_pnl' in summary
        assert 'realized_pnl' in summary
        assert 'total_pnl' in summary
        assert 'trades_per_day' in summary
        assert 'trades_per_hour' in summary
        assert 'average_slippage_percent' in summary
        assert 'tracking_active' in summary

    def test_get_simple_report(self, mock_position_tracker):
        """Test simple report string generation."""
        tracker = PerformanceTracker(
            position_tracker=mock_position_tracker
        )
        tracker.collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now()
        ))
        report = tracker.get_simple_report()
        assert "Performance Report" in report
        assert "Total Trades" in report
        assert "Win Rate" in report
        assert "Sharpe Ratio" in report

    def test_reset(self, mock_position_tracker):
        """Test PerformanceTracker.reset clears all data."""
        tracker = PerformanceTracker(
            position_tracker=mock_position_tracker
        )
        tracker.record_snapshot()
        tracker.collector.record_trade(TradeRecord(
            symbol="BTC/USDT", side="long",
            entry_price=50000, exit_price=51000,
            size=0.1, pnl=100.0, pnl_percentage=2.0,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now()
        ))
        tracker.record_trade_time(datetime.now())

        tracker.reset()
        assert len(tracker.collector._completed_trades) == 0
        assert tracker._daily_trade_counts == {}
        assert tracker._hourly_trade_counts == {}

    def test_trades_per_day_no_data(self):
        """Test trades_per_day with no data returns 0."""
        tracker = PerformanceTracker()
        assert tracker.get_trades_per_day() == 0.0

    def test_calmar_ratio_default(self, mock_position_tracker):
        """Test Calmar ratio defaults to 0 with no series data."""
        tracker = PerformanceTracker(
            position_tracker=mock_position_tracker
        )
        assert tracker.collector.get_calmar_ratio() == 0.0


# ──────────────────────────────────────────────────────────────────────
# Edge Case Tests
# ──────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_empty_collector_all_metrics(self):
        """Test all metrics return 0/None with no data."""
        collector = MetricsCollector()
        assert collector.get_win_rate() == 0.0
        assert collector.get_profit_factor() == 0.0
        assert collector.get_average_win() == 0.0
        assert collector.get_average_loss() == 0.0
        assert collector.get_expectancy() == 0.0
        assert collector.get_sharpe_ratio() == 0.0
        assert collector.get_sortino_ratio() == 0.0
        assert collector.get_max_drawdown() == 0.0
        assert collector.get_calmar_ratio() == 0.0
        assert collector.get_average_slippage() == 0.0
        assert collector.get_max_slippage() == 0.0

    def test_zero_portfolio_value_drawdown(self):
        """Test drawdown handles zero portfolio value gracefully."""
        collector = MetricsCollector()
        collector.record_pnl_snapshot(pnl=0, portfolio_value=0)
        collector.record_pnl_snapshot(pnl=0, portfolio_value=0)
        # Should not divide by zero
        assert collector.get_max_drawdown() == 0.0

    def test_sharpe_zero_std(self):
        """Test Sharpe ratio returns 0 when stdev is 0."""
        collector = MetricsCollector(risk_free_rate=0.0)
        # All same values => std = 0
        for _ in range(10):
            collector.record_pnl_snapshot(pnl=100, portfolio_value=10000)
        assert collector.get_sharpe_ratio() == 0.0

    def test_trade_record_repr(self):
        """Test repr strings are informative."""
        collector = MetricsCollector()
        repr_str = repr(collector)
        assert "MetricsCollector" in repr_str
        assert "trades=0" in repr_str

        tracker = PerformanceTracker()
        repr_str = repr(tracker)
        assert "PerformanceTracker" in repr_str
        assert "running=False" in repr_str

    def test_max_trade_history_enforced(self):
        """Test max_trade_history limits the deque."""
        collector = MetricsCollector(max_trade_history=3)
        for i in range(5):
            collector.record_trade(TradeRecord(
                symbol="BTC/USDT", side="long",
                entry_price=50000, exit_price=51000 + i * 100,
                size=0.1, pnl=100.0, pnl_percentage=2.0,
                entry_time=datetime.now(), exit_time=datetime.now()
            ))
        # Only last 3 trades should be kept
        assert len(collector._completed_trades) == 3
        assert collector.get_completed_trades(10).__len__() == 3