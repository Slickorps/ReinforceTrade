from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from utils.logger import logger


class PositionStatus(Enum):
    """Position status enumeration"""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"


@dataclass
class Position:
    """Position data structure representing a trading position"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    trades: List[Dict] = field(default_factory=list)
    fees: float = 0.0
    
    @property
    def is_active(self) -> bool:
        """Check if position is still active"""
        return self.status == PositionStatus.OPEN
    
    @property
    def is_closed(self) -> bool:
        """Check if position is closed"""
        return self.status == PositionStatus.CLOSED
    
    @property
    def pnl_percentage(self) -> float:
        """Calculate PnL as percentage of entry value"""
        if self.size == 0 or self.entry_price == 0:
            return 0.0
        
        entry_value = self.size * self.entry_price
        if entry_value == 0:
            return 0.0
        
        return (self.total_pnl / entry_value) * 100
    
    @property
    def unrealized_pnl_percentage(self) -> float:
        """Calculate unrealized PnL as percentage"""
        if self.size == 0 or self.entry_price == 0:
            return 0.0
        
        entry_value = self.size * self.entry_price
        if entry_value == 0:
            return 0.0
        
        return (self.unrealized_pnl / entry_value) * 100
    
    def update_price(self, new_price: float) -> None:
        """Update current price and recalculate unrealized PnL"""
        self.current_price = new_price
        self.updated_at = datetime.now()
        
        if self.is_active:
            if self.side == 'long':
                self.unrealized_pnl = (new_price - self.entry_price) * self.size
            else:  # short
                self.unrealized_pnl = (self.entry_price - new_price) * self.size
            
            self.total_pnl = self.realized_pnl + self.unrealized_pnl
    
    def add_trade(self, trade: Dict[str, Any]) -> None:
        """Add a trade to the position"""
        self.trades.append(trade)
        self.updated_at = datetime.now()
        
        # Update fees
        trade_fee = trade.get('fee', 0)
        self.fees += trade_fee
        
        # Update realized PnL for closing trades
        if trade.get('action') == 'close':
            realized = trade.get('realized_pnl', 0)
            self.realized_pnl += realized
            self.total_pnl = self.realized_pnl + self.unrealized_pnl
    
    def close(self, close_price: float, close_size: Optional[float] = None) -> float:
        """
        Close position or part of position.
        
        Args:
            close_price: Price at which to close
            close_size: Amount to close (None for full close)
            
        Returns:
            Realized PnL from the close
        """
        if not self.is_active:
            return 0.0
        
        close_size = close_size or self.size
        
        if close_size <= 0 or close_size > self.size:
            logger.error(f"Invalid close size: {close_size}")
            return 0.0
        
        # Calculate realized PnL
        if self.side == 'long':
            realized = (close_price - self.entry_price) * close_size
        else:  # short
            realized = (self.entry_price - close_price) * close_size
        
        # Add closing trade
        close_trade = {
            'timestamp': datetime.now(),
            'action': 'close',
            'size': close_size,
            'price': close_price,
            'realized_pnl': realized,
            'fee': 0  # Will be updated by order manager
        }
        
        self.add_trade(close_trade)
        
        # Update position size
        self.size -= close_size
        
        # Update status
        if self.size == 0:
            self.status = PositionStatus.CLOSED
            self.closed_at = datetime.now()
            self.unrealized_pnl = 0.0
        else:
            self.status = PositionStatus.PARTIALLY_CLOSED
        
        return realized
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'size': self.size,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': self.total_pnl,
            'pnl_percentage': self.pnl_percentage,
            'unrealized_pnl_percentage': self.unrealized_pnl_percentage,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'trades_count': len(self.trades),
            'fees': self.fees,
            'is_active': self.is_active
        }


class PositionTracker:
    """
    Position tracking system for managing trading positions.
    Handles position creation, updates, PnL calculation, and reporting.
    """
    
    def __init__(self):
        """Initialize PositionTracker"""
        self._positions: Dict[str, Position] = {}
        self._lock = Lock()
        
        # Statistics
        self._total_positions = 0
        self._active_positions = 0
        self._closed_positions = 0
        self._total_pnl = 0.0
        self._total_fees = 0.0
        
        logger.info("PositionTracker initialized")
    
    def create_position(self, symbol: str, side: str, size: float, 
                       entry_price: float) -> Optional[Position]:
        """
        Create a new position.
        
        Args:
            symbol: Trading pair symbol
            side: Position side ('long' or 'short')
            size: Position size
            entry_price: Entry price
            
        Returns:
            Position object or None if creation failed
        """
        try:
            if size <= 0 or entry_price <= 0:
                logger.error(f"Invalid position parameters: size={size}, price={entry_price}")
                return None
            
            if side not in ['long', 'short']:
                logger.error(f"Invalid position side: {side}")
                return None
            
            # Check if position already exists
            existing = self.get_position(symbol)
            if existing and existing.is_active:
                logger.warning(f"Active position already exists for {symbol}")
                return existing
            
            # Create new position
            position = Position(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                current_price=entry_price
            )
            
            with self._lock:
                self._positions[symbol] = position
                self._total_positions += 1
                self._active_positions += 1
            
            logger.info(f"Position created: {symbol} {side} {size} @ {entry_price}")
            return position
            
        except Exception as e:
            logger.error(f"Position creation failed: {e}")
            return None
    
    def update_position_price(self, symbol: str, current_price: float) -> bool:
        """
        Update position with current market price.
        
        Args:
            symbol: Trading pair symbol
            current_price: Current market price
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            position = self.get_position(symbol)
            if not position:
                return False
            
            position.update_price(current_price)
            
            # Update total PnL
            self._update_statistics()
            
            return True
            
        except Exception as e:
            logger.error(f"Position price update failed: {e}")
            return False
    
    def add_position_trade(self, symbol: str, trade: Dict[str, Any]) -> bool:
        """
        Add a trade to a position.
        
        Args:
            symbol: Trading pair symbol
            trade: Trade information
            
        Returns:
            True if trade added successfully, False otherwise
        """
        try:
            position = self.get_position(symbol)
            if not position:
                return False
            
            position.add_trade(trade)
            
            # Update statistics
            self._update_statistics()
            
            return True
            
        except Exception as e:
            logger.error(f"Adding position trade failed: {e}")
            return False
    
    def close_position(self, symbol: str, close_price: float, 
                      close_size: Optional[float] = None) -> float:
        """
        Close a position or part of position.
        
        Args:
            symbol: Trading pair symbol
            close_price: Close price
            close_size: Amount to close (None for full close)
            
        Returns:
            Realized PnL from the close
        """
        try:
            position = self.get_position(symbol)
            if not position or not position.is_active:
                return 0.0
            
            realized = position.close(close_price, close_size)
            
            # Update statistics
            if position.is_closed:
                with self._lock:
                    self._active_positions -= 1
                    self._closed_positions += 1
            
            self._update_statistics()
            
            logger.info(f"Position closed: {symbol} realized PnL: {realized:.2f}")
            return realized
            
        except Exception as e:
            logger.error(f"Position close failed: {e}")
            return 0.0
    
    def close_all_positions(self) -> Dict[str, float]:
        """
        Close all active positions at current prices.
        
        Returns:
            Dictionary of symbol to realized PnL
        """
        results = {}
        
        with self._lock:
            active_positions = list(self._positions.values())
        
        for position in active_positions:
            if position.is_active:
                realized = self.close_position(position.symbol, position.current_price)
                results[position.symbol] = realized
        
        logger.info(f"Closed {len(results)} positions")
        return results
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol"""
        return self._positions.get(symbol)
    
    def get_all_positions(self) -> Dict[str, Position]:
        """Get all positions"""
        with self._lock:
            return dict(self._positions)
    
    def get_active_positions(self) -> Dict[str, Position]:
        """Get all active positions"""
        active = {}
        with self._lock:
            for symbol, position in self._positions.items():
                if position.is_active:
                    active[symbol] = position
        return active
    
    def get_closed_positions(self) -> Dict[str, Position]:
        """Get all closed positions"""
        closed = {}
        with self._lock:
            for symbol, position in self._positions.items():
                if position.is_closed:
                    closed[symbol] = position
        return closed
    
    def update_all_prices(self, market_data: Dict[str, float]) -> None:
        """
        Update all positions with current market prices.
        
        Args:
            market_data: Dictionary of symbol to current price
        """
        updated_count = 0
        
        for symbol, price in market_data.items():
            if self.update_position_price(symbol, price):
                updated_count += 1
        
        if updated_count > 0:
            logger.debug(f"Updated prices for {updated_count} positions")
    
    def calculate_portfolio_value(self) -> Dict[str, float]:
        """
        Calculate portfolio value statistics.
        
        Returns:
            Dictionary with portfolio statistics
        """
        total_unrealized = 0.0
        total_realized = 0.0
        total_value = 0.0
        
        with self._lock:
            for position in self._positions.values():
                total_unrealized += position.unrealized_pnl
                total_realized += position.realized_pnl
                
                # Add position value
                if position.is_active:
                    total_value += position.size * position.current_price
        
        return {
            'total_unrealized_pnl': total_unrealized,
            'total_realized_pnl': total_realized,
            'total_pnl': total_unrealized + total_realized,
            'total_position_value': total_value,
            'active_positions': self._active_positions,
            'closed_positions': self._closed_positions
        }
    
    def get_position_statistics(self) -> Dict[str, Any]:
        """Get position statistics"""
        portfolio = self.calculate_portfolio_value()
        
        # Calculate additional statistics
        winning_positions = 0
        losing_positions = 0
        
        with self._lock:
            for position in self._positions.values():
                if position.total_pnl > 0:
                    winning_positions += 1
                elif position.total_pnl < 0:
                    losing_positions += 1
        
        win_rate = (winning_positions / self._total_positions * 100) if self._total_positions > 0 else 0
        
        return {
            'total_positions': self._total_positions,
            'active_positions': self._active_positions,
            'closed_positions': self._closed_positions,
            'winning_positions': winning_positions,
            'losing_positions': losing_positions,
            'win_rate': win_rate,
            'total_pnl': portfolio['total_pnl'],
            'total_fees': self._total_fees,
            'portfolio_value': portfolio['total_position_value']
        }
    
    def get_position_summary(self) -> Dict[str, Any]:
        """Get detailed position summary"""
        active = self.get_active_positions()
        closed = self.get_closed_positions()
        
        # Active positions summary
        active_summary = []
        for symbol, position in active.items():
            active_summary.append({
                'symbol': symbol,
                'side': position.side,
                'size': position.size,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'unrealized_pnl': position.unrealized_pnl,
                'pnl_percentage': position.pnl_percentage
            })
        
        # Closed positions summary
        closed_summary = []
        for symbol, position in closed.items():
            closed_summary.append({
                'symbol': symbol,
                'side': position.side,
                'total_pnl': position.total_pnl,
                'pnl_percentage': position.pnl_percentage,
                'duration': str(position.closed_at - position.created_at) if position.closed_at else None
            })
        
        return {
            'active_positions': active_summary,
            'closed_positions': closed_summary,
            'statistics': self.get_position_statistics()
        }
    
    def _update_statistics(self) -> None:
        """Update internal statistics"""
        with self._lock:
            self._total_pnl = 0.0
            self._total_fees = 0.0
            
            for position in self._positions.values():
                self._total_pnl += position.total_pnl
                self._total_fees += position.fees
    
    def cleanup_old_positions(self, days: int = 30) -> int:
        """
        Clean up old closed positions.
        
        Args:
            days: Number of days to keep positions
            
        Returns:
            Number of positions removed
        """
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        
        with self._lock:
            positions_to_remove = []
            
            for symbol, position in self._positions.items():
                if (position.is_closed and 
                    position.closed_at and 
                    position.closed_at < cutoff):
                    positions_to_remove.append(symbol)
            
            for symbol in positions_to_remove:
                del self._positions[symbol]
                removed += 1
        
        logger.info(f"Cleaned up {removed} old positions")
        return removed
    
    def __repr__(self) -> str:
        stats = self.get_position_statistics()
        return f"PositionTracker(active={stats['active_positions']}, total_pnl={stats['total_pnl']:.2f})"
