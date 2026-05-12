#!/usr/bin/env python3
"""
PositionTracker Usage Example
Demonstrates position management and PnL tracking.
"""

import sys
sys.path.insert(0, '..')

from trading import PositionTracker, PositionStatus
from utils.logger import logger
from datetime import datetime


def main():
    """Main example function"""
    logger.info("PositionTracker Example")
    
    # Initialize position tracker
    tracker = PositionTracker()
    
    logger.info(f"PositionTracker: {tracker}")
    
    # Create a long position
    position = tracker.create_position(
        symbol='BTC/USDT',
        side='long',
        size=0.1,
        entry_price=50000.0
    )
    
    if position:
        logger.info(f"Position created: {position.symbol}")
        logger.info(f"Entry price: ${position.entry_price}")
        logger.info(f"Position size: {position.size}")
        logger.info(f"Position status: {position.status.value}")
    
    # Update price (price goes up)
    tracker.update_position_price('BTC/USDT', 51000.0)
    
    # Check PnL
    updated_position = tracker.get_position('BTC/USDT')
    if updated_position:
        logger.info(f"Current price: ${updated_position.current_price}")
        logger.info(f"Unrealized PnL: ${updated_position.unrealized_pnl:.2f}")
        logger.info(f"PnL percentage: {updated_position.unrealized_pnl_percentage:.2f}%")
    
    # Add a trade
    trade = {
        'timestamp': datetime.now(),
        'action': 'increase',
        'size': 0.05,
        'price': 51000.0,
        'fee': 2.5
    }
    
    tracker.add_position_trade('BTC/USDT', trade)
    
    # Update price (price goes down)
    tracker.update_position_price('BTC/USDT', 49000.0)
    
    # Check updated PnL
    updated_position = tracker.get_position('BTC/USDT')
    if updated_position:
        logger.info(f"Updated PnL: ${updated_position.unrealized_pnl:.2f}")
        logger.info(f"Total trades: {len(updated_position.trades)}")
    
    # Close position
    realized = tracker.close_position('BTC/USDT', 49000.0)
    logger.info(f"Position closed - Realized PnL: ${realized:.2f}")
    
    # Get statistics
    stats = tracker.get_position_statistics()
    logger.info(f"Statistics: {stats}")
    
    # Get portfolio value
    portfolio = tracker.calculate_portfolio_value()
    logger.info(f"Portfolio value: {portfolio}")


def test_multiple_positions():
    """Test multiple positions"""
    logger.info("Testing multiple positions...")
    
    tracker = PositionTracker()
    
    # Create multiple positions
    positions_data = [
        ('BTC/USDT', 'long', 0.1, 50000.0),
        ('ETH/USDT', 'short', 1.0, 3000.0),
        ('ADA/USDT', 'long', 1000.0, 1.5)
    ]
    
    for symbol, side, size, price in positions_data:
        tracker.create_position(symbol, side, size, price)
    
    # Update all prices
    market_data = {
        'BTC/USDT': 51000.0,  # +2%
        'ETH/USDT': 2900.0,   # -3.33%
        'ADA/USDT': 1.6       # +6.67%
    }
    
    tracker.update_all_prices(market_data)
    
    # Get summary
    summary = tracker.get_position_summary()
    logger.info(f"Active positions: {len(summary['active_positions'])}")
    
    for pos in summary['active_positions']:
        logger.info(f"  {pos['symbol']} {pos['side']}: PnL ${pos['unrealized_pnl']:.2f} ({pos['pnl_percentage']:.2f}%)")
    
    # Close all positions
    results = tracker.close_all_positions()
    logger.info(f"Closed all positions: {results}")


def test_position_lifecycle():
    """Test complete position lifecycle"""
    logger.info("Testing position lifecycle...")
    
    tracker = PositionTracker()
    
    # 1. Create position
    position = tracker.create_position('BTC/USDT', 'long', 0.1, 50000.0)
    logger.info(f"1. Created: {position.status.value}")
    
    # 2. Partial close
    realized = tracker.close_position('BTC/USDT', 51000.0, 0.05)
    logger.info(f"2. Partial close: ${realized:.2f}")
    
    updated = tracker.get_position('BTC/USDT')
    logger.info(f"   Status: {updated.status.value}, Size: {updated.size}")
    
    # 3. Full close
    realized = tracker.close_position('BTC/USDT', 52000.0)
    logger.info(f"3. Full close: ${realized:.2f}")
    
    final = tracker.get_position('BTC/USDT')
    logger.info(f"   Status: {final.status.value}")
    logger.info(f"   Total PnL: ${final.total_pnl:.2f}")
    logger.info(f"   Trades: {len(final.trades)}")


if __name__ == '__main__':
    test_position_lifecycle()
    print()
    test_multiple_positions()
    print()
    main()
