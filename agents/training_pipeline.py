from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.results_plotter import plot_results
from environments.trading_env import TradingEnvironment
from data.data_loader import DataLoader
from .rl_agent import RLAgent
from utils.logger import logger
import matplotlib.pyplot as plt
import numpy as np
import os

class TrainingCallback(BaseCallback):
    """
    Callback for monitoring training progress.
    """
    def __init__(self, check_freq: int, save_path: str, verbose: int = 1):
        super().__init__(verbose)
        self.check_freq = check_freq
        self.save_path = save_path
        os.makedirs(save_path, exist_ok=True)

    def _on_step(self) -> bool:
        if self.n_calls % self.check_freq == 0:
            # Save model checkpoint
            model_path = f"{self.save_path}/model_{self.n_calls}_steps.zip"
            self.model.save(model_path)
            logger.info(f"Saved checkpoint at step {self.n_calls}")
        return True

class TrainingPipeline:
    """
    Pipeline for training RL agents on trading data.
    """
    def __init__(self, agent_type: str = 'ppo'):
        self.agent_type = agent_type
        self.data_loader = DataLoader()
        self.agent = RLAgent(agent_type=agent_type)

    def prepare_environment(self, data: List[Dict[str, Any]], initial_balance: float = 10000) -> TradingEnvironment:
        """Create and return trading environment"""
        env = TradingEnvironment(data, initial_balance=initial_balance)
        return env

    def train_on_csv(self, csv_path: str, total_timesteps: int = 50000, test_split: float = 0.2):
        """
        Train agent on data from CSV file.
        """
        logger.info(f"Loading data from {csv_path}")
        raw_data = self.data_loader.load_from_csv(csv_path)
        processed_df = self.data_loader.preprocess_data(raw_data)

        train_data, test_data = self.data_loader.split_train_test(processed_df, train_ratio=1-test_split)

        # Create environment
        env = self.prepare_environment(train_data)

        # Setup callback
        callback = TrainingCallback(check_freq=10000, save_path=f"models/{self.agent_type}")

        # Train agent
        self.agent.train(env, total_timesteps=total_timesteps, callback=callback)

        # Evaluate on test data
        self.evaluate_on_data(test_data)

        logger.info("Training pipeline completed")

    def train_on_exchange_data(self, symbol: str, timeframe: str = '1h', limit: int = 1000,
                              total_timesteps: int = 50000, test_split: float = 0.2):
        """
        Train agent on live exchange data.
        """
        logger.info(f"Fetching data for {symbol} from exchange")
        raw_data = self.data_loader.fetch_historical_data(symbol, timeframe=timeframe, limit=limit)
        processed_df = self.data_loader.preprocess_data(raw_data)

        train_data, test_data = self.data_loader.split_train_test(processed_df, train_ratio=1-test_split)

        env = self.prepare_environment(train_data)
        callback = TrainingCallback(check_freq=10000, save_path=f"models/{self.agent_type}")

        self.agent.train(env, total_timesteps=total_timesteps, callback=callback)
        self.evaluate_on_data(test_data)

        logger.info("Exchange data training completed")

    def evaluate_on_data(self, test_data: List[Dict[str, Any]]):
        """Evaluate trained agent on test data"""
        if not self.agent.model:
            logger.error("No trained model to evaluate")
            return

        env = self.prepare_environment(test_data)

        obs, _ = env.reset()
        total_reward = 0
        done = False

        while not done:
            action, _ = self.agent.model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            total_reward += reward

        logger.info(f"Evaluation completed. Total reward on test data: {total_reward}")

    def plot_training_results(self, log_dir: str = "./logs/"):
        """Plot training results"""
        try:
            plot_results([log_dir], num_timesteps=None, x_axis="timesteps", task_name="training")
            plt.savefig("training_results.png")
            logger.info("Training results plot saved")
        except Exception as e:
            logger.error(f"Error plotting results: {e}")

    def load_and_predict(self, market_data: Dict[str, Any]):
        """Load trained model and make prediction"""
        self.agent.load_model()
        return self.agent.generate_signal({})
