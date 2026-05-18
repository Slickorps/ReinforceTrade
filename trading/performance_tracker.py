"""
Performance tracking system for real-time trading metrics collection and analysis.

Provides:
- MetricsCollector: Collects win rate, profit factor, Sharpe ratio, max drawdown
- PerformanceTracker: Real-time P&L, trade frequency, slippage analysis

Designed to integrate with TradeMonitor event system and PositionTracker data.
"""
from typing import Dict, Any, List, Optional, Tuple, Deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from statistics import mean, stdev
import math

from trading.order_manager import Order, OrderStatus
from trading.position_tracker import Position, PositionTracker
from trading.monitor import TradeMonitor, EventType, MonitorEvent, PnLSnapshot
from utils.logger import logger


# ──────────────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    """A completed trade record for performance analysis."""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_percentage: float
    entry_time: datetime
    exit_time: datetime
    fees: float = 0.0
    slippage: float = 0.0  # Expected vs actual execution price difference
    trade_id: str = ""

    @property
    def holding_duration(self) -> timedelta:
        """Calculate holding duration of this trade."""
        return self.exit_time - self.entry_time

    @property
    def is_winning(self) -> bool:
        """Whether this trade was profitable."""
        return self.pnl > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'size': self.size,
            'pnl': self.pnl,
            'pnl_percentage': self.pnl_percentage,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'holding_duration_seconds': self.holding_duration.total_seconds(),
            'fees': self.fees,
            'slippage': self.slippage,
            'is_winning': self.is_winning,
            'trade_id': self.trade_id
        }


# ──────────────────────────────────────────────────────────────────────
# MetricsCollector
# ──────────────────────────────────────────────────────────────────────

