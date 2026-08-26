import gymnasium as gym
import numpy as np
import pandas as pd
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

        # Observation space: [balance, position, price, volume, technical indicators...]
        # Simplified for now
        self.observation_space = spaces.Box(
            low=np.array([0, -1, 0, 0]),  # balance, position (-1=short, 0=flat, 1=long), price, volume
            high=np.array([np.inf, 1, np.inf, np.inf]),
            dtype=np.float32
        )

        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0  # 0: no position, 1: long, -1: short
        self.position_size = 0
        self.total_pnl = 0

        return self._get_observation(), {}

    def step(self, action):
        current_data = self.data[self.current_step]
        price = current_data['close']

        # Execute action
        reward = 0
        if action == 1 and self.position <= 0:  # Buy
            if self.position == -1:  # Close short
                pnl = (self.position_size - price) * abs(self.position_size)
                self.balance += pnl
                reward += pnl
                self.position = 0
                self.position_size = 0
            else:  # Open long
                size = self.balance * 0.1  # Use 10% of balance
                fee = size * self.transaction_fee
                self.balance -= fee
                self.position = 1
                self.position_size = size / price
                reward -= fee

        elif action == 2 and self.position >= 0:  # Sell
            if self.position == 1:  # Close long
                pnl = (price - self.position_size) * abs(self.position_size)
                self.balance += pnl
                reward += pnl
                self.position = 0
                self.position_size = 0
            else:  # Open short
                size = self.balance * 0.1
                fee = size * self.transaction_fee
                self.balance -= fee
                self.position = -1
                self.position_size = size / price
                reward -= fee

        # Calculate unrealized PnL
        if self.position == 1:
            unrealized_pnl = (price - self.position_size) * abs(self.position_size)
        elif self.position == -1:
            unrealized_pnl = (self.position_size - price) * abs(self.position_size)
        else:
            unrealized_pnl = 0

        self.total_pnl = self.balance - self.initial_balance + unrealized_pnl

        self.current_step += 1
        terminated = self.current_step >= len(self.data) - 1
        truncated = False

        # Reward is the change in total portfolio value
        next_obs = self._get_observation()

        return next_obs, reward, terminated, truncated, {"total_pnl": self.total_pnl, "balance": self.balance}

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
