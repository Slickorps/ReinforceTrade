import pandas as pd
from typing import Dict, Any, List
from strategies.base_strategy import BaseStrategy
from utils.logger import logger

class Backtester:
    def __init__(self, strategy: BaseStrategy, initial_balance: float = 10000, lookback: int = 60):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = []
        self.trades = []
        self.lookback = lookback
        logger.info(f"Backtester initialized with strategy {strategy.name} and balance {initial_balance}")

    def run(self, market_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        window: List[Dict[str, Any]] = []
        for data in market_data:
            # Maintain a rolling price-history window so strategies can compute signals
            window.append(data)
            if len(window) > self.lookback:
                window.pop(0)
            context = {**data, "prices": list(window)}

            # Check exit conditions for open positions
            for position in self.positions[:]:
                if self.strategy.should_exit(context, position):
                    self.close_position(position, data['close'])
            # Check entry conditions
            if self.strategy.should_enter(context):
                self.open_position(data)
        # Close any remaining positions
        for position in self.positions:
            self.close_position(position, market_data[-1]['close'])
        results = self.calculate_results()
        return results

    def open_position(self, data: Dict[str, Any]):
        # Assume long position for simplicity
        amount = self.balance * 0.1 / data['close']  # 10% of balance
        position = {
            "entry_price": data['close'],
            "amount": amount,
            "side": "long",
            "timestamp": data.get('timestamp')
        }
        self.positions.append(position)
        self.balance -= amount * data['close']
        logger.info(f"Opened position: {position}")

    def close_position(self, position: Dict[str, Any], exit_price: float):
        pnl = (exit_price - position['entry_price']) * position['amount']
        self.balance += position['amount'] * exit_price
        trade = {
            "entry_price": position['entry_price'],
            "exit_price": exit_price,
            "amount": position['amount'],
            "pnl": pnl,
            "side": position['side']
        }
        self.trades.append(trade)
        self.positions.remove(position)
        logger.info(f"Closed position: {trade}")

    def calculate_results(self) -> Dict[str, Any]:
        total_pnl = sum(trade['pnl'] for trade in self.trades)
        win_trades = len([t for t in self.trades if t['pnl'] > 0])
        total_trades = len(self.trades)
        win_rate = win_trades / total_trades if total_trades > 0 else 0
        final_balance = self.balance
        return {
            "initial_balance": self.initial_balance,
            "final_balance": final_balance,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "trades": self.trades
        }