class MetricsCollector:
    """
    Collects and calculates key trading performance metrics.

    Tracks:
    - Win rate (percentage of winning trades)
    - Profit factor (gross profit / gross loss)
    - Average win / average loss
    - Max drawdown (real-time from PnL snapshots)
    - Sharpe ratio (rolling window calculation)
    - Calmar ratio (annualized return / max drawdown)

    Integrates with TradeMonitor events via add_event_listener().
    """

    def __init__(
        self,
        trade_monitor: Optional[TradeMonitor] = None,
        position_tracker: Optional[PositionTracker] = None,
        max_trade_history: int = 10000,
        sharpe_rolling_window: int = 252,  # Number of data points (~1 year daily)
        risk_free_rate: float = 0.02  # 2% annual risk-free rate
    ):
        """
        Initialize MetricsCollector.

        Args:
            trade_monitor: TradeMonitor instance for event-driven data collection
            position_tracker: PositionTracker instance for portfolio valuation
            max_trade_history: Maximum number of completed trades to store
            sharpe_rolling_window: Rolling window size for Sharpe ratio calculation
            risk_free_rate: Annual risk-free rate (0.02 = 2%) for Sharpe ratio
        """
        self.position_tracker = position_tracker
        self.trade_monitor = trade_monitor
        self.max_trade_history = max_trade_history
        self.sharpe_rolling_window = sharpe_rolling_window
        self.risk_free_rate = risk_free_rate

        # Trade history
        self._completed_trades: Deque[TradeRecord] = deque(maxlen=max_trade_history)

        # PnL time series for Sharpe and drawdown calculations
        self._pnl_series: Deque[float] = deque(maxlen=sharpe_rolling_window * 2)
        self._portfolio_value_series: Deque[Tuple[datetime, float]] = deque(
            maxlen=sharpe_rolling_window * 2
        )

        # Cumulative statistics
        self._total_realized_pnl: float = 0.0
        self._total_fees: float = 0.0
        self._peak_portfolio_value: float = 0.0
        self._trough_after_peak: float = float('inf')
        self._current_drawdown: float = 0.0
        self._max_drawdown: float = 0.0
        self._start_time: Optional[datetime] = None

        # Slippage tracking
        self._slippage_samples: Deque[float] = deque(maxlen=1000)

        # Trade timing for frequency analysis
        self._trade_timestamps: Deque[datetime] = deque(maxlen=10000)

        # Register with TradeMonitor if provided
        if self.trade_monitor:
            self.register_monitor_listeners()

        logger.info("MetricsCollector initialized")
        logger.debug(
            f"sharpe_rolling_window={sharpe_rolling_window}, "
            f"max_trade_history={max_trade_history}, "
            f"risk_free_rate={risk_free_rate}"
        )

    # ── Event Registration ──────────────────────────────────────────

    def register_monitor_listeners(self) -> None:
        """Register event listeners with TradeMonitor."""
        if not self.trade_monitor:
            logger.warning("No TradeMonitor set, skipping listener registration")
            return

        self.trade_monitor.add_event_listener(
            EventType.POSITION_CLOSED, self._on_position_closed
        )
        self.trade_monitor.add_event_listener(
            EventType.POSITION_OPENED, self._on_position_opened
        )
        self.trade_monitor.add_event_listener(
            EventType.ORDER_FILLED, self._on_order_filled
        )
        logger.debug("MetricsCollector registered with TradeMonitor")

    def unregister_monitor_listeners(self) -> None:
        """Unregister event listeners from TradeMonitor."""
        if not self.trade_monitor:
            return
        self.trade_monitor.remove_event_listener(
            EventType.POSITION_CLOSED, self._on_position_closed
        )
        self.trade_monitor.remove_event_listener(
            EventType.POSITION_OPENED, self._on_position_opened
        )
        self.trade_monitor.remove_event_listener(
            EventType.ORDER_FILLED, self._on_order_filled
        )

    # ── Event Handlers ──────────────────────────────────────────────

    def _on_position_closed(self, event: MonitorEvent) -> None:
        """Handle position closed event — record completed trade."""
        data = event.data
        symbol = data.get('symbol', 'unknown')

        # Record trade timestamp
        self._trade_timestamps.append(event.timestamp)
        if self._start_time is None:
            self._start_time = event.timestamp

        # Create trade record
        entry_price = self._get_entry_price_from_event(symbol, data)
        trade_record = TradeRecord(
            symbol=symbol,
            side=data.get('side', 'unknown'),
            entry_price=entry_price,
            exit_price=data.get('exit_price', 0.0),
            size=data.get('size', 0.0),
            pnl=data.get('realized_pnl', 0.0),
            pnl_percentage=data.get('pnl_percentage', 0.0),
            entry_time=self._get_entry_time_for_symbol(symbol) or event.timestamp,
            exit_time=event.timestamp,
            fees=data.get('fees', 0.0),
            slippage=data.get('slippage', 0.0),
            trade_id=data.get('order_id', '')
        )

        self._completed_trades.append(trade_record)
        self._total_realized_pnl += trade_record.pnl
        self._total_fees += trade_record.fees

        logger.debug(f"Trade recorded: {symbol} PnL={trade_record.pnl:.2f}")

    def _on_position_opened(self, event: MonitorEvent) -> None:
        """Handle position opened event."""
        if self._start_time is None:
            self._start_time = event.timestamp
        logger.debug(f"Position opened: {event.data.get('symbol', 'unknown')}")

    def _on_order_filled(self, event: MonitorEvent) -> None:
        """Handle order filled event — track slippage if limit order."""
        data = event.data
        actual_price = data.get('price', 0.0)
        expected_price = data.get('expected_price')
        if expected_price and expected_price > 0:
            slippage = abs(actual_price - expected_price) / expected_price
            self._slippage_samples.append(slippage)

    def _get_entry_price_from_event(self, symbol: str,
                                     event_data: Dict[str, Any]) -> float:
        """Extract entry price from event data or PositionTracker."""
        # Try from event data first
        if 'entry_price' in event_data:
            return event_data['entry_price']

        # Fall back to PositionTracker
        if self.position_tracker:
            position = self.position_tracker.get_position(symbol)
            if position:
                return position.entry_price

        return 0.0

    def _get_entry_time_for_symbol(self, symbol: str) -> Optional[datetime]:
        """Get entry time for a symbol from PositionTracker."""
        if self.position_tracker:
            position = self.position_tracker.get_position(symbol)
            if position:
                return position.created_at
        return None

    # ── Data Recording ──────────────────────────────────────────────

    def record_pnl_snapshot(self, pnl: float, portfolio_value: float,
                            timestamp: Optional[datetime] = None) -> None:
        """
        Record a P&L snapshot for drawdown and Sharpe ratio calculation.

        Call this periodically (e.g., every minute or per bar close).

        Args:
            pnl: Current total P&L
            portfolio_value: Current portfolio value
            timestamp: Snapshot timestamp (defaults to now)
        """
        ts = timestamp or datetime.now()

        # Track drawdown
        if portfolio_value > self._peak_portfolio_value:
            self._peak_portfolio_value = portfolio_value
            self._trough_after_peak = portfolio_value

        if portfolio_value < self._trough_after_peak:
            self._trough_after_peak = portfolio_value

        if self._peak_portfolio_value > 0:
            self._current_drawdown = (
                self._peak_portfolio_value - portfolio_value
            ) / self._peak_portfolio_value

        if self._current_drawdown > self._max_drawdown:
            self._max_drawdown = self._current_drawdown

        # Record for time series
        self._pnl_series.append(pnl)
        self._portfolio_value_series.append((ts, portfolio_value))

    def record_trade(self, trade: TradeRecord) -> None:
        """
        Manually record a completed trade.

        Args:
            trade: Completed trade record
        """
        self._completed_trades.append(trade)
        self._total_realized_pnl += trade.pnl
        self._total_fees += trade.fees
        self._trade_timestamps.append(trade.exit_time)
        if self._start_time is None:
            self._start_time = trade.entry_time

    def record_slippage(self, slippage: float) -> None:
        """
        Record a slippage sample.

        Args:
            slippage: Slippage as a decimal (e.g., 0.001 = 0.1%)
        """
        self._slippage_samples.append(slippage)

    # ── Metric Calculations ─────────────────────────────────────────

    def get_win_rate(self) -> float:
        """
        Calculate win rate as percentage.

        Returns:
            Win rate percentage (0.0 - 100.0)
        """
        total = len(self._completed_trades)
        if total == 0:
            return 0.0
        wins = sum(1 for t in self._completed_trades if t.is_winning)
        return (wins / total) * 100.0

    def get_profit_factor(self) -> float:
        """
        Calculate profit factor (gross profit / gross loss).

        Returns:
            Profit factor, or float('inf') if no losses
        """
        gross_profit = 0.0
        gross_loss = 0.0

        for trade in self._completed_trades:
            if trade.pnl > 0:
                gross_profit += trade.pnl
            elif trade.pnl < 0:
                gross_loss += abs(trade.pnl)

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    def get_average_win(self) -> float:
        """Calculate average profit of winning trades."""
        wins = [t.pnl for t in self._completed_trades if t.pnl > 0]
        if not wins:
            return 0.0
        return mean(wins)

    def get_average_loss(self) -> float:
        """Calculate average loss of losing trades (returns positive value)."""
        losses = [abs(t.pnl) for t in self._completed_trades if t.pnl < 0]
        if not losses:
            return 0.0
        return mean(losses)

    def get_expectancy(self) -> float:
        """
        Calculate trade expectancy.
        E = (win_rate * avg_win) - (loss_rate * avg_loss)

        Returns:
            Expected return per trade
        """
        if not self._completed_trades:
            return 0.0
        win_rate = self.get_win_rate() / 100.0
        avg_win = self.get_average_win()
        avg_loss = self.get_average_loss()
        return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    def get_sharpe_ratio(self, annualize: bool = True) -> float:
        """
        Calculate Sharpe ratio from P&L series.

        Args:
            annualize: If True, annualize the Sharpe ratio

        Returns:
            Sharpe ratio, or 0.0 if not enough data
        """
        if len(self._pnl_series) < 2:
            return 0.0

        # Calculate returns from P&L series
        returns = []
        pnl_list = list(self._pnl_series)
        for i in range(1, len(pnl_list)):
            prev_pnl = pnl_list[i - 1]
            curr_pnl = pnl_list[i]
            if abs(prev_pnl) < 1e-9:
                continue
            ret = (curr_pnl - prev_pnl) / abs(prev_pnl)
            returns.append(ret)

        if len(returns) < 2:
            return 0.0

        try:
            avg_return = mean(returns)
            std_return = stdev(returns)
            if std_return == 0:
                return 0.0

            daily_rf_rate = self.risk_free_rate / 365
            sharpe = (avg_return - daily_rf_rate) / std_return

            if annualize:
                sharpe *= math.sqrt(252)

            return sharpe
        except Exception:
            return 0.0

    def get_sortino_ratio(self, annualize: bool = True) -> float:
        """
        Calculate Sortino ratio using only downside deviation.

        Args:
            annualize: If True, annualize the ratio

        Returns:
            Sortino ratio, or 0.0 if not enough data
        """
        if len(self._pnl_series) < 2:
            return 0.0

        returns = []
        pnl_list = list(self._pnl_series)
        for i in range(1, len(pnl_list)):
            prev_pnl = pnl_list[i - 1]
            curr_pnl = pnl_list[i]
            if abs(prev_pnl) < 1e-9:
                continue
            ret = (curr_pnl - prev_pnl) / abs(prev_pnl)
            returns.append(ret)

        if len(returns) < 2:
            return 0.0

        try:
            avg_return = mean(returns)
            daily_rf_rate = self.risk_free_rate / 365

            # Downside deviation (only returns below risk-free rate)
            downside = [min(r - daily_rf_rate, 0) for r in returns]
            sum_sq = sum(d * d for d in downside)
            downside_dev = math.sqrt(sum_sq / len(downside)) if downside else 0.0

            if downside_dev == 0:
                return 0.0

            sortino = (avg_return - daily_rf_rate) / downside_dev

            if annualize:
                sortino *= math.sqrt(252)

            return sortino
        except Exception:
            return 0.0

    def get_max_drawdown(self) -> float:
        """
        Get maximum drawdown from tracked P&L series.

        Returns:
            Max drawdown as a decimal (0.05 = 5%)
        """
        # Use internal tracked max drawdown if available
        if self._max_drawdown > 0:
            return self._max_drawdown

        # Calculate from portfolio value series if no tracked value
        if len(self._portfolio_value_series) < 2:
            return 0.0

        peak = float('-inf')
        max_dd = 0.0
        for _, value in self._portfolio_value_series:
            if value > peak:
                peak = value
            if peak > 0:
                dd = (peak - value) / peak
                if dd > max_dd:
                    max_dd = dd

        return max_dd

    def get_calmar_ratio(self) -> float:
        """
        Calculate Calmar ratio (annualized return / max drawdown).

        Returns:
            Calmar ratio, or 0.0 if max_drawdown is 0
        """
        max_dd = self.get_max_drawdown()
        if max_dd == 0:
            return 0.0

        # Estimate annualized return from total P&L
        if len(self._portfolio_value_series) < 2:
            return 0.0

        first_ts, first_value = self._portfolio_value_series[0]
        last_ts, last_value = self._portfolio_value_series[-1]

        if first_value <= 0:
            return 0.0

        total_return = (last_value - first_value) / first_value
        days = (last_ts - first_ts).days or 1
        annualized_return = (1 + total_return) ** (365 / days) - 1

        return annualized_return / max_dd

    def get_average_slippage(self) -> float:
        """
        Calculate average slippage.

        Returns:
            Average slippage as decimal (0.001 = 0.1%)
        """
        if not self._slippage_samples:
            return 0.0
        return mean(self._slippage_samples)

    def get_max_slippage(self) -> float:
        """Get maximum observed slippage."""
        if not self._slippage_samples:
            return 0.0
        return max(self._slippage_samples)

    # ── Data Access ─────────────────────────────────────────────────

    def get_completed_trades(self, count: int = 50) -> List[TradeRecord]:
        """Get recent completed trades."""
        trades = list(self._completed_trades)
        return trades[-count:]

    def get_completed_trades_dict(self, count: int = 50) -> List[Dict[str, Any]]:
        """Get recent completed trades as dictionaries."""
        return [t.to_dict() for t in self.get_completed_trades(count)]

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a complete performance summary.

        Returns:
            Dictionary with all key performance metrics
        """
        return {
            'win_rate': self.get_win_rate(),
            'profit_factor': self.get_profit_factor(),
            'average_win': self.get_average_win(),
            'average_loss': self.get_average_loss(),
            'expectancy': self.get_expectancy(),
            'sharpe_ratio': self.get_sharpe_ratio(),
            'sortino_ratio': self.get_sortino_ratio(),
            'max_drawdown': self.get_max_drawdown(),
            'calmar_ratio': self.get_calmar_ratio(),
            'total_realized_pnl': self._total_realized_pnl,
            'total_fees': self._total_fees,
            'total_trades': len(self._completed_trades),
            'winning_trades': sum(1 for t in self._completed_trades if t.is_winning),
            'losing_trades': sum(1 for t in self._completed_trades if not t.is_winning),
            'average_slippage': self.get_average_slippage(),
            'max_slippage': self.get_max_slippage(),
            'sharpe_rolling_window': self.sharpe_rolling_window
        }

    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trade history for charting or export."""
        return self.get_completed_trades_dict(limit)

    def reset(self) -> None:
        """Reset all collected metrics."""
        self._completed_trades.clear()
        self._pnl_series.clear()
        self._portfolio_value_series.clear()
        self._slippage_samples.clear()
        self._trade_timestamps.clear()
        self._total_realized_pnl = 0.0
        self._total_fees = 0.0
        self._peak_portfolio_value = 0.0
        self._trough_after_peak = float('inf')
        self._current_drawdown = 0.0
        self._max_drawdown = 0.0
        self._start_time = None
        logger.info("MetricsCollector reset")

    def __repr__(self) -> str:
        return (
            f"MetricsCollector(trades={len(self._completed_trades)}, "
            f"win_rate={self.get_win_rate():.1f}%, "
            f"sharpe={self.get_sharpe_ratio():.2f}, "
            f"max_dd={self.get_max_drawdown():.2%})"
        )


