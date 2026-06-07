# ReinforceTrade API Reference

Complete API documentation for the ReinforceTrade multi-agent trading system.

## Table of Contents

- [Core Components](#core-components)
- [Agents Module](#agents-module)
- [Strategies Module](#strategies-module)
- [Backtesting Module](#backtesting-module)
- [Environments Module](#environments-module)
- [Data Module](#data-module)
- [Optimization Module](#optimization-module)
- [Reports Module](#reports-module)
- [Trading Module](#trading-module)
- [Monitoring Module](#monitoring-module)
- [ML Factor Engine](#ml-factor-engine)
- [Configuration](#configuration)

---

## Core Components

### TradingBot

Main orchestrator for live trading operations.

```python
class TradingBot:
    def __init__(
        self,
        strategy: BaseStrategy,
        exchange: Exchange,
        risk_manager: RiskManager,
        symbols: List[str]
    )
```

**Parameters:**
- `strategy` (`BaseStrategy`): Trading strategy instance
- `exchange` (`Exchange`): Exchange interface for order execution
- `risk_manager` (`RiskManager`): Risk management system
- `symbols` (`List[str]`): List of trading pairs to monitor

**Methods:**

#### `run_backtest(historical_data: List[Dict]) -> Dict`
Run backtest on historical data.

**Returns:** Backtest results dictionary with performance metrics.

#### `run_live(interval: int = 60)`
Start live trading loop.

**Parameters:**
- `interval` (`int`): Seconds between trading cycles (default: 60)

#### `stop()`
Stop live trading gracefully.

---

## Agents Module

### BaseAgent

Abstract base class for all agents.

```python
class BaseAgent(ABC):
    def __init__(self, name: str)
```

**Methods:**

#### `analyze(market_data: Dict[str, Any]) -> Dict[str, Any]` [abstract]
Analyze market data and return analysis results.

**Parameters:**
- `market_data` (`Dict`): Dictionary containing price history and indicators

**Returns:** Analysis dictionary with agent-specific metrics.

#### `generate_signal(analysis: Dict[str, Any]) -> Dict[str, Any]` [abstract]
Generate trading signal based on analysis.

**Returns:** Signal dictionary with `signal` and `strength` keys.

---

### EnvironmentAgent

Monitors market conditions and identifies volatility/trend.

```python
class EnvironmentAgent(BaseAgent):
    def __init__(
        self,
        volatility_window: int = 20,
        trend_window: int = 50
    )
```

**Parameters:**
- `volatility_window` (`int`): Window for volatility calculation (default: 20)
- `trend_window` (`int`): Window for trend detection (default: 50)

**Analysis Output:**
```python
{
    "volatility": 0.15,        # Current volatility (0-1 scale)
    "trend": "bullish",        # "bullish", "bearish", or "neutral"
    "regime": "trending",      # "trending", "ranging", "volatile"
    "market_health": 0.82      # Overall market condition (0-1)
}
```

**Signal Output:**
```python
{
    "signal": "bullish",       # "bullish", "bearish", "neutral"
    "strength": 0.75,         # Confidence level (0-1)
    "message": "Low volatility uptrend detected"
}
```

---

### ShortTermAgent

Generates short-term momentum-based trading signals.

```python
class ShortTermAgent(BaseAgent):
    def __init__(
        self,
        momentum_window: int = 10,
        threshold: float = 0.02
    )
```

**Parameters:**
- `momentum_window` (`int`): Window for momentum calculation (default: 10)
- `threshold` (`float`): Minimum momentum to trigger signal (default: 0.02)

**Analysis Output:**
```python
{
    "momentum": 0.035,         # Rate of change
    "volume_ratio": 1.5,       # Volume vs average
    "rsi": 65.0,              # RSI value
    "support": 48000,         # Support level
    "resistance": 52000       # Resistance level
}
```

**Signal Output:**
```python
{
    "signal": "buy",           # "buy", "sell", or "hold"
    "strength": 0.85,         # Confidence level (0-1)
    "entry_zone": [49500, 50000],
    "timeframe": "1h"
}
```

---

### TrendAgent

Provides macro-level trend direction analysis.

```python
class TrendAgent(BaseAgent):
    def __init__(
        self,
        fast_ma: int = 20,
        slow_ma: int = 50
    )
```

**Parameters:**
- `fast_ma` (`int`): Fast moving average period (default: 20)
- `slow_ma` (`int`): Slow moving average period (default: 50)

**Analysis Output:**
```python
{
    "trend_strength": 0.08,    # Trend strength indicator
    "ma_alignment": "bullish", # "bullish" (fast > slow), "bearish", "neutral"
    "support_levels": [45000, 42000],
    "resistance_levels": [55000, 58000],
    "pattern": "higher_highs"  # Detected pattern
}
```

**Signal Output:**
```python
{
    "signal": "long",          # "long", "short", or "neutral"
    "strength": 0.72,         # Confidence level (0-1)
    "duration": "medium",    # Expected trend duration
    "expected_return": 0.12   # Predicted return
}
```

---

### DecisionTower

Central control tower that aggregates agent signals.

```python
class DecisionTower:
    def __init__(
        self,
        agents: List[BaseAgent],
        weights: Dict[str, float] = None
    )
```

**Parameters:**
- `agents` (`List[BaseAgent]`): List of agent instances
- `weights` (`Dict[str, float]`): Optional custom weights for each agent

**Methods:**

#### `process_market_data(market_data: Dict) -> Dict`
Process market data through all agents and make decision.

**Returns:**
```python
{
    "analyses": {
        "EnvironmentAgent": {...},
        "ShortTermAgent": {...},
        "TrendAgent": {...}
    },
    "signals": {
        "EnvironmentAgent": {"signal": "bullish", "strength": 0.8},
        "ShortTermAgent": {"signal": "buy", "strength": 0.9},
        "TrendAgent": {"signal": "long", "strength": 0.7}
    },
    "decision": {
        "action": "buy",         # Final action
        "confidence": 0.82,      # Aggregated confidence
        "scores": {              # Individual action scores
            "buy": 2.4,
            "sell": 0.3,
            "hold": 0.8
        }
    }
}
```

#### `aggregate_signals(signals: Dict) -> Dict`
Aggregate signals using weighted voting.

#### `set_agent_weights(weights: Dict[str, float])`
Update agent weights dynamically.

**Example:**
```python
tower.set_agent_weights({
    'EnvironmentAgent': 0.20,
    'ShortTermAgent': 0.25,
    'TrendAgent': 0.25,
    'RLAgent': 0.30
})
```

---

### RLAgent

Reinforcement learning agent using Stable Baselines3.

```python
class RLAgent(BaseAgent):
    def __init__(
        self,
        agent_type: str = 'ppo',
        model_path: str = None
    )
```

**Parameters:**
- `agent_type` (`str`): RL algorithm type ('ppo', 'a2c', 'dqn')
- `model_path` (`str`): Path to save/load model file

**Methods:**

#### `train(env: TradingEnvironment, total_timesteps: int, callback: BaseCallback = None)`
Train the RL agent on a trading environment.

**Parameters:**
- `env` (`TradingEnvironment`): Trading environment instance
- `total_timesteps` (`int`): Number of training steps
- `callback` (`BaseCallback`): Optional training callback

**Example:**
```python
from agents import RLAgent
from environments import TradingEnvironment

rl_agent = RLAgent(agent_type='ppo')
env = TradingEnvironment(data, initial_balance=10000)

rl_agent.train(env, total_timesteps=100000)
rl_agent.save_model()
```

#### `load_model()`
Load pre-trained model from disk.

#### `save_model()`
Save current model to disk.

---

### TrainingPipeline

High-level pipeline for training RL agents.

```python
class TrainingPipeline:
    def __init__(self, agent_type: str = 'ppo')
```

**Methods:**

#### `train_on_csv(csv_path: str, total_timesteps: int = 50000, test_split: float = 0.2)`
Train agent on data from CSV file.

**Parameters:**
- `csv_path` (`str`): Path to CSV file with OHLCV data
- `total_timesteps` (`int`): Training steps
- `test_split` (`float`): Fraction of data for testing (default: 0.2)

#### `train_on_exchange_data(symbol: str, timeframe: str = '1h', limit: int = 1000, total_timesteps: int = 50000)`
Train agent on live exchange data.

**Example:**
```python
from agents import TrainingPipeline

pipeline = TrainingPipeline(agent_type='ppo')
pipeline.train_on_exchange_data(
    symbol='BTC/USDT',
    timeframe='1h',
    limit=5000,
    total_timesteps=100000
)
```

---

## Strategies Module

### BaseStrategy

Abstract base class for all trading strategies.

```python
class BaseStrategy(ABC):
    def __init__(self, name: str)
```

**Methods:**

#### `should_enter(market_data: Dict) -> bool` [abstract]
Determine if strategy should enter a position.

#### `should_exit(market_data: Dict, position: Dict) -> bool` [abstract]
Determine if strategy should exit a position.

#### `calculate_stop_loss(entry_price: float, position_side: str) -> float`
Calculate stop loss price.

#### `calculate_take_profit(entry_price: float, position_side: str) -> float`
Calculate take profit price.

---

### MultiAgentStrategy

Multi-agent trading strategy with integrated risk management.

```python
class MultiAgentStrategy(BaseStrategy):
    def __init__(
        self,
        use_rl: bool = True,
        confidence_threshold: float = 0.6,
        max_position_size: float = 0.1,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.10
    )
```

**Parameters:**
- `use_rl` (`bool`): Include RL agent in decision making
- `confidence_threshold` (`float`): Minimum confidence to trade (0-1)
- `max_position_size` (`float`): Maximum position as fraction of balance (0-1)
- `stop_loss_pct` (`float`): Stop loss percentage (0-1)
- `take_profit_pct` (`float`): Take profit percentage (0-1)

**Methods:**

#### `should_enter(market_data: Dict) -> bool`
Check if entry conditions are met.

Returns `True` if:
- Decision confidence >= threshold
- Risk limits not exceeded

#### `should_exit(market_data: Dict, position: Dict) -> bool`
Check if exit conditions are met.

Returns `True` if:
- Stop loss triggered
- Take profit triggered
- Reversal signal with high confidence

#### `calculate_position_size(balance: float, confidence: float) -> float`
Calculate optimal position size based on risk parameters.

**Example:**
```python
from strategies import MultiAgentStrategy

strategy = MultiAgentStrategy(
    use_rl=True,
    confidence_threshold=0.65,
    max_position_size=0.1,
    stop_loss_pct=0.05,
    take_profit_pct=0.10
)

# Check entry
market_data = {'prices': [...], 'close': 50000}
if strategy.should_enter(market_data):
    size = strategy.calculate_position_size(10000, 0.8)
```

---

### RiskManager

Risk management and position sizing system.

```python
class RiskManager:
    def __init__(
        self,
        max_risk_per_trade: float = 0.01,
        max_portfolio_risk: float = 0.05,
        max_correlation: float = 0.7
    )
```

**Parameters:**
- `max_risk_per_trade` (`float`): Maximum risk per trade as fraction (default: 0.01 = 1%)
- `max_portfolio_risk` (`float`): Maximum total portfolio risk (default: 0.05 = 5%)
- `max_correlation` (`float`): Maximum correlation between positions (default: 0.7)

**Methods:**

#### `calculate_position_size(balance: float, entry_price: float, stop_loss: float, confidence: float) -> float`
Calculate position size using Kelly Criterion.

**Formula:**
```
position_size = (balance × risk_per_trade × confidence × kelly_fraction) / price_risk
```

#### `check_exposure(symbol: str, new_position_value: float, total_portfolio_value: float) -> bool`
Check if new position would exceed exposure limits.

**Returns:** `True` if trade is allowed, `False` if rejected.

#### `record_trade(trade: Dict)`
Record completed trade for risk analysis.

#### `get_risk_metrics() -> Dict`
Get current risk metrics.

**Returns:**
```python
{
    "total_trades": 100,
    "win_rate": 0.62,
    "avg_profit": 1250.50,
    "avg_loss": -420.30,
    "max_drawdown": 0.15,
    "risk_reward_ratio": 2.97,
    "current_exposure": {"BTC": 15000, "ETH": 8000},
    "total_exposure": 23000
}
```

#### `should_reduce_exposure(consecutive_losses: int = 3) -> bool`
Check if exposure should be reduced due to consecutive losses.

#### `get_dynamic_stop_loss(volatility: float, base_stop: float = 0.05) -> float`
Adjust stop loss based on market volatility.

---

## Backtesting Module

### Backtester

Basic backtesting engine.

```python
class Backtester:
    def __init__(
        self,
        strategy: BaseStrategy,
        initial_balance: float = 10000
    )
```

**Methods:**

#### `run(market_data: List[Dict]) -> Dict`
Run backtest on historical data.

**Parameters:**
- `market_data` (`List[Dict]`): List of OHLCV dictionaries

**Returns:**
```python
{
    "initial_balance": 10000.0,
    "final_balance": 12500.0,
    "total_return": 0.25,        # 25% return
    "total_trades": 50,
    "winning_trades": 30,
    "losing_trades": 20,
    "win_rate": 0.60,
    "avg_profit": 150.0,
    "avg_loss": -75.0,
    "largest_profit": 500.0,
    "largest_loss": -300.0,
    "total_pnl": 2500.0,
    "trades": [...]              # List of all trades
}
```

---

### EnhancedBacktester

Advanced backtester with risk management and visualization.

```python
class EnhancedBacktester(Backtester):
    def __init__(
        self,
        strategy: MultiAgentStrategy,
        initial_balance: float = 10000,
        risk_manager: RiskManager = None
    )
```

**Methods:**

#### `run(market_data: List[Dict]) -> Dict`
Run enhanced backtest.

**Additional Returns:**
```python
{
    # ... basic metrics ...
    "sharpe_ratio": 1.85,
    "max_drawdown": 0.12,        # 12% max drawdown
    "max_drawdown_pct": 12.0,
    "calmar_ratio": 2.08,
    "profit_factor": 1.75,
    "equity_curve": [...],       # Per-step equity values
    "drawdown_periods": [...],   # Drawdown analysis
    "agent_signals_history": [...]  # Agent decisions
}
```

#### `generate_report(save_path: str = "reports/backtest_report.json")`
Generate comprehensive backtest report with visualizations.

---

## Environments Module

### TradingEnvironment

OpenAI Gym-compatible trading environment for RL training.

```python
class TradingEnvironment(gym.Env):
    def __init__(
        self,
        data: List[Dict],
        initial_balance: float = 10000,
        transaction_fee: float = 0.001,
        max_position: float = 1.0
    )
```

**Parameters:**
- `data` (`List[Dict]`): OHLCV price data
- `initial_balance` (`float`): Starting capital
- `transaction_fee` (`float`): Transaction cost per trade (default: 0.001)
- `max_position` (`float`): Maximum position size (default: 1.0)

**Action Space:**
```python
# Discrete: 0 = Hold, 1 = Buy, 2 = Sell
self.action_space = spaces.Discrete(3)
```

**Observation Space:**
```python
# Continuous: [balance, position, current_price, volume]
self.observation_space = spaces.Box(
    low=0, high=np.inf, shape=(4,), dtype=np.float32
)
```

**Methods:**

#### `reset() -> np.ndarray`
Reset environment to initial state.

**Returns:** Initial observation.

#### `step(action: int) -> Tuple[np.ndarray, float, bool, Dict]`
Execute one timestep.

**Parameters:**
- `action` (`int`): 0=Hold, 1=Buy, 2=Sell

**Returns:**
- `observation` (`np.ndarray`): New state
- `reward` (`float`): Reward for action
- `done` (`bool`): Whether episode ended
- `info` (`Dict`): Additional information

**Example:**
```python
from environments import TradingEnvironment

env = TradingEnvironment(data, initial_balance=10000)
obs = env.reset()

for _ in range(1000):
    action = 1  # Buy
    obs, reward, done, info = env.step(action)
    if done:
        break
```

---

## Data Module

### DataLoader

Handles loading and preprocessing of historical market data.

```python
class DataLoader:
    def __init__(
        self,
        exchange_name: str = 'binance',
        api_key: str = None,
        secret: str = None
    )
```

**Methods:**

#### `load_from_csv(filepath: str, date_column: str = 'timestamp') -> List[Dict]`
Load data from CSV file.

**Expected CSV Format:**
```
timestamp,open,high,low,close,volume
1609459200,50000,51000,49500,50500,1500
```

#### `fetch_historical_data(symbol: str, timeframe: str = '1h', limit: int = 1000, start_date: str = None) -> List[Dict]`
Fetch historical data from exchange.

**Parameters:**
- `symbol` (`str`): Trading pair (e.g., 'BTC/USDT')
- `timeframe` (`str`): Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
- `limit` (`int`): Number of candles to fetch
- `start_date` (`str`): Optional start date (ISO format)

**Returns:** List of OHLCV dictionaries.

#### `preprocess_data(data: List[Dict], add_technical_indicators: bool = True) -> pd.DataFrame`
Preprocess raw data and add technical indicators.

**Added Indicators:**
- SMA 20, SMA 50
- RSI (14 period)
- MACD
- Bollinger Bands

**Returns:** Pandas DataFrame with indicators.

#### `split_train_test(data: pd.DataFrame, train_ratio: float = 0.8) -> Tuple[List, List]`
Split data into training and testing sets.

**Example:**
```python
from data import DataLoader

data_loader = DataLoader(exchange_name='binance')

# Fetch from exchange
data = data_loader.fetch_historical_data('BTC/USDT', timeframe='1h', limit=5000)

# Preprocess
df = data_loader.preprocess_data(data)

# Split
train_data, test_data = data_loader.split_train_test(df, train_ratio=0.8)
```

---

## Optimization Module

### StrategyOptimizer

Strategy parameter optimization using grid search and genetic algorithms.

```python
class StrategyOptimizer:
    def __init__(
        self,
        data: List[Dict],
        initial_balance: float = 10000
    )
```

**Methods:**

#### `grid_search(param_grid: Dict[str, List], metric: str = 'sharpe_ratio') -> Tuple[Dict, float]`
Perform grid search over parameter space.

**Parameters:**
- `param_grid` (`Dict`): Parameter names mapped to list of values
- `metric` (`str`): Metric to optimize ('sharpe_ratio', 'total_return', 'win_rate', 'calmar_ratio', 'combined')

**Returns:** `(best_params, best_score)`

**Example:**
```python
from optimization import StrategyOptimizer

param_grid = {
    'confidence_threshold': [0.5, 0.6, 0.7],
    'stop_loss_pct': [0.03, 0.05, 0.07],
    'take_profit_pct': [0.08, 0.10, 0.12]
}

optimizer = StrategyOptimizer(data, initial_balance=10000)
best_params, best_score = optimizer.grid_search(param_grid, metric='sharpe_ratio')
```

#### `genetic_algorithm(param_bounds: Dict[str, Tuple], population_size: int = 20, generations: int = 10, mutation_rate: float = 0.1, metric: str = 'sharpe_ratio') -> Tuple[Dict, float]`
Optimize parameters using genetic algorithm.

**Parameters:**
- `param_bounds` (`Dict`): Parameter names mapped to (min, max) tuples
- `population_size` (`int`): Number of individuals in population
- `generations` (`int`): Number of generations to evolve
- `mutation_rate` (`float`): Probability of mutation (0-1)
- `metric` (`str`): Optimization metric

**Example:**
```python
param_bounds = {
    'confidence_threshold': (0.5, 0.9),
    'stop_loss_pct': (0.02, 0.10),
    'take_profit_pct': (0.05, 0.20)
}

best_params, best_score = optimizer.genetic_algorithm(
    param_bounds,
    population_size=20,
    generations=10,
    metric='combined'
)
```

#### `save_results(output_path: str = "optimization/results.json")`
Save optimization results to file.

#### `get_optimization_report() -> str`
Generate human-readable optimization report.

---

### WalkForwardValidator

Walk-forward validation for strategy robustness testing.

```python
class WalkForwardValidator:
    def __init__(
        self,
        data: List[Dict],
        train_size: int = 1000,
        test_size: int = 300
    )
```

**Methods:**

#### `run_walk_forward(param_grid: Dict = None, optimization_method: str = 'grid', metric: str = 'sharpe_ratio') -> Dict`
Run walk-forward validation with rolling window.

**Process:**
1. Train on in-sample data (optimization)
2. Test on out-of-sample data (validation)
3. Roll window forward and repeat

**Returns:**
```python
{
    "window_results": [...],    # Results for each window
    "aggregate": {
        "avg_oos_return": 0.15,
        "avg_oos_sharpe": 1.25,
        "consistency_score": 0.82,
        "overfitting_score": 0.15,
        "robustness_score": 0.75,
        "positive_windows": 8,
        "total_windows": 10
    },
    "is_robust": True         # Whether strategy is robust
}
```

#### `save_validation_report(output_path: str)`
Save validation report to file.

#### `get_validation_summary() -> str`
Get human-readable validation summary.

---

## Reports Module

### ReportGenerator

Generates comprehensive backtest reports with visualizations.

```python
class ReportGenerator:
    def __init__(self, output_dir: str = "reports")
```

**Methods:**

#### `generate_full_report(results: Dict, strategy_name: str = "MultiAgentStrategy") -> str`
Generate complete HTML report with all metrics and visualizations.

**Parameters:**
- `results` (`Dict`): Backtest results from EnhancedBacktester
- `strategy_name` (`str`): Name of strategy for report title

**Returns:** Path to generated report directory.

**Generated Files:**
- `report.html` - Main HTML report
- `equity_curve.png` - Equity curve visualization
- `drawdown.png` - Drawdown analysis
- `trade_distribution.png` - Trade distribution histogram
- `monthly_returns.png` - Monthly returns chart
- `cumulative_returns.png` - Cumulative returns chart
- `data.json` - Raw data export

**Example:**
```python
from reports import ReportGenerator
from backtesting import EnhancedBacktester

# Run backtest
backtester = EnhancedBacktester(strategy, 10000)
results = backtester.run(data)

# Generate report
report_gen = ReportGenerator(output_dir="reports")
report_dir = report_gen.generate_full_report(results, "MyStrategy")

print(f"Report available at: {report_dir}/report.html")
```

---

## Trading Module

### Exchange (Abstract)

Abstract base class for exchange integration.

```python
class Exchange(ABC):
    @abstractmethod
    def get_balance(self) -> Dict[str, float]
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict[str, Any]
    
    @abstractmethod
    def place_order(self, symbol: str, side: str, amount: float, 
                   order_type: str = 'market', price: float = None) -> Dict[str, Any]
```

**Implementations:**
- `CCXTExchange` — CCXT-based multi-exchange adapter (Binance, Coinbase, etc.)
- `IBAdapter` — Interactive Brokers TWS/Gateway adapter
- `OANDAdapter` — OANDA REST API adapter for forex trading

### BrokerFactory

Unified broker adapter instantiation from configuration.

```python
from trading.broker_factory import create_exchange, list_supported_brokers

# Create CCXT exchange
exchange = create_exchange({"name": "ccxt", "exchange_id": "binance",
                             "api_key": "...", "secret": "..."})
# Create IB adapter
exchange = create_exchange({"name": "ib", "host": "127.0.0.1",
                             "port": 7497, "client_id": 1})
# Create OANDA adapter
exchange = create_exchange({"name": "oanda", "api_key": "...",
                             "environment": "practice", "account_id": "..."})

# List available brokers
print(list_supported_brokers())  # ['ccxt', 'ib', 'oanda']
```

### WebSocketClient

Real-time market data stream via WebSocket.

```python
from trading.websocket_client import WebSocketClient

client = WebSocketClient(symbols=['BTC/USDT'], exchange_name='binance')
client.on_message = lambda msg: print(f"Price update: {msg}")
client.start()
```

### OrderManager

Order lifecycle management with status tracking.

```python
from trading.order_manager import OrderManager

manager = OrderManager(exchange)
order = manager.place_order(symbol='BTC/USDT', side='buy', amount=0.01)
status = manager.get_status(order['id'])
manager.cancel(order['id'])
```

### PositionTracker

Real-time position tracking with P&L calculation.

```python
from trading.position_tracker import PositionTracker

tracker = PositionTracker()
tracker.update('BTC/USDT', quantity=0.01, entry_price=50000.0, side='long')
pnl = tracker.get_unrealized_pnl('BTC/USDT', current_price=52000.0)
metrics = tracker.get_summary()
```

## Monitoring Module

### TradeMonitor

Real-time trade monitoring and metrics collection.

```python
from monitoring import TradeMonitor

monitor = TradeMonitor()
monitor.start()

# Events are tracked automatically
monitor.get_active_trades()
monitor.get_today_pnl()
monitor.get_win_rate()
```

### AlertManager

Configurable alerting with multiple channels (email, Slack, Telegram).

```python
from monitoring import AlertManager

alerts = AlertManager()
alerts.add_rule("max_drawdown", threshold=-0.10, action="halt_trading")
alerts.add_rule("api_error", max_count=3, window_seconds=60, action="notify")
```

### MetricsCollector & PerformanceTracker

Prometheus-compatible metrics collection and performance analysis.

```python
from monitoring import MetricsCollector, PerformanceTracker

collector = MetricsCollector()
collector.record_trade(trade_dict)

tracker = PerformanceTracker()
tracker.calculate_sharpe(returns_series)
tracker.calculate_max_drawdown(equity_curve)
```

## ML Factor Engine

### MLFactor

sklearn pipeline wrapper for ML-based signal generation.

```python
from ml import MLFactor

# Create with preset
mf = MLFactor(preset="rf_classifier")
mf.add_feature("momentum", lambda df: df["close"].pct_change(20))
mf.add_feature("volatility", lambda df: df["close"].pct_change().rolling(20).std())

# Train and predict
mf.fit(X_train, y_train)
probs = mf.predict_proba(X_test)
mf.save("models/my_model.joblib")
```

**Presets**: `rf_classifier`, `gb_classifier`, `lr_classifier`, `rf_regressor`, `gb_regressor`, `ridge_regressor`

### WalkForwardCV

Time-series-aware walk-forward validation.

```python
from ml import WalkForwardCV

cv = WalkForwardCV(n_splits=5, train_size=252, test_size=63)

for train_idx, test_idx in cv.split(X):
    # Train on train_idx, evaluate on test_idx
    pass
```

### MLFactorRouter

High-level API for multi-model management.

```python
from ml import MLFactorRouter

router = MLFactorRouter(model_dir="models")
record = router.train(X, y, preset="rf_classifier", name="btc_momentum")
predictions = router.predict("btc_momentum", X_new)
models = router.list_models()
router.delete_model("btc_momentum")
```

### FactorPipeline

Composable alpha factor pipeline.

```python
from ml.factor_pipeline import FactorPipeline

pipeline = FactorPipeline(weights={"momentum": 0.5, "volatility": 0.25, "sentiment": 0.25})
signal = pipeline.compute(market_data)  # {"composite": 0.65, ...}
```

### Individual Factors

- `MomentumFactor(roc_period=14, rsi_period=14)` — ROC, MACD, RSI signals
- `VolatilityFactor(atr_period=14, hist_period=50)` — ATR, regime classification
- `SentimentFactor(lookback=20)` — Volume trend, buy/sell pressure

---

## Configuration

### Settings

Pydantic-based configuration management.

```python
from config import settings

# Access settings
print(settings.database_url)
print(settings.exchange_api_key)
print(settings.log_level)
```

**Environment Variables:**
```env
DATABASE_URL=sqlite:///reinforcetrade.db
EXCHANGE_API_KEY=your_api_key
EXCHANGE_SECRET=your_secret
EXCHANGE_NAME=binance
LOG_LEVEL=INFO
```

---

## Utility Functions

### Logger

Centralized logging with Loguru.

```python
from utils import logger

# Different log levels
logger.debug("Debug message")
logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
```

**Log Output:**
- Console output (colored)
- File output: `logs/reinforcetrade.log`

---

## Quick Reference

### Common Patterns

#### Pattern 1: Simple Backtest
```python
from data import DataLoader
from strategies import MultiAgentStrategy
from backtesting import EnhancedBacktester

data = DataLoader().fetch_historical_data('BTC/USDT', '1h', 1000)
strategy = MultiAgentStrategy(use_rl=False)
results = EnhancedBacktester(strategy, 10000).run(data)
```

#### Pattern 2: Train and Deploy RL
```python
from agents import TrainingPipeline
from environments import TradingEnvironment

pipeline = TrainingPipeline('ppo')
pipeline.train_on_exchange_data('BTC/USDT', total_timesteps=100000)
```

#### Pattern 3: Optimize Strategy
```python
from optimization import StrategyOptimizer

optimizer = StrategyOptimizer(data)
best_params, _ = optimizer.grid_search(param_grid)
```

#### Pattern 4: Validate Robustness
```python
from optimization import WalkForwardValidator

validator = WalkForwardValidator(data, train_size=1000, test_size=300)
results = validator.run_walk_forward(param_grid)
```

---

## Type Definitions

### Market Data Format
```python
MarketData = Dict[str, Any]  # Contains 'prices' key with OHLCV list

OHLCV = {
    "timestamp": int,      # Unix timestamp
    "open": float,
    "high": float,
    "low": float,
    "close": float,
    "volume": float
}
```

### Signal Format
```python
Signal = {
    "signal": str,         # "buy", "sell", "hold", "long", "short"
    "strength": float,     # 0.0 to 1.0
    "confidence": float   # 0.0 to 1.0
}
```

### Trade Format
```python
Trade = {
    "entry_price": float,
    "exit_price": float,
    "amount": float,
    "pnl": float,
    "return_pct": float,
    "side": str,          # "long" or "short"
    "entry_time": int,
    "exit_time": int
}
```

---

For more examples and usage patterns, see the [Getting Started Guide](getting_started.md).
