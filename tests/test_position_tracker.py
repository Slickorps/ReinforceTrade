"""
Unit tests for PositionTracker and Position classes.
"""

import unittest
from unittest.mock import Mock
from datetime import datetime, timedelta
import sys
sys.path.insert(0, '..')

from trading.position_tracker import PositionTracker, Position, PositionStatus


class TestPosition(unittest.TestCase):
    """Test cases for Position class"""
    
    def test_position_creation(self):
        """Test position creation"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        self.assertEqual(position.symbol, 'BTC/USDT')
        self.assertEqual(position.side, 'long')
        self.assertEqual(position.size, 0.1)
        self.assertEqual(position.entry_price, 50000.0)
        self.assertEqual(position.current_price, 50000.0)
        self.assertEqual(position.status, PositionStatus.OPEN)
        self.assertTrue(position.is_active)
        self.assertFalse(position.is_closed)
        
    def test_position_short(self):
        """Test short position"""
        position = Position(
            symbol='BTC/USDT',
            side='short',
            size=0.1,
            entry_price=50000.0
        )
        
        self.assertEqual(position.side, 'short')
        self.assertTrue(position.is_active)
        
    def test_update_price_long(self):
        """Test price update for long position"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        # Price goes up
        position.update_price(51000.0)
        
        self.assertEqual(position.current_price, 51000.0)
        self.assertEqual(position.unrealized_pnl, 100.0)  # (51000-50000) * 0.1
        self.assertEqual(position.total_pnl, 100.0)
        
        # Price goes down
        position.update_price(49000.0)
        
        self.assertEqual(position.current_price, 49000.0)
        self.assertEqual(position.unrealized_pnl, -100.0)  # (49000-50000) * 0.1
        
    def test_update_price_short(self):
        """Test price update for short position"""
        position = Position(
            symbol='BTC/USDT',
            side='short',
            size=0.1,
            entry_price=50000.0
        )
        
        # Price goes down (profit for short)
        position.update_price(49000.0)
        
        self.assertEqual(position.current_price, 49000.0)
        self.assertEqual(position.unrealized_pnl, 100.0)  # (50000-49000) * 0.1
        
        # Price goes up (loss for short)
        position.update_price(51000.0)
        
        self.assertEqual(position.current_price, 51000.0)
        self.assertEqual(position.unrealized_pnl, -100.0)  # (50000-51000) * 0.1
        
    def test_add_trade(self):
        """Test adding trade to position"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        trade = {
            'timestamp': datetime.now(),
            'action': 'increase',
            'size': 0.05,
            'price': 51000.0,
            'fee': 2.5
        }
        
        position.add_trade(trade)
        
        self.assertEqual(len(position.trades), 1)
        self.assertEqual(position.fees, 2.5)
        self.assertIsNotNone(position.updated_at)
        
    def test_add_closing_trade(self):
        """Test adding closing trade"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        trade = {
            'timestamp': datetime.now(),
            'action': 'close',
            'size': 0.1,
            'price': 51000.0,
            'realized_pnl': 100.0,
            'fee': 2.5
        }
        
        position.add_trade(trade)
        
        self.assertEqual(position.realized_pnl, 100.0)
        self.assertEqual(position.total_pnl, 100.0)
        
    def test_close_position_full(self):
        """Test full position close"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        realized = position.close(51000.0)
        
        self.assertEqual(realized, 100.0)
        self.assertEqual(position.status, PositionStatus.CLOSED)
        self.assertEqual(position.size, 0.0)
        self.assertEqual(position.unrealized_pnl, 0.0)
        self.assertEqual(position.realized_pnl, 100.0)
        self.assertIsNotNone(position.closed_at)
        
    def test_close_position_partial(self):
        """Test partial position close"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        realized = position.close(51000.0, 0.05)
        
        self.assertEqual(realized, 50.0)  # Half of full position
        self.assertEqual(position.status, PositionStatus.PARTIALLY_CLOSED)
        self.assertEqual(position.size, 0.05)
        self.assertEqual(position.realized_pnl, 50.0)
        
    def test_close_position_short(self):
        """Test closing short position"""
        position = Position(
            symbol='BTC/USDT',
            side='short',
            size=0.1,
            entry_price=50000.0
        )
        
        # Price goes down (profit for short)
        realized = position.close(49000.0)
        
        self.assertEqual(realized, 100.0)  # (50000-49000) * 0.1
        
    def test_close_invalid_size(self):
        """Test closing with invalid size"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        # Try to close more than position size
        realized = position.close(51000.0, 0.2)
        
        self.assertEqual(realized, 0.0)
        
    def test_pnl_percentage(self):
        """Test PnL percentage calculation"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        position.update_price(51000.0)
        
        # Entry value = 0.1 * 50000 = 5000, PnL = 100
        expected_percentage = (100.0 / 5000.0) * 100
        self.assertEqual(position.pnl_percentage, expected_percentage)
        
    def test_pnl_percentage_zero_entry(self):
        """Test PnL percentage with zero entry price"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=0.0
        )
        
        self.assertEqual(position.pnl_percentage, 0.0)
        
    def test_to_dict(self):
        """Test position serialization"""
        position = Position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        position.update_price(51000.0)
        
        data = position.to_dict()
        
        self.assertEqual(data['symbol'], 'BTC/USDT')
        self.assertEqual(data['side'], 'long')
        self.assertEqual(data['size'], 0.1)
        self.assertEqual(data['entry_price'], 50000.0)
        self.assertEqual(data['current_price'], 51000.0)
        self.assertEqual(data['unrealized_pnl'], 100.0)
        self.assertEqual(data['status'], 'open')
        self.assertTrue(data['is_active'])


class TestPositionTracker(unittest.TestCase):
    """Test cases for PositionTracker class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tracker = PositionTracker()
        
    def test_init(self):
        """Test PositionTracker initialization"""
        self.assertEqual(len(self.tracker._positions), 0)
        
        stats = self.tracker.get_position_statistics()
        self.assertEqual(stats['total_positions'], 0)
        self.assertEqual(stats['active_positions'], 0)
        
    def test_create_position_success(self):
        """Test successful position creation"""
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        self.assertIsNotNone(position)
        self.assertEqual(position.symbol, 'BTC/USDT')
        self.assertEqual(position.side, 'long')
        
        # Check statistics
        stats = self.tracker.get_position_statistics()
        self.assertEqual(stats['total_positions'], 1)
        self.assertEqual(stats['active_positions'], 1)
        
    def test_create_position_invalid_parameters(self):
        """Test position creation with invalid parameters"""
        # Invalid size
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=-0.1,
            entry_price=50000.0
        )
        
        self.assertIsNone(position)
        
        # Invalid price
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=-50000.0
        )
        
        self.assertIsNone(position)
        
        # Invalid side
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='invalid',
            size=0.1,
            entry_price=50000.0
        )
        
        self.assertIsNone(position)
        
    def test_create_position_duplicate(self):
        """Test creating position for existing symbol"""
        # Create first position
        position1 = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        # Try to create second position
        position2 = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.2,
            entry_price=51000.0
        )
        
        # Should return existing position
        self.assertEqual(position1.id, position2.id)
        
    def test_get_position(self):
        """Test getting position by symbol"""
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        retrieved = self.tracker.get_position('BTC/USDT')
        
        self.assertEqual(retrieved.id, position.id)
        
    def test_get_position_not_found(self):
        """Test getting non-existent position"""
        position = self.tracker.get_position('NONEXISTENT')
        
        self.assertIsNone(position)
        
    def test_update_position_price(self):
        """Test updating position price"""
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        result = self.tracker.update_position_price('BTC/USDT', 51000.0)
        
        self.assertTrue(result)
        
        updated = self.tracker.get_position('BTC/USDT')
        self.assertEqual(updated.current_price, 51000.0)
        self.assertEqual(updated.unrealized_pnl, 100.0)
        
    def test_update_position_price_not_found(self):
        """Test updating price for non-existent position"""
        result = self.tracker.update_position_price('NONEXISTENT', 51000.0)
        
        self.assertFalse(result)
        
    def test_add_position_trade(self):
        """Test adding trade to position"""
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        trade = {
            'timestamp': datetime.now(),
            'action': 'increase',
            'size': 0.05,
            'price': 51000.0,
            'fee': 2.5
        }
        
        result = self.tracker.add_position_trade('BTC/USDT', trade)
        
        self.assertTrue(result)
        
        updated = self.tracker.get_position('BTC/USDT')
        self.assertEqual(len(updated.trades), 1)
        self.assertEqual(updated.fees, 2.5)
        
    def test_close_position(self):
        """Test closing position"""
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        realized = self.tracker.close_position('BTC/USDT', 51000.0)
        
        self.assertEqual(realized, 100.0)
        
        # Check statistics
        stats = self.tracker.get_position_statistics()
        self.assertEqual(stats['active_positions'], 0)
        self.assertEqual(stats['closed_positions'], 1)
        
    def test_close_position_not_active(self):
        """Test closing non-active position"""
        position = self.tracker.create_position(
            symbol='BTC/USDT',
            side='long',
            size=0.1,
            entry_price=50000.0
        )
        
        # Close once
        self.tracker.close_position('BTC/USDT', 51000.0)
        
        # Try to close again
        realized = self.tracker.close_position('BTC/USDT', 51000.0)
        
        self.assertEqual(realized, 0.0)
        
    def test_get_active_positions(self):
        """Test getting active positions"""
        self.tracker.create_position('BTC/USDT', 'long', 0.1, 50000.0)
        self.tracker.create_position('ETH/USDT', 'short', 1.0, 3000.0)
        
        active = self.tracker.get_active_positions()
        
        self.assertEqual(len(active), 2)
        self.assertIn('BTC/USDT', active)
        self.assertIn('ETH/USDT', active)
        
    def test_get_closed_positions(self):
        """Test getting closed positions"""
        # Create and close position
        self.tracker.create_position('BTC/USDT', 'long', 0.1, 50000.0)
        self.tracker.close_position('BTC/USDT', 51000.0)
        
        closed = self.tracker.get_closed_positions()
        
        self.assertEqual(len(closed), 1)
        self.assertIn('BTC/USDT', closed)
        
    def test_update_all_prices(self):
        """Test updating all positions with market data"""
        self.tracker.create_position('BTC/USDT', 'long', 0.1, 50000.0)
        self.tracker.create_position('ETH/USDT', 'short', 1.0, 3000.0)
        
        market_data = {
            'BTC/USDT': 51000.0,
            'ETH/USDT': 2900.0
        }
        
        self.tracker.update_all_prices(market_data)
        
        btc_position = self.tracker.get_position('BTC/USDT')
        eth_position = self.tracker.get_position('ETH/USDT')
        
        self.assertEqual(btc_position.current_price, 51000.0)
        self.assertEqual(eth_position.current_price, 2900.0)
        
    def test_calculate_portfolio_value(self):
        """Test portfolio value calculation"""
        self.tracker.create_position('BTC/USDT', 'long', 0.1, 50000.0)
        self.tracker.create_position('ETH/USDT', 'short', 1.0, 3000.0)
        
        # Update prices
        self.tracker.update_position_price('BTC/USDT', 51000.0)
        self.tracker.update_position_price('ETH/USDT', 2900.0)
        
        portfolio = self.tracker.calculate_portfolio_value()
        
        self.assertEqual(portfolio['active_positions'], 2)
        self.assertEqual(portfolio['total_unrealized_pnl'], 200.0)  # 100 + 100
        self.assertEqual(portfolio['total_position_value'], 8000.0)  # 5100 + 2900
        
    def test_close_all_positions(self):
        """Test closing all positions"""
        self.tracker.create_position('BTC/USDT', 'long', 0.1, 50000.0)
        self.tracker.create_position('ETH/USDT', 'short', 1.0, 3000.0)
        
        # Update prices
        self.tracker.update_position_price('BTC/USDT', 51000.0)
        self.tracker.update_position_price('ETH/USDT', 2900.0)
        
        results = self.tracker.close_all_positions()
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results['BTC/USDT'], 100.0)
        self.assertEqual(results['ETH/USDT'], 100.0)
        
        # Check all are closed
        stats = self.tracker.get_position_statistics()
        self.assertEqual(stats['active_positions'], 0)
        self.assertEqual(stats['closed_positions'], 2)
        
    def test_position_statistics(self):
        """Test position statistics"""
        # Create winning position
        self.tracker.create_position('BTC/USDT', 'long', 0.1, 50000.0)
        self.tracker.update_position_price('BTC/USDT', 51000.0)
        self.tracker.close_position('BTC/USDT', 51000.0)
        
        # Create losing position
        self.tracker.create_position('ETH/USDT', 'long', 1.0, 3000.0)
        self.tracker.update_position_price('ETH/USDT', 2900.0)
        self.tracker.close_position('ETH/USDT', 2900.0)
        
        stats = self.tracker.get_position_statistics()
        
        self.assertEqual(stats['total_positions'], 2)
        self.assertEqual(stats['closed_positions'], 2)
        self.assertEqual(stats['winning_positions'], 1)
        self.assertEqual(stats['losing_positions'], 1)
        self.assertEqual(stats['win_rate'], 50.0)
        self.assertEqual(stats['total_pnl'], 0.0)  # 100 - 100
        
    def test_cleanup_old_positions(self):
        """Test cleaning up old positions"""
        # Create and close position
        position = self.tracker.create_position('BTC/USDT', 'long', 0.1, 50000.0)
        self.tracker.close_position('BTC/USDT', 51000.0)
        
        # Manually set old close time
        position.closed_at = datetime.now() - timedelta(days=40)
        
        # Clean up positions older than 30 days
        removed = self.tracker.cleanup_old_positions(days=30)
        
        self.assertEqual(removed, 1)
        
        # Position should be removed
        retrieved = self.tracker.get_position('BTC/USDT')
        self.assertIsNone(retrieved)
        
    def test_repr(self):
        """Test string representation"""
        repr_str = repr(self.tracker)
        
        self.assertIn('PositionTracker', repr_str)
        self.assertIn('active=0', repr_str)
        self.assertIn('total_pnl=0.00', repr_str)


if __name__ == '__main__':
    unittest.main()
