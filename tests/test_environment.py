import unittest
import numpy as np
from environments import TradingEnvironment


def candles(prices, volume=1000):
    """Build an OHLCV series from a list of close prices."""
    return [{'close': float(p), 'volume': float(volume)} for p in prices]


class TestTradingEnvironmentContract(unittest.TestCase):
    """Gymnasium API contract"""

    def setUp(self):
        self.env = TradingEnvironment(candles([100, 110, 120, 130]), initial_balance=10000)

    def test_reset_returns_obs_info(self):
        result = self.env.reset()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        obs, info = result
        self.assertEqual(obs.shape, (4,))
        self.assertIsInstance(info, dict)
        self.assertTrue(self.env.observation_space.contains(obs))

    def test_step_returns_five_tuple(self):
        self.env.reset()
        result = self.env.step(0)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 5)
        obs, reward, terminated, truncated, info = result
        self.assertEqual(obs.shape, (4,))
        self.assertIsInstance(reward, float)
        self.assertIsInstance(terminated, bool)
        self.assertIsInstance(truncated, bool)
        self.assertIn('total_pnl', info)
        self.assertIn('balance', info)

    def test_reset_seed_is_accepted(self):
        obs, info = self.env.reset(seed=42)
        self.assertEqual(obs.shape, (4,))


class TestTradingEnvironmentAccounting(unittest.TestCase):

    def test_hold_does_nothing(self):
        env = TradingEnvironment(candles([100, 100, 100]), initial_balance=10000, transaction_fee=0.0)
        env.reset()
        obs, reward, terminated, truncated, info = env.step(0)
        self.assertEqual(env.position, 0)
        self.assertAlmostEqual(env.balance, 10000.0)
        self.assertAlmostEqual(reward, 0.0)
        self.assertAlmostEqual(info['total_pnl'], 0.0)

    def test_open_long_tracks_quantity_and_entry(self):
        env = TradingEnvironment(candles([100, 110, 120]), initial_balance=10000, transaction_fee=0.0)
        env.reset()
        env.step(1)  # buy at 100
        self.assertEqual(env.position, 1)
        self.assertAlmostEqual(env.entry_price, 100.0)
        self.assertAlmostEqual(env.position_size, 10.0)  # 1000 notional / 100

    def test_long_mark_to_market_reward(self):
        env = TradingEnvironment(candles([100, 110, 120]), initial_balance=10000, transaction_fee=0.0)
        env.reset()
        _, r_open, _, _, _ = env.step(1)      # open long at 100 -> reward 0
        _, r_up, _, _, info = env.step(0)     # hold, price 110 -> +100
        self.assertAlmostEqual(r_open, 0.0)
        self.assertAlmostEqual(r_up, 100.0)   # (110-100) * 10 units
        self.assertAlmostEqual(info['total_pnl'], 100.0)

    def test_close_long_realizes_pnl(self):
        env = TradingEnvironment(candles([100, 110, 120]), initial_balance=10000, transaction_fee=0.0)
        env.reset()
        env.step(1)                            # open long at 100
        env.step(0)                            # hold to 110
        _, r_close, _, _, info = env.step(2)   # sell at 120
        self.assertEqual(env.position, 0)
        self.assertAlmostEqual(env.balance, 10200.0)  # +200 realized
        self.assertAlmostEqual(info['total_pnl'], 200.0)
        self.assertAlmostEqual(r_close, 100.0)        # equity 10100 -> 10200

    def test_short_profits_when_price_falls(self):
        env = TradingEnvironment(candles([100, 90, 80]), initial_balance=10000, transaction_fee=0.0)
        env.reset()
        env.step(2)                            # open short at 100
        self.assertEqual(env.position, -1)
        _, r_down, _, _, _ = env.step(0)       # hold, price 90 -> +100
        self.assertAlmostEqual(r_down, 100.0)
        _, _, _, _, info = env.step(1)         # cover short at 80
        self.assertEqual(env.position, 0)
        self.assertAlmostEqual(env.balance, 10200.0)
        self.assertAlmostEqual(info['total_pnl'], 200.0)

    def test_transaction_fee_is_charged(self):
        env = TradingEnvironment(candles([100, 100]), initial_balance=10000, transaction_fee=0.001)
        env.reset()
        _, reward, _, _, _ = env.step(1)       # open long: 1000 notional * 0.001 = 1.0 fee
        self.assertAlmostEqual(env.balance, 9999.0)
        self.assertAlmostEqual(reward, -1.0)

    def test_repeated_buy_while_long_is_ignored(self):
        env = TradingEnvironment(candles([100, 100, 100]), initial_balance=10000, transaction_fee=0.001)
        env.reset()
        env.step(1)
        qty = env.position_size
        balance = env.balance
        env.step(1)  # already long -> no-op (no extra fee/position)
        self.assertEqual(env.position, 1)
        self.assertAlmostEqual(env.position_size, qty)
        self.assertAlmostEqual(env.balance, balance)

    def test_episode_terminates_at_end(self):
        env = TradingEnvironment(candles([100, 101, 102]), initial_balance=10000)
        env.reset()
        _, _, terminated, _, _ = env.step(0)
        self.assertFalse(terminated)
        _, _, terminated, truncated, _ = env.step(0)
        self.assertTrue(terminated)
        self.assertFalse(truncated)


if __name__ == '__main__':
    unittest.main()
