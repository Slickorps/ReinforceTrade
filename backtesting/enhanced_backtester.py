from backtesting.backtester import Backtester
from strategies.risk_manager import RiskManager
from strategies.multi_agent_strategy import MultiAgentStrategy
from typing import Dict, Any, List
from utils.logger import logger
import pandas as pd
import matplotlib.pyplot as plt
import json

class EnhancedBacktester(Backtester):
    """
    Enhanced backtesting engine with risk management and multi-agent strategy support.
    Provides comprehensive performance metrics and visualization.
    """
    def __init__(self, strategy: MultiAgentStrategy, initial_balance: float = 10000,
                 risk_manager: RiskManager = None):
        super().__init__(strategy, initial_balance)
        self.risk_manager = risk_manager or RiskManager()
        self.performance_metrics = {}
        self.equity_curve = []
        self.drawdown_periods = []
        self.agent_signals_history = []

    def run(self, market_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run backtest with full risk management and performance tracking.
        """
        logger.info(f"Starting enhanced backtest with {len(market_data)} data points")

        for i, data in enumerate(market_data):
            current_price = data['close']
            timestamp = data.get('timestamp', i)

            # Track equity
            current_equity = self._calculate_equity(current_price)
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': current_equity,
                'price': current_price
            })

            # Check and update positions
            for position in self.positions[:]:
                # Calculate unrealized PnL
                unrealized_pnl = self._calculate_unrealized_pnl(position, current_price)
                position['unrealized_pnl'] = unrealized_pnl

                # Check exit conditions
                if self.strategy.should_exit(data, position):
                    self.close_position(position, current_price)

            # Check entry conditions
            if self.strategy.should_enter(data):
                # Get confidence from strategy
                signals = self.strategy.get_agent_signals(data)
                confidence = signals['decision'].get('confidence', 0)

                # Check risk limits
                symbol = data.get('symbol', 'UNKNOWN')
                position_size = self.strategy.calculate_position_size(self.balance, confidence)

                if self.risk_manager.check_exposure(symbol, position_size, self.balance):
                    self.open_position(data, position_size)
                    self.risk_manager.update_exposure(symbol, position_size)

            # Record agent signals for transparency
            if i % 100 == 0:  # Record every 100 steps
                signals = self.strategy.get_agent_signals(data)
                self.agent_signals_history.append({
                    'timestamp': timestamp,
                    'signals': signals
                })

        # Close remaining positions
        final_price = market_data[-1]['close'] if market_data else 0
        for position in self.positions:
            self.close_position(position, final_price)

        # Calculate comprehensive results
        results = self._calculate_enhanced_results()

        logger.info("Enhanced backtest completed")
        return results

    def open_position(self, data: Dict[str, Any], position_size: float = None):
        """Open position with specified size"""
        if position_size is None:
            position_size = self.balance * 0.1  # Default 10%

        price = data['close']
        amount = position_size / price

        position = {
            "entry_price": price,
            "amount": amount,
            "side": "long",
            "timestamp": data.get('timestamp'),
            "size": position_size
        }

        self.positions.append(position)
        self.balance -= position_size
        logger.info(f"Opened position: {amount:.4f} units at {price}")

    def close_position(self, position: Dict[str, Any], exit_price: float):
        """Close position and record trade"""
        entry_price = position['entry_price']
        amount = position['amount']

        # Calculate PnL
        if position['side'] == 'long':
            pnl = (exit_price - entry_price) * amount
        else:
            pnl = (entry_price - exit_price) * amount

        # Calculate return percentage
        invested = entry_price * amount
        return_pct = (pnl / invested) * 100 if invested > 0 else 0

        self.balance += (exit_price * amount)

        trade = {
            "entry_price": entry_price,
            "exit_price": exit_price,
            "amount": amount,
            "pnl": pnl,
            "return_pct": return_pct,
            "side": position['side'],
            "entry_time": position.get('timestamp'),
            "exit_time": exit_price  # Should be current timestamp
        }

        self.trades.append(trade)
        self.risk_manager.record_trade(trade)

        self.positions.remove(position)
        logger.info(f"Closed position: PnL={pnl:.2f} ({return_pct:.2f}%)")

    def _calculate_equity(self, current_price: float) -> float:
        """Calculate total equity including unrealized PnL"""
        equity = self.balance
        for position in self.positions:
            unrealized_pnl = self._calculate_unrealized_pnl(position, current_price)
            equity += (position['amount'] * current_price)
        return equity

    def _calculate_unrealized_pnl(self, position: Dict[str, Any], current_price: float) -> float:
        """Calculate unrealized PnL for open position"""
        if position['side'] == 'long':
            return (current_price - position['entry_price']) * position['amount']
        else:
            return (position['entry_price'] - current_price) * position['amount']

    def _calculate_enhanced_results(self) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        # Basic metrics
        total_trades = len(self.trades)
        if total_trades == 0:
            return {
                'initial_balance': self.initial_balance,
                'final_balance': self.balance,
                'total_return': 0,
                'total_return_pct': 0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'win_rate_pct': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'max_drawdown_pct': 0,
                'calmar_ratio': 0,
                'total_pnl': 0,
                'trades': [],
                'equity_curve': self.equity_curve,
                'risk_metrics': self.risk_manager.get_risk_metrics(),
                'agent_signals_sample': self.agent_signals_history[:10]
            }

        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]

        total_pnl = sum(t['pnl'] for t in self.trades)
        total_return = (self.balance - self.initial_balance) / self.initial_balance

        # Advanced metrics
        win_rate = len(winning_trades) / total_trades
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0

        # Profit factor
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Sharpe ratio approximation (simplified)
        if len(self.equity_curve) > 1:
            equity_values = [e['equity'] for e in self.equity_curve]
            returns = pd.Series(equity_values).pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * (252 ** 0.5) if returns.std() != 0 else 0
        else:
            sharpe_ratio = 0

        # Max drawdown
        max_drawdown = self._calculate_max_drawdown()

        # Calmar ratio
        calmar_ratio = (total_return / max_drawdown) if max_drawdown > 0 else 0

        results = {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'win_rate_pct': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'calmar_ratio': calmar_ratio,
            'total_pnl': total_pnl,
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'risk_metrics': self.risk_manager.get_risk_metrics(),
            'agent_signals_sample': self.agent_signals_history[:10]  # First 10 for transparency
        }

        self.performance_metrics = results
        return results

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve"""
        if not self.equity_curve:
            return 0

        peak = self.equity_curve[0]['equity']
        max_dd = 0

        for point in self.equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def generate_report(self, save_path: str = "reports/backtest_report.json"):
        """
        Generate comprehensive backtest report with visualizations.
        """
        import os
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Save JSON report
        with open(save_path, 'w') as f:
            # Remove non-serializable data for JSON
            report_data = {k: v for k, v in self.performance_metrics.items()
                          if k not in ['trades', 'equity_curve', 'agent_signals_sample']}
            json.dump(report_data, f, indent=2)

        # Generate visualizations
        self._plot_equity_curve()
        self._plot_drawdown()
        self._plot_trade_distribution()

        logger.info(f"Backtest report generated: {save_path}")

    def _plot_equity_curve(self):
        """Plot equity curve over time"""
        if not self.equity_curve:
            return

        df = pd.DataFrame(self.equity_curve)
        plt.figure(figsize=(12, 6))
        plt.plot(df['timestamp'], df['equity'], label='Equity', color='blue')
        plt.axhline(y=self.initial_balance, color='red', linestyle='--', label='Initial Balance')
        plt.title('Equity Curve During Backtest')
        plt.xlabel('Time')
        plt.ylabel('Equity')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig('reports/equity_curve.png')
        plt.close()

    def _plot_drawdown(self):
        """Plot drawdown over time"""
        if not self.equity_curve:
            return

        peak = self.equity_curve[0]['equity']
        drawdowns = []

        for point in self.equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            drawdowns.append(dd * 100)  # Convert to percentage

        plt.figure(figsize=(12, 4))
        plt.fill_between(range(len(drawdowns)), drawdowns, color='red', alpha=0.3)
        plt.plot(drawdowns, color='red')
        plt.title('Drawdown Over Time')
        plt.xlabel('Time')
        plt.ylabel('Drawdown (%)')
        plt.grid(True, alpha=0.3)
        plt.savefig('reports/drawdown.png')
        plt.close()

    def _plot_trade_distribution(self):
        """Plot distribution of trade returns"""
        if not self.trades:
            return

        returns = [t['return_pct'] for t in self.trades]

        plt.figure(figsize=(10, 6))
        plt.hist(returns, bins=30, alpha=0.7, color='green', edgecolor='black')
        plt.axvline(x=0, color='red', linestyle='--')
        plt.title('Distribution of Trade Returns')
        plt.xlabel('Return (%)')
        plt.ylabel('Frequency')
        plt.grid(True, alpha=0.3)
        plt.savefig('reports/trade_distribution.png')
        plt.close()
