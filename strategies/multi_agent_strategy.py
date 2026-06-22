from strategies.base_strategy import BaseStrategy
from agents import DecisionTower, EnvironmentAgent, ShortTermAgent, TrendAgent, RLAgent
from typing import Dict, Any
from utils.logger import logger

class MultiAgentStrategy(BaseStrategy):
    """
    Trading strategy that combines signals from multiple agents.
    Includes entry logic, exit conditions, and stop loss/take profit mechanisms.
    """
    def __init__(self, use_rl: bool = True, confidence_threshold: float = 0.6):
        super().__init__("MultiAgentStrategy")
        
        # Initialize agents
        self.agents = [
            EnvironmentAgent(),
            ShortTermAgent(),
            TrendAgent()
        ]
        
        # Add RL agent if enabled
        if use_rl:
            if RLAgent is None:
                logger.warning(
                    "RLAgent requested but stable_baselines3 is not installed. "
                    "Running without RL agent. Install with: pip install stable-baselines3"
                )
            else:
                self.rl_agent = RLAgent(agent_type='ppo')
                self.rl_agent.load_model()
                self.agents.append(self.rl_agent)
        
        self.decision_tower = DecisionTower(self.agents)
        self.confidence_threshold = confidence_threshold
        
        # Strategy parameters
        self.max_position_size = 0.1  # Max 10% of balance per trade
        self.stop_loss_pct = 0.05     # 5% stop loss
        self.take_profit_pct = 0.10   # 10% take profit
        
        logger.info(f"MultiAgentStrategy initialized with {len(self.agents)} agents")

    def should_enter(self, market_data: Dict[str, Any]) -> bool:
        """
        Determine if we should enter a position.
        Requires strong confidence from decision tower.
        """
        result = self.decision_tower.process_market_data(market_data)
        decision = result['decision']
        
        action = decision.get('action', 'hold')
        confidence = decision.get('confidence', 0)
        
        # Only enter if action is buy/sell with sufficient confidence
        should_enter = (action in ['buy', 'sell']) and (confidence >= self.confidence_threshold)
        
        if should_enter:
            logger.info(f"Entry signal: {action} with confidence {confidence:.2f}")
        
        return should_enter

    def should_exit(self, market_data: Dict[str, Any], position: Dict[str, Any]) -> bool:
        """
        Determine if we should exit a position.
        Check stop loss, take profit, or reversal signals.
        """
        current_price = market_data.get('close', 0)
        entry_price = position.get('entry_price', current_price)
        position_side = position.get('side', 'long')
        
        # Calculate PnL
        if position_side == 'long':
            pnl_pct = (current_price - entry_price) / entry_price
        else:  # short
            pnl_pct = (entry_price - current_price) / entry_price
        
        # Check stop loss
        if pnl_pct <= -self.stop_loss_pct:
            logger.info(f"Stop loss triggered at {pnl_pct:.2%}")
            return True
        
        # Check take profit
        if pnl_pct >= self.take_profit_pct:
            logger.info(f"Take profit triggered at {pnl_pct:.2%}")
            return True
        
        # Check for reversal signal
        result = self.decision_tower.process_market_data(market_data)
        decision = result['decision']
        action = decision.get('action', 'hold')
        confidence = decision.get('confidence', 0)
        
        # Exit if opposite signal with high confidence
        if position_side == 'long' and action == 'sell' and confidence >= self.confidence_threshold:
            logger.info(f"Reversal signal: sell at confidence {confidence:.2f}")
            return True
        elif position_side == 'short' and action == 'buy' and confidence >= self.confidence_threshold:
            logger.info(f"Reversal signal: buy at confidence {confidence:.2f}")
            return True
        
        return False

    def calculate_position_size(self, balance: float, confidence: float) -> float:
        """
        Dynamic position sizing based on confidence level.
        Higher confidence = larger position size.
        """
        base_size = balance * self.max_position_size
        # Scale by confidence (linear scaling, could be modified)
        size_multiplier = min(confidence / self.confidence_threshold, 1.5)
        position_size = base_size * size_multiplier
        
        logger.debug(f"Calculated position size: {position_size} (multiplier: {size_multiplier:.2f})")
        return position_size

    def get_stop_loss_price(self, entry_price: float, position_side: str) -> float:
        """Calculate stop loss price"""
        return super().calculate_stop_loss(entry_price, position_side)

    def get_take_profit_price(self, entry_price: float, position_side: str) -> float:
        """Calculate take profit price"""
        return super().calculate_take_profit(entry_price, position_side)

    def get_agent_signals(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get individual signals from all agents for transparency"""
        return self.decision_tower.process_market_data(market_data)
