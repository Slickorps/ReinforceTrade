import gymnasium as gym
import numpy as np
from gymnasium import spaces
from typing import Dict, Any, List

class TradingEnvironment(gym.Env):
    """
    Custom trading environment for reinforcement learning.
    Agents learn to make trading decisions based on market data.
    """
    def __init__(self, data: List[Dict[str, Any]], initial_balance: float = 10000, transaction_fee: float = 0.001):
        super(TradingEnvironment, self).__init__()

        self.data = data
        self.initial_balance = initial_balance
        self.transaction_fee = transaction_fee

        # Action space: 0 = hold, 1 = buy, 2 = sell
        self.action_space = spaces.Discrete(3)

        # Observation space: [balance, position, price, volume]
        self.observation_space = spaces.Box(
            low=np.array([0, -1, 0, 0], dtype=np.float32),  # balance, position (-1=short, 0=flat, 1=long), price, volume
            high=np.array([np.inf, 1, np.inf, np.inf], dtype=np.float32),
            dtype=np.float32
        )

        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.balance = float(self.initial_balance)
        self.position = 0  # 0: no position, 1: long, -1: short
        self.position_size = 0.0  # quantity of the base asset held
        self.entry_price = 0.0
        self.total_pnl = 0.0
        self._prev_equity = float(self.initial_balance)

        return self._get_observation(), {}

    def _unrealized_pnl(self, price: float) -> float:
        """Mark-to-market PnL of the open position at the given price."""
        if self.position == 1:
            return (price - self.entry_price) * self.position_size
        if self.position == -1:
            return (self.entry_price - price) * self.position_size
        return 0.0

    def _equity(self, price: float) -> float:
        """Total mark-to-market portfolio value (cash + unrealized PnL)."""
        return self.balance + self._unrealized_pnl(price)

    def _open_position(self, price: float, direction: int) -> None:
        """Open a long (direction=1) or short (direction=-1) position using 10% of cash."""
        size = self.balance * 0.1
        fee = size * self.transaction_fee
        self.balance -= fee
        self.position = direction
        self.entry_price = price
        self.position_size = size / price

    def _close_position(self, price: float) -> None:
        """Realize the open position's PnL back into cash."""
        self.balance += self._unrealized_pnl(price)
        self.position = 0
        self.position_size = 0.0
        self.entry_price = 0.0

    def step(self, action):
        current_data = self.data[self.current_step]
        price = current_data['close']

        # Execute action
        if action == 1 and self.position <= 0:  # Buy
            if self.position == -1:  # Close short
                self._close_position(price)
            else:  # Open long
                self._open_position(price, direction=1)

        elif action == 2 and self.position >= 0:  # Sell
            if self.position == 1:  # Close long
                self._close_position(price)
            else:  # Open short
                self._open_position(price, direction=-1)

        # Reward is the change in mark-to-market portfolio value
        equity = self._equity(price)
        reward = equity - self._prev_equity
        self._prev_equity = equity
        self.total_pnl = equity - self.initial_balance

        self.current_step += 1
        terminated = self.current_step >= len(self.data) - 1
        truncated = False

        next_obs = self._get_observation()

        return next_obs, float(reward), terminated, truncated, {
            "total_pnl": self.total_pnl,
            "balance": self.balance,
            "position": self.position,
        }

    def _get_observation(self):
        if self.current_step >= len(self.data):
            return np.zeros(self.observation_space.shape)

        current_data = self.data[self.current_step]
        price = current_data['close']
        volume = current_data.get('volume', 0)

        return np.array([
            self.balance,
            self.position,
            price,
            volume
        ], dtype=np.float32)

    def render(self):
        print(f"Step: {self.current_step}, Balance: {self.balance:.2f}, Position: {self.position}, Total PnL: {self.total_pnl:.2f}")
