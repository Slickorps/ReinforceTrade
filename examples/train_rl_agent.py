#!/usr/bin/env python3
"""
Train RL Agent Example
This example demonstrates how to train a reinforcement learning agent.
"""

import sys
sys.path.insert(0, '..')

# Windows consoles often use a legacy code page (e.g. GBK) that cannot encode
# emoji glyphs used below; force UTF-8 output where supported.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from environments import TradingEnvironment
from agents import RLAgent, TrainingPipeline
from data import DataLoader
from utils import logger
import numpy as np

def generate_training_data(num_points=500):
    """Generate synthetic data for RL training"""
    np.random.seed(123)
    data = []
    price = 50000
    
    for i in range(num_points):
        # More volatile data for training
        change = np.random.normal(0, 0.02)
        price *= (1 + change)
        
        data.append({
            'timestamp': 1609459200 + i*3600,
            'open': price * (1 + np.random.normal(0, 0.001)),
            'high': price * (1 + abs(np.random.normal(0, 0.012))),
            'low': price * (1 - abs(np.random.normal(0, 0.012))),
            'close': price,
            'volume': 1000 + abs(np.random.normal(0, 400))
        })
    
    return data

def train_rl_agent_example():
    """Example of training an RL agent"""
    logger.info("=" * 60)
    logger.info("RL Agent Training Example")
    logger.info("=" * 60)
    
    # Load or generate data
    logger.info("Loading training data...")
    try:
        data_loader = DataLoader()
        raw_data = data_loader.fetch_historical_data(
            symbol='BTC/USDT',
            timeframe='1h',
            limit=500
        )
        logger.info(f"Loaded {len(raw_data)} data points from exchange")
    except Exception as e:
        logger.warning(f"Using synthetic data: {e}")
        raw_data = generate_training_data(500)
    
    # Split into train and test
    train_size = int(len(raw_data) * 0.8)
    train_data = raw_data[:train_size]
    test_data = raw_data[train_size:]
    
    logger.info(f"Training set: {len(train_data)} points")
    logger.info(f"Test set: {len(test_data)} points")
    
    # Create training environment
    logger.info("Creating trading environment...")
    train_env = TradingEnvironment(
        data=train_data,
        initial_balance=10000,
        transaction_fee=0.001
    )
    
    # Create RL agent
    logger.info("Initializing RL agent (PPO)...")
    rl_agent = RLAgent(agent_type='ppo')
    
    # Train the agent
    logger.info("Starting training (this may take a few minutes)...")
    try:
        rl_agent.train(
            env=train_env,
            total_timesteps=50000,  # Reduce for faster testing
        )
        logger.info("Training completed successfully!")
        
        # Save the model
        rl_agent.save_model()
        
        # Test on test data
        logger.info("Testing on validation data...")
        test_env = TradingEnvironment(
            data=test_data,
            initial_balance=10000,
            transaction_fee=0.001
        )
        
        obs, _ = test_env.reset()
        total_reward = 0
        done = False
        steps = 0
        
        while not done and steps < 1000:
            action, _ = rl_agent.model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = test_env.step(action)
            done = terminated or truncated
            total_reward += reward
            steps += 1
        
        logger.info(f"Test completed: Total reward = {total_reward:.2f}")
        logger.info(f"Final portfolio value: ${info.get('balance', 0):.2f}")
        
    except Exception as e:
        logger.error(f"Training error: {e}")
        logger.info("Note: RL training requires stable-baselines3 and proper environment setup")
        raise
    
    logger.info("=" * 60)
    logger.info("RL Training Example Completed")
    logger.info("=" * 60)

if __name__ == '__main__':
    train_rl_agent_example()
    print("\n✅ RL agent training example completed!")
