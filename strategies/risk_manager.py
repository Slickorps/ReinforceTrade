from typing import Dict, Any, List
from utils.logger import logger

class RiskManager:
    """
    Risk management system for trading operations.
    Implements position sizing, exposure limits, and risk monitoring.
    """
    def __init__(self, max_risk_per_trade: float = 0.01, max_portfolio_risk: float = 0.05, max_correlation: float = 0.7,
                 max_drawdown: float = 0.15):
        self.max_risk_per_trade = max_risk_per_trade  # 1% max risk per trade
        self.max_portfolio_risk = max_portfolio_risk  # 5% max portfolio risk
        self.max_correlation = max_correlation
        self.max_drawdown = max_drawdown  # 15% max drawdown limit
        self.current_exposure = {}
        self.trade_history = []
        
        logger.info("RiskManager initialized")

    def calculate_position_size(self, balance: float, entry_price: float, stop_loss: float, confidence: float) -> float:
        """
        Calculate optimal position size based on risk parameters.
        Uses Kelly Criterion simplified: position = (balance * risk_per_trade) / (entry - stop_loss)
        """
        risk_amount = balance * self.max_risk_per_trade
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            logger.warning("Price risk is zero, using minimum position size")
            return balance * 0.01  # Minimum 1% position
        
        # Kelly-like position sizing
        kelly_fraction = 0.5  # Conservative Kelly (half-Kelly)
        position_size = (risk_amount / price_risk) * entry_price * kelly_fraction
        
        # Apply confidence scaling
        position_size *= confidence
        
        # Cap at max position size
        max_position = balance * 0.1  # 10% of balance
        position_size = min(position_size, max_position)
        
        logger.info(f"Calculated position size: {position_size:.2f} (risk: {risk_amount:.2f}, price_risk: {price_risk:.4f})")
        return position_size

    def check_exposure(self, symbol: str, new_position_value: float, total_portfolio_value: float) -> bool:
        """
        Check if new position would exceed exposure limits.
        Returns True if allowed, False if rejected.
        """
        current_symbol_exposure = self.current_exposure.get(symbol, 0)
        total_exposure = sum(self.current_exposure.values())
        
        # Check individual symbol limit (20%)
        symbol_limit = total_portfolio_value * 0.2
        if current_symbol_exposure + new_position_value > symbol_limit:
            logger.warning(f"Symbol {symbol} exposure limit exceeded")
            return False
        
        # Check portfolio exposure limit
        portfolio_limit = total_portfolio_value * self.max_portfolio_risk
        if total_exposure + new_position_value > portfolio_limit:
            logger.warning(f"Portfolio exposure limit exceeded")
            return False
        
        return True

    def update_exposure(self, symbol: str, position_value: float):
        """Update current exposure tracking"""
        self.current_exposure[symbol] = position_value
        logger.debug(f"Updated exposure for {symbol}: {position_value}")

    def record_trade(self, trade: Dict[str, Any]):
        """Record trade for risk analysis"""
        self.trade_history.append(trade)
        
        # Keep only last 100 trades
        if len(self.trade_history) > 100:
            self.trade_history.pop(0)

    def get_risk_metrics(self) -> Dict[str, Any]:
        """
        Calculate current risk metrics.
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'max_drawdown': 0
            }
        
        wins = [t for t in self.trade_history if t.get('pnl', 0) > 0]
        losses = [t for t in self.trade_history if t.get('pnl', 0) <= 0]
        
        win_rate = len(wins) / len(self.trade_history) if self.trade_history else 0
        avg_profit = sum(t.get('pnl', 0) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get('pnl', 0) for t in losses) / len(losses) if losses else 0
        
        # Calculate max drawdown
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0
        for trade in self.trade_history:
            cumulative_pnl += trade.get('pnl', 0)
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            drawdown = peak - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            'total_trades': len(self.trade_history),
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'risk_reward_ratio': abs(avg_profit / avg_loss) if avg_loss != 0 else 0,
            'current_exposure': self.current_exposure,
            'total_exposure': sum(self.current_exposure.values())
        }

    def should_reduce_exposure(self, consecutive_losses: int = 3) -> bool:
        """
        Check if we should reduce exposure due to consecutive losses.
        """
        if len(self.trade_history) < consecutive_losses:
            return False
        
        recent_trades = self.trade_history[-consecutive_losses:]
        losses = [t for t in recent_trades if t.get('pnl', 0) <= 0]
        
        if len(losses) >= consecutive_losses:
            logger.warning(f"Detected {consecutive_losses} consecutive losses, reducing exposure")
            return True
        
        return False

    def get_dynamic_stop_loss(self, volatility: float, base_stop: float = 0.05) -> float:
        """
        Adjust stop loss based on market volatility.
        Higher volatility = wider stop loss to avoid getting stopped out.
        """
        # ATR-based stop loss adjustment could be implemented here
        if volatility > 0.1:  # High volatility
            return base_stop * 1.5
        elif volatility < 0.02:  # Low volatility
            return base_stop * 0.8
        return base_stop
