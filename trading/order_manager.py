from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from utils.logger import logger


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """Order side enumeration"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """Order data structure"""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled: float = 0.0
    remaining: float = 0.0
    fee: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    exchange_id: Optional[str] = None
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.remaining == 0.0:
            self.remaining = self.amount
    
    @property
    def is_active(self) -> bool:
        """Check if order is still active"""
        return self.status in [
            OrderStatus.PENDING,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED
        ]
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_cancelled(self) -> bool:
        """Check if order is cancelled"""
        return self.status == OrderStatus.CANCELLED
    
    @property
    def fill_percentage(self) -> float:
        """Get fill percentage"""
        if self.amount == 0:
            return 0.0
        return (self.filled / self.amount) * 100
    
    def update_from_exchange(self, exchange_data: Dict[str, Any]) -> None:
        """Update order data from exchange response"""
        self.exchange_id = exchange_data.get('id', self.exchange_id)
        self.status = self._parse_status(exchange_data.get('status', 'pending'))
        self.filled = float(exchange_data.get('filled', self.filled))
        self.remaining = float(exchange_data.get('remaining', self.remaining))
        self.price = float(exchange_data.get('price', self.price or 0))
        
        # Update timestamps
        if self.status == OrderStatus.FILLED and not self.filled_at:
            self.filled_at = datetime.now()
        
        self.updated_at = datetime.now()
        
        # Extract fee if available
        fee_data = exchange_data.get('fee', {})
        if fee_data:
            self.fee = float(fee_data.get('cost', self.fee))
    
    def _parse_status(self, status_str: str) -> OrderStatus:
        """Parse exchange status string to OrderStatus"""
        status_map = {
            'pending': OrderStatus.PENDING,
            'open': OrderStatus.OPEN,
            'partially_filled': OrderStatus.PARTIALLY_FILLED,
            'filled': OrderStatus.FILLED,
            'closed': OrderStatus.FILLED,
            'cancelled': OrderStatus.CANCELLED,
            'canceled': OrderStatus.CANCELLED,
            'rejected': OrderStatus.REJECTED,
            'expired': OrderStatus.EXPIRED
        }
        return status_map.get(status_str.lower(), OrderStatus.PENDING)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side.value,
            'type': self.order_type.value,
            'amount': self.amount,
            'price': self.price,
            'status': self.status.value,
            'filled': self.filled,
            'remaining': self.remaining,
            'fee': self.fee,
            'fill_percentage': self.fill_percentage,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'is_active': self.is_active,
            'is_filled': self.is_filled,
            'exchange_id': self.exchange_id
        }


class OrderManager:
    """
    Order management system for trading operations.
    Handles order lifecycle, tracking, and execution coordination.
    """
    
    def __init__(self, exchange=None, max_pending_orders: int = 10):
        """
        Initialize OrderManager.
        
        Args:
            exchange: Exchange instance for order operations
            max_pending_orders: Maximum number of pending orders allowed
        """
        self.exchange = exchange
        self.max_pending_orders = max_pending_orders
        
        # Order storage
        self._orders: Dict[str, Order] = {}
        self._pending_orders: Dict[str, Order] = {}
        self._open_orders: Dict[str, Order] = {}
        self._filled_orders: Dict[str, Order] = {}
        self._cancelled_orders: Dict[str, Order] = {}
        
        # Thread safety
        self._lock = Lock()
        
        # Statistics
        self._order_counter = 0
        self._total_orders = 0
        self._total_filled = 0
        self._total_cancelled = 0
        self._total_rejected = 0
        
        logger.info("OrderManager initialized")
    
    def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                    amount: float, price: Optional[float] = None,
                    client_order_id: Optional[str] = None,
                    metadata: Optional[Dict] = None) -> Optional[Order]:
        """
        Create a new order.
        
        Args:
            symbol: Trading pair symbol
            side: Order side (BUY or SELL)
            order_type: Order type (MARKET, LIMIT, etc.)
            amount: Order amount
            price: Order price (required for limit orders)
            client_order_id: Optional client order ID
            metadata: Optional metadata dictionary
            
        Returns:
            Order object or None if creation failed
        """
        try:
            # Check pending order limit
            if len(self._pending_orders) >= self.max_pending_orders:
                logger.warning(f"Max pending orders ({self.max_pending_orders}) reached")
                return None
            
            # Validate order
            if order_type == OrderType.LIMIT and price is None:
                logger.error("Price is required for limit orders")
                return None
            
            if amount <= 0:
                logger.error(f"Invalid order amount: {amount}")
                return None
            
            # Generate order ID
            self._order_counter += 1
            order_id = f"local_{self._order_counter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create order
            order = Order(
                id=order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=amount,
                price=price,
                client_order_id=client_order_id,
                metadata=metadata or {}
            )
            
            with self._lock:
                self._orders[order_id] = order
                self._pending_orders[order_id] = order
                self._total_orders += 1
            
            logger.info(f"Order created: {order_id} ({side.value} {amount} {symbol})")
            return order
            
        except Exception as e:
            logger.error(f"Order creation failed: {e}")
            return None
    
    def submit_order(self, order_id: str) -> bool:
        """
        Submit order to exchange for execution.
        
        Args:
            order_id: Local order ID
            
        Returns:
            True if submission successful, False otherwise
        """
        try:
            order = self._orders.get(order_id)
            if not order:
                logger.error(f"Order not found: {order_id}")
                return False
            
            if not self.exchange:
                logger.error("No exchange configured")
                return False
            
            # Submit to exchange
            exchange_order = self.exchange.place_order(
                symbol=order.symbol,
                side=order.side.value,
                amount=order.amount,
                price=order.price,
                order_type=order.order_type.value
            )
            
            if not exchange_order or not exchange_order.get('id'):
                logger.error(f"Exchange rejected order: {order_id}")
                order.status = OrderStatus.REJECTED
                order.reject_reason = "Exchange rejected"
                self._handle_rejected_order(order)
                return False
            
            # Update order with exchange data
            order.exchange_id = exchange_order['id']
            order.update_from_exchange(exchange_order)
            
            # Move from pending to open/active
            with self._lock:
                if order_id in self._pending_orders:
                    del self._pending_orders[order_id]
                
                if order.is_active:
                    self._open_orders[order_id] = order
            
            logger.info(f"Order submitted: {order_id} (Exchange ID: {order.exchange_id})")
            return True
            
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            return False
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            order = self._orders.get(order_id)
            if not order:
                logger.error(f"Order not found: {order_id}")
                return False
            
            if not order.is_active:
                logger.warning(f"Order {order_id} is not active (status: {order.status.value})")
                return False
            
            # Cancel on exchange if submitted
            if order.exchange_id and self.exchange:
                success = self.exchange.cancel_order(order.exchange_id)
                if not success:
                    logger.error(f"Exchange cancellation failed for {order_id}")
                    return False
            
            # Update order status
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.now()
            order.updated_at = datetime.now()
            
            # Move to cancelled
            with self._lock:
                if order_id in self._open_orders:
                    del self._open_orders[order_id]
                if order_id in self._pending_orders:
                    del self._pending_orders[order_id]
                self._cancelled_orders[order_id] = order
                self._total_cancelled += 1
            
            logger.info(f"Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            return False
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """
        Cancel all active orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            Number of orders cancelled
        """
        cancelled_count = 0
        orders_to_cancel = []
        
        with self._lock:
            for order_id, order in list(self._open_orders.items()) + list(self._pending_orders.items()):
                if symbol is None or order.symbol == symbol:
                    orders_to_cancel.append(order_id)
        
        for order_id in orders_to_cancel:
            if self.cancel_order(order_id):
                cancelled_count += 1
        
        logger.info(f"Cancelled {cancelled_count} orders" + (f" for {symbol}" if symbol else ""))
        return cancelled_count
    
    def update_order_status(self, order_id: str) -> Optional[Order]:
        """
        Update order status from exchange.
        
        Args:
            order_id: Order ID to update
            
        Returns:
            Updated Order or None
        """
        try:
            order = self._orders.get(order_id)
            if not order:
                logger.error(f"Order not found: {order_id}")
                return None
            
            if not order.exchange_id or not self.exchange:
                logger.warning(f"Order {order_id} has no exchange ID")
                return order
            
            # Fetch from exchange
            exchange_data = self.exchange.get_order_status(order.exchange_id)
            if not exchange_data:
                logger.error(f"Failed to fetch order status from exchange: {order_id}")
                return order
            
            # Update order
            previous_status = order.status
            order.update_from_exchange(exchange_data)
            
            # Handle status changes
            if previous_status != order.status:
                if order.status == OrderStatus.FILLED:
                    self._handle_filled_order(order)
                elif order.status == OrderStatus.CANCELLED:
                    self._handle_cancelled_order(order)
                elif order.status == OrderStatus.REJECTED:
                    self._handle_rejected_order(order)
                
                logger.info(f"Order {order_id} status changed: {previous_status.value} -> {order.status.value}")
            
            return order
            
        except Exception as e:
            logger.error(f"Order status update failed: {e}")
            return None
    
    def sync_orders(self) -> None:
        """Synchronize all open orders with exchange"""
        with self._lock:
            open_order_ids = list(self._open_orders.keys())
        
        updated_count = 0
        for order_id in open_order_ids:
            order = self.update_order_status(order_id)
            if order:
                updated_count += 1
        
        logger.info(f"Synchronized {updated_count} orders")
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return self._orders.get(order_id)
    
    def get_orders_by_symbol(self, symbol: str, status: Optional[OrderStatus] = None) -> List[Order]:
        """Get orders for specific symbol"""
        orders = []
        for order in self._orders.values():
            if order.symbol == symbol:
                if status is None or order.status == status:
                    orders.append(order)
        return orders
    
    def get_active_orders(self) -> List[Order]:
        """Get all active orders"""
        with self._lock:
            return list(self._open_orders.values()) + list(self._pending_orders.values())
    
    def get_filled_orders(self, since: Optional[datetime] = None) -> List[Order]:
        """Get filled orders, optionally filtered by time"""
        orders = []
        for order in self._filled_orders.values():
            if since is None or (order.filled_at and order.filled_at >= since):
                orders.append(order)
        return orders
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """Get order statistics"""
        with self._lock:
            return {
                'total_orders': self._total_orders,
                'total_filled': self._total_filled,
                'total_cancelled': self._total_cancelled,
                'total_rejected': self._total_rejected,
                'pending_orders': len(self._pending_orders),
                'open_orders': len(self._open_orders),
                'filled_orders': len(self._filled_orders),
                'cancelled_orders': len(self._cancelled_orders),
                'active_orders': len(self._open_orders) + len(self._pending_orders)
            }
    
    def _handle_filled_order(self, order: Order) -> None:
        """Handle filled order"""
        with self._lock:
            if order.id in self._open_orders:
                del self._open_orders[order.id]
            self._filled_orders[order.id] = order
            self._total_filled += 1
        
        logger.info(f"Order filled: {order.id} ({order.fill_percentage:.1f}%)")
    
    def _handle_cancelled_order(self, order: Order) -> None:
        """Handle cancelled order"""
        with self._lock:
            if order.id in self._open_orders:
                del self._open_orders[order.id]
            if order.id in self._pending_orders:
                del self._pending_orders[order.id]
            self._cancelled_orders[order.id] = order
    
    def _handle_rejected_order(self, order: Order) -> None:
        """Handle rejected order"""
        with self._lock:
            if order.id in self._pending_orders:
                del self._pending_orders[order.id]
            self._total_rejected += 1
    
    def cleanup_old_orders(self, days: int = 7) -> int:
        """Clean up orders older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        
        with self._lock:
            for order_id in list(self._cancelled_orders.keys()):
                order = self._cancelled_orders[order_id]
                if order.cancelled_at and order.cancelled_at < cutoff:
                    del self._cancelled_orders[order_id]
                    if order_id in self._orders:
                        del self._orders[order_id]
                    removed += 1
            
            for order_id in list(self._filled_orders.keys()):
                order = self._filled_orders[order_id]
                if order.filled_at and order.filled_at < cutoff:
                    del self._filled_orders[order_id]
                    if order_id in self._orders:
                        del self._orders[order_id]
                    removed += 1
        
        logger.info(f"Cleaned up {removed} old orders")
        return removed
    
    def __repr__(self) -> str:
        stats = self.get_order_statistics()
        return f"OrderManager(active={stats['active_orders']}, filled={stats['total_filled']})"