# ──────────────────────────────────────────────────────────────────────
# PerformanceTracker (High-Level)
# ──────────────────────────────────────────────────────────────────────

class PerformanceTracker:
    """
    High-level performance tracker that composes MetricsCollector
    with TradeMonitor and PositionTracker.

    Provides:
    - Real-time P&L calculation
    - Trade frequency analysis (per hour, per day)
    - Slippage analysis summary
    - Automatic periodic snapshot recording

    Usage:
        tracker = PerformanceTracker(
            trade_monitor=monitor,
            position_tracker=positions
        )
        tracker.start()
        # ... trading loop ...
        summary = tracker.get_performance_summary()
    """

    def __init__(
        self,
        trade_monitor: Optional[TradeMonitor] = None,
        position_tracker: Optional[PositionTracker] = None,
        snapshot_interval_seconds: int = 60,
        max_metrics_history: int = 10000,
        sharpe_window: int = 252,
        risk_free_rate: float = 0.02
    ):
        """
        Initialize PerformanceTracker.

        Args:
            trade_monitor: TradeMonitor instance
            position_tracker: PositionTracker instance
            snapshot_interval_seconds: Seconds between automatic P&L snapshots
            max_metrics_history: Max number of trade records to retain
            sharpe_window: Rolling window for Sharpe ratio calculation
            risk_free_rate: Annual risk-free rate for Sharpe ratio
        """
        self.trade_monitor = trade_monitor
        self.position_tracker = position_tracker
        self.snapshot_interval_seconds = snapshot_interval_seconds

        # Core metrics collector
        self.collector = MetricsCollector(
            trade_monitor=trade_monitor,
            position_tracker=position_tracker,
            max_trade_history=max_metrics_history,
            sharpe_rolling_window=sharpe_window,
            risk_free_rate=risk_free_rate
        )

        # Snapshot timing
        self._last_snapshot_time: Optional[datetime] = None
        self._running: bool = False

        # Frequency tracking
        self._hourly_trade_counts: Dict[int, int] = {}  # {hour_of_day: count}
        self._daily_trade_counts: Dict[str, int] = {}  # {YYYY-MM-DD: count}

        logger.info(
            f"PerformanceTracker initialized "
            f"(snapshot_interval={snapshot_interval_seconds}s)"
        )

    # ── Lifecycle ───────────────────────────────────────────────────

    def start(self) -> None:
        """Start performance tracking."""
        self._running = True
        self.collector.register_monitor_listeners()
        logger.info("PerformanceTracker started")

    def stop(self) -> None:
        """Stop performance tracking."""
        self._running = False
        self.collector.unregister_monitor_listeners()
        logger.info("PerformanceTracker stopped")

    def tick(self, timestamp: Optional[datetime] = None) -> None:
        """
        Called on each trading loop iteration.

        Automatically records P&L snapshots at configured intervals.

        Args:
            timestamp: Current timestamp (defaults to now)
        """
        if not self._running:
            return

        ts = timestamp or datetime.now()

        # Check if snapshot due
        if self._last_snapshot_time:
            elapsed = (ts - self._last_snapshot_time).total_seconds()
            if elapsed < self.snapshot_interval_seconds:
                return

        self._last_snapshot_time = ts
        self.record_snapshot(ts)

    def record_snapshot(self, timestamp: Optional[datetime] = None) -> None:
        """
        Record a performance snapshot manually.

        Args:
            timestamp: Snapshot timestamp (defaults to now)
        """
        if not self.position_tracker:
            return

        ts = timestamp or datetime.now()
        portfolio = self.position_tracker.calculate_portfolio_value()

        self.collector.record_pnl_snapshot(
            pnl=portfolio['total_pnl'],
            portfolio_value=portfolio['total_position_value'],
            timestamp=ts
        )

    # ── Trade Frequency Analysis ────────────────────────────────────

    def record_trade_time(self, trade_timestamp: datetime) -> None:
        """
        Record a trade timestamp for frequency analysis.

        Args:
            trade_timestamp: Time when trade occurred
        """
        hour = trade_timestamp.hour
        self._hourly_trade_counts[hour] = (
            self._hourly_trade_counts.get(hour, 0) + 1
        )

        day_key = trade_timestamp.strftime('%Y-%m-%d')
        self._daily_trade_counts[day_key] = (
            self._daily_trade_counts.get(day_key, 0) + 1
        )

    def get_trades_per_day(self, days: int = 30) -> float:
        """
        Calculate average trades per day over recent period.

        Args:
            days: Number of recent days to consider

        Returns:
            Average trades per day
        """
        if not self._daily_trade_counts:
            return 0.0

        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent = {
            d: c for d, c in self._daily_trade_counts.items() if d >= cutoff
        }

        if not recent:
            return 0.0

        return sum(recent.values()) / len(recent)

    def get_trades_per_hour(self) -> float:
        """
        Calculate average trades per hour (based on all trade data).

        Returns:
            Average trades per hour across all recorded hours
        """
        if not self._hourly_trade_counts:
            return 0.0
        return sum(self._hourly_trade_counts.values()) / 24.0

    def get_most_active_hour(self) -> Optional[int]:
        """
        Get the hour of day with most trades.

        Returns:
            Hour (0-23) with most trades, or None if no data
        """
        if not self._hourly_trade_counts:
            return None
        return max(self._hourly_trade_counts, key=self._hourly_trade_counts.get)

    def get_hourly_distribution(self) -> Dict[int, int]:
        """Get trade count per hour of day."""
        return dict(self._hourly_trade_counts)

    # ── Slippage Analysis ───────────────────────────────────────────

    def get_slippage_summary(self) -> Dict[str, float]:
        """
        Get slippage analysis summary.

        Returns:
            Dict with avg, max, min slippage metrics
        """
        return {
            'average_slippage': self.collector.get_average_slippage(),
            'max_slippage': self.collector.get_max_slippage(),
            'slippage_samples': len(self.collector._slippage_samples)
        }

    # ── Comprehensive Summary ───────────────────────────────────────

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive performance summary including
        metrics, P&L, trade frequency, and slippage analysis.

        Returns:
            Complete performance summary dictionary
        """
        metrics = self.collector.get_summary()

        # Get latest portfolio data
        portfolio = {}
        if self.position_tracker:
            portfolio = self.position_tracker.calculate_portfolio_value()

        return {
            # Core metrics
            **metrics,

            # Portfolio
            'unrealized_pnl': portfolio.get('total_unrealized_pnl', 0.0),
            'realized_pnl': metrics['total_realized_pnl'],
            'total_pnl': (
                portfolio.get('total_unrealized_pnl', 0.0)
                + metrics['total_realized_pnl']
            ),

            # Trade frequency
            'trades_per_day': self.get_trades_per_day(),
            'trades_per_hour': self.get_trades_per_hour(),
            'most_active_hour': self.get_most_active_hour(),
            'hourly_distribution': self.get_hourly_distribution(),

            # Slippage
            'average_slippage_percent': metrics['average_slippage'] * 100,
            'max_slippage_percent': metrics['max_slippage'] * 100,

            # Status
            'tracking_active': self._running,
            'total_trades_recorded': metrics['total_trades']
        }

    def get_simple_report(self) -> str:
        """
        Generate a human-readable performance report string.

        Returns:
            Formatted multi-line report string
        """
        s = self.get_performance_summary()
        return (
            f"══════════ Performance Report ══════════\n"
            f" Total Trades:      {s['total_trades']:>8d}\n"
            f" Winning Trades:    {s['winning_trades']:>8d}\n"
            f" Losing Trades:     {s['losing_trades']:>8d}\n"
            f" Win Rate:          {s['win_rate']:>8.1f}%\n"
            f"──────────────────────────────────────────\n"
            f" Profit Factor:     {s['profit_factor']:>8.2f}\n"
            f" Average Win:       {s['average_win']:>8.2f}\n"
            f" Average Loss:      {s['average_loss']:>8.2f}\n"
            f" Expectancy:        {s['expectancy']:>8.2f}\n"
            f"──────────────────────────────────────────\n"
            f" Total P&L:         {s['total_pnl']:>8.2f}\n"
            f" Unrealized P&L:    {s['unrealized_pnl']:>8.2f}\n"
            f" Realized P&L:      {s['realized_pnl']:>8.2f}\n"
            f" Max Drawdown:      {s['max_drawdown']:>8.2%}\n"
            f"──────────────────────────────────────────\n"
            f" Sharpe Ratio:      {s['sharpe_ratio']:>8.2f}\n"
            f" Sortino Ratio:     {s['sortino_ratio']:>8.2f}\n"
            f" Calmar Ratio:      {s['calmar_ratio']:>8.2f}\n"
            f"──────────────────────────────────────────\n"
            f" Avg Slippage:      {s['average_slippage_percent']:>8.4f}%\n"
            f" Max Slippage:      {s['max_slippage_percent']:>8.4f}%\n"
            f" Trades/Day:        {s['trades_per_day']:>8.1f}\n"
            f" Most Active Hour:  {s['most_active_hour'] or 'N/A':>8}\n"
            f"══════════════════════════════════════════"
        )

    def reset(self) -> None:
        """Reset all performance data."""
        self.collector.reset()
        self._hourly_trade_counts.clear()
        self._daily_trade_counts.clear()
        self._last_snapshot_time = None
        logger.info("PerformanceTracker reset")

    def __repr__(self) -> str:
        return (
            f"PerformanceTracker(running={self._running}, "
            f"trades={len(self.collector._completed_trades)})"
        )