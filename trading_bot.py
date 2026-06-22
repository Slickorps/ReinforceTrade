import time
import signal
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents import DecisionTower, EnvironmentAgent, ShortTermAgent, TrendAgent, RLAgent
from trading import CCXTExchange
from strategies import MultiAgentStrategy, RiskManager
from backtesting import EnhancedBacktester
from config import settings
from utils import logger


class TradingBot:
    """
    Main trading bot controller for live trading.
    Integrates multi-agent system, risk management, and exchange execution.
    """
    
    def __init__(self, 
                 exchange: CCXTExchange = None,
                 symbols: List[str] = None,
                 risk_manager: RiskManager = None,
                 strategy: MultiAgentStrategy = None):
        """
        Initialize TradingBot with all necessary components.
        
        Args:
            exchange: CCXTExchange instance for live trading
            symbols: List of trading pairs to monitor
            risk_manager: RiskManager instance for risk control
            strategy: MultiAgentStrategy for signal generation
        """
        # Initialize agents
        self.agents = [
            EnvironmentAgent(),
            ShortTermAgent(),
            TrendAgent()
        ]
        
        # Add RL agent if configured
        if hasattr(settings, 'rl_agent') and settings.rl_agent.get('enabled', False):
            try:
                rl_agent = RLAgent(
                    model_path=settings.rl_agent.get('model_path', 'models/rl_model'),
                    agent_type=settings.rl_agent.get('type', 'PPO')
                )
                self.agents.append(rl_agent)
                logger.info("RL Agent added to trading bot")
            except Exception as e:
                logger.warning(f"Failed to load RL agent: {e}")
        
        # Initialize decision tower
        self.decision_tower = DecisionTower(self.agents)
        
        # Initialize exchange
        self.exchange = exchange
        
        # Initialize symbols
        self.symbols = symbols or settings.trading.get('symbols', ['BTC/USDT', 'ETH/USDT'])
        
        # Initialize strategy
        self.strategy = strategy or MultiAgentStrategy(use_rl=False)
        
        # Initialize risk manager
        self.risk_manager = risk_manager or RiskManager(
            max_position_size=settings.risk.get('max_position_size', 0.1),
            max_drawdown=settings.risk.get('max_drawdown', 0.15),
            stop_loss_pct=settings.risk.get('stop_loss', 0.05),
            take_profit_pct=settings.risk.get('take_profit', 0.1)
        )
        
        # Trading state
        self.running = False
        self.trading_thread = None
        self.interval = settings.trading.get('interval', 60)  # seconds
        self.last_trade_time = {}
        self.trade_history = []
        self.current_positions = {}
        
        # Performance metrics
        self.start_time = None
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("TradingBot initialized successfully")
        logger.info(f"Monitoring symbols: {self.symbols}")
        logger.info(f"Trading interval: {self.interval}s")
    
    def run_live(self, test_mode: bool = True) -> None:
        """
        Start live trading loop.
        
        Args:
            test_mode: If True, run in test/sandbox mode (recommended for development)
        """
        if self.running:
            logger.warning("Trading bot is already running")
            return
        
        if self.exchange is None:
            logger.error("No exchange configured. Please provide a CCXTExchange instance.")
            return
        
        # Check exchange connection
        if not self.exchange.check_connection():
            logger.error("Exchange connection failed. Please check your API credentials.")
            return
        
        self.running = True
        self.start_time = datetime.now()
        
        logger.info(f"Starting live trading in {'TEST' if test_mode else 'LIVE'} mode")
        logger.info("Press Ctrl+C to stop the trading bot")
        
        try:
            while self.running:
                # Main trading loop
                self._trading_iteration()
                
                # Sleep until next iteration
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            logger.info("Trading interrupted by user")
        except Exception as e:
            logger.error(f"Trading loop error: {e}", exc_info=True)
        finally:
            self._graceful_shutdown()
    
    def _trading_iteration(self) -> None:
        """Execute one iteration of the trading loop"""
        try:
            # 1. Fetch real-time market data for all symbols
            market_data = self._fetch_market_data()
            if not market_data:
                logger.warning("No market data available, skipping iteration")
                return
            
            # 2. Update agents with market data
            agent_signals = self._get_agent_signals(market_data)
            
            # 3. Get decision from decision tower
            decision = self.decision_tower.aggregate_signals(agent_signals, market_data)
            
            # 4. Check risk limits
            if not self._check_risk_limits(decision):
                logger.info("Risk limits exceeded, skipping trade")
                return
            
            # 5. Execute trades based on decision
            for symbol in self.symbols:
                if symbol in decision:
                    signal = decision[symbol]
                    if signal['action'] != 'HOLD':
                        self._execute_trade(symbol, signal)
            
            # 6. Update positions and PnL
            self._update_positions()
            
            # 7. Log trading status
            self._log_trading_status()
            
        except Exception as e:
            logger.error(f"Error in trading iteration: {e}", exc_info=True)
    
    def _fetch_market_data(self) -> Dict[str, Any]:
        """
        Fetch real-time market data for all symbols.
        
        Returns:
            Dictionary with market data for each symbol
        """
        market_data = {}
        
        for symbol in self.symbols:
            try:
                # Get ticker data
                ticker = self.exchange.get_ticker(symbol)
                if ticker:
                    market_data[symbol] = ticker
                else:
                    logger.warning(f"Failed to get ticker for {symbol}")
                    
            except Exception as e:
                logger.error(f"Error fetching market data for {symbol}: {e}")
        
        return market_data
    
    def _get_agent_signals(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get signals from all agents.
        
        Args:
            market_data: Current market data
            
        Returns:
            Dictionary with signals from each agent
        """
        signals = {}
        
        for agent in self.agents:
            try:
                agent_name = agent.__class__.__name__
                agent_signal = agent.analyze(market_data)
                signals[agent_name] = agent_signal
                logger.debug(f"Agent {agent_name} signal: {agent_signal}")
                
            except Exception as e:
                logger.error(f"Error getting signal from {agent.__class__.__name__}: {e}")
        
        return signals
    
    def _check_risk_limits(self, decision: Dict[str, Any]) -> bool:
        """
        Check if trade is within risk limits.
        
        Args:
            decision: Trading decision from decision tower
            
        Returns:
            True if trade is within risk limits, False otherwise
        """
        try:
            # Check total exposure
            total_exposure = sum(
                abs(pos.get('size', 0)) for pos in self.current_positions.values()
            )
            
            if total_exposure > self.risk_manager.max_position_size:
                logger.warning(f"Total exposure {total_exposure} exceeds limit {self.risk_manager.max_position_size}")
                return False
            
            # Check drawdown
            current_drawdown = self._calculate_drawdown()
            if current_drawdown > self.risk_manager.max_drawdown:
                logger.warning(f"Current drawdown {current_drawdown:.2%} exceeds limit {self.risk_manager.max_drawdown:.2%}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False
    
    def _execute_trade(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """
        Execute a trade based on signal.
        
        Args:
            symbol: Trading pair symbol
            signal: Trading signal with action and parameters
            
        Returns:
            True if trade executed successfully, False otherwise
        """
        try:
            action = signal.get('action')
            strength = signal.get('strength', 0.5)
            
            # Calculate position size based on signal strength
            position_size = self.risk_manager.calculate_position_size(
                signal_strength=strength,
                account_balance=self._get_account_balance()
            )
            
            if position_size <= 0:
                logger.info(f"Zero position size for {symbol}, skipping trade")
                return False
            
            # Execute trade
            if action == 'BUY':
                order = self.exchange.place_order(
                    symbol=symbol,
                    side='buy',
                    amount=position_size,
                    order_type='market'
                )
                
            elif action == 'SELL':
                # Check if we have position to sell
                current_position = self.current_positions.get(symbol, {}).get('size', 0)
                if current_position <= 0:
                    logger.warning(f"No position to sell for {symbol}")
                    return False
                
                order = self.exchange.place_order(
                    symbol=symbol,
                    side='sell',
                    amount=min(position_size, current_position),
                    order_type='market'
                )
            else:
                logger.debug(f"No trade action for {symbol}")
                return False
            
            if order and order.get('id'):
                # Record trade
                self._record_trade(symbol, action, order)
                logger.info(f"Trade executed: {action} {position_size} {symbol} (Order ID: {order['id']})")
                return True
            else:
                logger.error(f"Trade execution failed for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}")
            return False
    
    def _get_account_balance(self) -> float:
        """Get current account balance in quote currency (e.g., USDT)"""
        try:
            balance = self.exchange.get_balance()
            # Sum all quote currency balances (USDT, USD, etc.)
            total = 0.0
            for currency, amount in balance.items():
                if currency in ['USDT', 'USD', 'USDC', 'BUSD']:
                    total += amount
            return total
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return 0.0
    
    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown from peak"""
        if self.total_pnl <= 0:
            return 0.0
        
        peak = max(0, self.total_pnl)
        if peak == 0:
            return 0.0
        
        current = self.total_pnl
        drawdown = (peak - current) / peak if peak > 0 else 0
        
        return drawdown
    
    def _update_positions(self) -> None:
        """Update current positions from exchange"""
        try:
            balance = self.exchange.get_balance()
            
            for symbol in self.symbols:
                base_currency = symbol.split('/')[0]
                if base_currency in balance:
                    size = balance[base_currency]
                    if size > 0:
                        # Get current price
                        ticker = self.exchange.get_ticker(symbol)
                        if ticker:
                            self.current_positions[symbol] = {
                                'size': size,
                                'current_price': ticker['price'],
                                'updated_at': datetime.now()
                            }
                    else:
                        if symbol in self.current_positions:
                            del self.current_positions[symbol]
                            
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
    
    def _record_trade(self, symbol: str, action: str, order: Dict[str, Any]) -> None:
        """Record trade execution"""
        trade_record = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'action': action,
            'order_id': order.get('id'),
            'amount': order.get('amount'),
            'price': order.get('price'),
            'status': order.get('status')
        }
        
        self.trade_history.append(trade_record)
        self.total_trades += 1
        
        # Calculate PnL (simplified)
        if action == 'SELL':
            # TODO: Implement proper PnL calculation
            pass
    
    def _log_trading_status(self) -> None:
        """Log current trading status"""
        try:
            runtime = datetime.now() - self.start_time if self.start_time else None
            runtime_str = str(runtime).split('.')[0] if runtime else "N/A"
            
            status = {
                'runtime': runtime_str,
                'total_trades': self.total_trades,
                'current_positions': len(self.current_positions),
                'total_pnl': f"${self.total_pnl:.2f}",
                'drawdown': f"{self._calculate_drawdown():.2%}"
            }
            
            logger.info(f"Trading Status: {status}")
            
        except Exception as e:
            logger.error(f"Error logging status: {e}")
    
    def stop(self) -> None:
        """Stop the trading bot"""
        logger.info("Stopping trading bot...")
        self.running = False
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop()
    
    def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown"""
        logger.info("Performing graceful shutdown...")
        
        # Cancel any pending orders
        try:
            # TODO: Implement order cancellation logic
            pass
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        # Log final statistics
        self._log_trading_status()
        
        logger.info("Trading bot stopped")
    
    def get_trading_stats(self) -> Dict[str, Any]:
        """Get current trading statistics"""
        runtime = datetime.now() - self.start_time if self.start_time else None
        
        return {
            'running': self.running,
            'runtime': str(runtime).split('.')[0] if runtime else None,
            'total_trades': self.total_trades,
            'total_pnl': self.total_pnl,
            'current_drawdown': self._calculate_drawdown(),
            'current_positions': self.current_positions,
            'trade_history_count': len(self.trade_history)
        }
    
    def __repr__(self) -> str:
        return f"TradingBot(symbols={self.symbols}, running={self.running})"
