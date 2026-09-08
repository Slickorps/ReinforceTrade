from stable_baselines3 import PPO, A2C, DQN
from stable_baselines3.common.callbacks import BaseCallback
from .base_agent import BaseAgent
from typing import Dict, Any, Optional
from utils.logger import logger
import os
import numpy as np

class RLAgent(BaseAgent):
    """
    Reinforcement Learning agent using Stable Baselines3.
    Can be trained on trading environments and used for signal generation.
    """
    def __init__(self, agent_type: str = 'ppo', model_path: Optional[str] = None):
        super().__init__(f"RLAgent_{agent_type}")
        self.agent_type = agent_type
        self.model_path = model_path or f"models/{agent_type}_model.zip"
        self.model: Optional[Any] = None

        # Ensure models directory exists
        os.makedirs('models', exist_ok=True)

    def load_model(self):
        """Load pre-trained model"""
        if os.path.exists(self.model_path):
            if self.agent_type.upper() == 'PPO':
                self.model = PPO.load(self.model_path)
            elif self.agent_type.upper() == 'A2C':
                self.model = A2C.load(self.model_path)
            elif self.agent_type.upper() == 'DQN':
                self.model = DQN.load(self.model_path)
            logger.info(f"Loaded model from {self.model_path}")
        else:
            logger.warning(f"Model file {self.model_path} not found")

    def save_model(self):
        """Save trained model"""
        if self.model:
            self.model.save(self.model_path)
            logger.info(f"Saved model to {self.model_path}")

    def train(self, env, total_timesteps: int = 100000, callback: Optional[BaseCallback] = None):
        """
        Train the RL agent on the given environment.
        """
        logger.info(f"Starting training for {total_timesteps} timesteps")

        if self.agent_type.upper() == 'PPO':
            model = PPO('MlpPolicy', env, verbose=1)
        elif self.agent_type.upper() == 'A2C':
            model = A2C('MlpPolicy', env, verbose=1)
        elif self.agent_type.upper() == 'DQN':
            model = DQN('MlpPolicy', env, verbose=1)
        else:
            raise ValueError(f"Unsupported agent type: {self.agent_type}")

        self.model = model
        model.learn(total_timesteps=total_timesteps, callback=callback)
        self.save_model()
        logger.info("Training completed")

    def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market data (not used in RL, kept for interface)"""
        return {"rl_analysis": "RL agents use direct action prediction"}

    def generate_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trading signal using trained RL model"""
        if not self.model:
            self.load_model()
            if not self.model:
                logger.error("No trained model available")
                return {"signal": "hold", "strength": 0}

        # Create observation from the analysis payload (may hold price history)
        obs = self._create_observation(analysis)

        # Get action from model
        action, _ = self.model.predict(obs, deterministic=True)

        # Convert action to signal
        if action == 0:  # hold
            signal = "hold"
            strength = 0.0
        elif action == 1:  # buy
            signal = "buy"
            strength = 0.8
        elif action == 2:  # sell
            signal = "sell"
            strength = 0.8
        else:
            signal = "hold"
            strength = 0.0

        return {"signal": signal, "strength": strength, "action": action}

    def _create_observation(self, market_data: Dict[str, Any]) -> np.ndarray:
        """Create observation array from market data"""
        # Simplified observation - extend based on your needs
        prices = market_data.get('prices', [])
        if not prices:
            return np.zeros(4)  # Same as TradingEnvironment observation space

        current_price = prices[-1]['close']
        volume = prices[-1].get('volume', 0)

        # Mock balance and position for prediction (in real trading these would be actual values)
        balance = 10000
        position = 0

        return np.array([balance, position, current_price, volume], dtype=np.float32)
