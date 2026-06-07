# Getting Started with ReinforceTrade

This guide will walk you through setting up ReinforceTrade and running your first backtest.

## Prerequisites

- Python 3.8 or higher
- Git
- A code editor (VSCode, PyCharm, etc.)
- (Optional) Exchange API keys for live trading

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/reinforcetrade.git
cd reinforcetrade
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `pandas`, `numpy`: Data processing
- `stable-baselines3`: Reinforcement learning
- `ccxt`: Exchange API integration
- `matplotlib`, `seaborn`: Visualization
- `pydantic`: Configuration management
- `loguru`: Logging

### Step 4: Configure Environment

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Exchange API (optional for backtesting, required for live trading)
EXCHANGE_API_KEY=your_api_key_here
EXCHANGE_SECRET=your_secret_here
EXCHANGE_NAME=binance

# Database
DATABASE_URL=sqlite:///reinforcetrade.db

# Logging
LOG_LEVEL=INFO

# Trading Parameters
MAX_POSITION_SIZE=0.1
RISK_PER_TRADE=0.01
```

**Security Note**: Never commit your `.env` file to version control. It's already in `.gitignore`.

## Quick Start: Your First Backtest

### Step 1: Prepare Historical Data

Download sample data or fetch from exchange:

```python
from data import DataLoader

# Initialize data loader
data_loader = DataLoader(exchange_name='binance')

# Fetch historical data for Bitcoin
symbol = 'BTC/USDT'
timeframe = '1h'  # 1-hour candles
limit = 5000      # Number of candles

data = data_loader.fetch_historical_data(
    symbol=symbol,
    timeframe=timeframe,
    limit=limit
)

print(f"Fetched {len(data)} data points")
```

### Step 2: Run a Simple Backtest

```python
from strategies import MultiAgentStrategy
from backtesting import EnhancedBacktester
from strategies import RiskManager

# Create strategy
strategy = MultiAgentStrategy(
    use_rl=True,                  # Use RL agent
    confidence_threshold=0.6      # Minimum confidence to trade
)

# Create risk manager
risk_manager = RiskManager(
    max_risk_per_trade=0.01,      # 1% risk per trade
    max_portfolio_risk=0.05       # 5% max portfolio risk
)

# Create backtester
backtester = EnhancedBacktester(
    strategy=strategy,
    initial_balance=10000,         # $10,000 starting capital
    risk_manager=risk_manager
)

# Run backtest
results = backtester.run(data)

# Print summary
print(f"Total Return: {results['total_return_pct']:.2f}%")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
print(f"Win Rate: {results['win_rate_pct']:.1f}%")
print(f"Max Drawdown: {results['max_drawdown_pct']:.2f}%")
print(f"Total Trades: {results['total_trades']}")
```

### Step 3: Generate Visual Report

```python
from reports import ReportGenerator

# Create report generator
report_gen = ReportGenerator(output_dir="reports")

# Generate full HTML report
report_dir = report_gen.generate_full_report(
    results=results,
    strategy_name="MultiAgentStrategy"
)

print(f"Report generated at: {report_dir}/report.html")
```

Open `reports/report_TIMESTAMP/report.html` in your browser to see:
- Equity curve with buy/sell points
- Drawdown analysis
- Trade distribution
- Agent decision transparency
- Performance metrics dashboard

## Training RL Agents

### Step 1: Prepare Training Environment

```python
from environments import TradingEnvironment
from agents import RLAgent
from data import DataLoader

# Load and preprocess data
data_loader = DataLoader()
data = data_loader.fetch_historical_data('BTC/USDT', timeframe='1h', limit=5000)
processed_df = data_loader.preprocess_data(data)
train_data, test_data = data_loader.split_train_test(processed_df, train_ratio=0.8)

# Create training environment
env = TradingEnvironment(
    data=train_data,
    initial_balance=10000,
    transaction_fee=0.001  # 0.1% fee
)
```

### Step 2: Train the RL Agent

```python
from agents import RLAgent

# Create RL agent
rl_agent = RLAgent(agent_type='ppo')

# Train the agent
rl_agent.train(
    env=env,
    total_timesteps=100000,    # Training steps
    check_freq=10000           # Save checkpoint every 10k steps
)

print("Training completed!")
```

### Step 3: Evaluate on Test Data

```python
from backtesting import EnhancedBacktester

# Create strategy with trained RL agent
strategy = MultiAgentStrategy(use_rl=True)

# Run backtest on test data
backtester = EnhancedBacktester(strategy, initial_balance=10000)
results = backtester.run(test_data)

# Generate report
report_gen.generate_full_report(results, strategy_name="Trained_RL_Strategy")
```

## Strategy Optimization

### Grid Search

```python
from optimization import StrategyOptimizer

# Define parameter grid
param_grid = {
    'confidence_threshold': [0.5, 0.6, 0.7, 0.8],
    'stop_loss_pct': [0.03, 0.05, 0.07],
    'take_profit_pct': [0.08, 0.10, 0.15],
    'max_position_size': [0.05, 0.10, 0.15]
}

# Create optimizer
optimizer = StrategyOptimizer(data, initial_balance=10000)

# Run grid search
best_params, best_score = optimizer.grid_search(
    param_grid=param_grid,
    metric='sharpe_ratio'  # Optimize for Sharpe ratio
)

print(f"Best Parameters: {best_params}")
print(f"Best Score: {best_score:.4f}")

# Save results
optimizer.save_results("optimization/grid_search_results.json")
```

### Genetic Algorithm

```python
# Define parameter bounds for genetic algorithm
param_bounds = {
    'confidence_threshold': (0.5, 0.9),
    'stop_loss_pct': (0.02, 0.10),
    'take_profit_pct': (0.05, 0.20),
    'max_position_size': (0.05, 0.20)
}

# Run genetic algorithm optimization
best_params, best_score = optimizer.genetic_algorithm(
    param_bounds=param_bounds,
    population_size=20,
    generations=10,
    metric='combined'  # Combined score of multiple metrics
)
```


## ML Factor Signals

Generate alpha signals using ML-based factor computation:

```python
from ml import MLFactor, FactorPipeline
from ml.factor_pipeline import FactorPipeline

# Composite pipeline with weighted aggregation
pipeline = FactorPipeline(
    weights={"momentum": 0.5, "volatility": 0.25, "sentiment": 0.25}
)
signal = pipeline.compute(market_data)  # {"composite": 0.42, "factors": {...}}

# sklearn-powered ML factor with walk-forward training
mf = MLFactor(preset="rf_classifier")
mf.add_feature("returns_5d", lambda df: df["close"].pct_change(5))
mf.add_feature("vol_20d", lambda df: df["close"].pct_change().rolling(20).std())

X = mf.build_features(df)
y = (df["close"].shift(-1) > df["close"]).astype(int)
results = mf.walk_forward_fit(df, target_col="target")

# Save trained model
mf.save("models/my_factor.joblib")
```

## Walk-Forward Validation

Prevent overfitting with walk-forward analysis:

```python
from optimization import WalkForwardValidator

# Create validator
validator = WalkForwardValidator(
    data=data,
    train_size=2000,    # 2000 candles for training
    test_size=500       # 500 candles for testing
)

# Run walk-forward validation
results = validator.run_walk_forward(
    param_grid=param_grid,
    optimization_method='grid',
    metric='sharpe_ratio'
)

# Print summary
print(validator.get_validation_summary())

# Save report
validator.save_validation_report("optimization/walk_forward_report.json")
```

## Live Trading (Advanced)

⚠️ **Warning**: Only proceed with live trading after thorough backtesting and with funds you can afford to lose.

### Step 1: Configure Exchange Connection

```python
from trading import Exchange
from config import settings

# Initialize exchange connection
exchange = CCXTExchange(
    api_key=settings.exchange_api_key,
    secret=settings.exchange_secret,
    exchange_name=settings.exchange_name
)

# Check balance
balance = exchange.get_balance()
print(f"Available balance: {balance}")
```

### Step 2: Create Live Trading Bot

```python
from trading_bot import TradingBot

# Create trading bot
bot = TradingBot(
    strategy=strategy,
    exchange=exchange,
    risk_manager=risk_manager,
    symbols=['BTC/USDT', 'ETH/USDT']
)

# Run live trading
bot.run_live()
```

### Step 3: Monitoring

The bot will:
- Log all decisions to `logs/reinforcetrade.log`
- Send trade notifications (configure in settings)
- Automatically stop on drawdown limit breach

## Troubleshooting

### Common Issues

#### Import Errors

```bash
# Make sure you're in the virtual environment
which python  # Should show venv path

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### Missing Data

```python
# Check if data was fetched correctly
if not data or len(data) == 0:
    print("No data fetched. Check:")
    print("1. Exchange API connectivity")
    print("2. Symbol format (e.g., 'BTC/USDT')")
    print("3. Timeframe validity")
```

#### Memory Issues

```python
# For large datasets, process in chunks
chunk_size = 1000
for i in range(0, len(data), chunk_size):
    chunk = data[i:i+chunk_size]
    # Process chunk
```

#### RL Training Slow

```python
# Reduce observation space complexity
# Use simpler reward function
# Decrease total_timesteps for initial testing
rl_agent.train(env, total_timesteps=10000)  # Start small
```

## Best Practices

### 1. Always Backtest First

```python
# Test on at least 6 months of historical data
# Use out-of-sample testing
# Validate with walk-forward analysis
```

### 2. Start Small

```python
# Paper trading first
initial_balance = 1000  # Start with small amount
# Monitor for 1-2 weeks before increasing
```

### 3. Risk Management

```python
# Never risk more than you can afford to lose
risk_manager = RiskManager(
    max_risk_per_trade=0.01,      # Max 1% per trade
    max_portfolio_risk=0.05       # Max 5% total exposure
)
```

### 4. Regular Monitoring

```python
# Review performance weekly
# Retrain RL agents monthly
# Re-optimize parameters quarterly
```

## Next Steps

- Read the [Architecture Documentation](architecture.md) to understand how the system works
- Explore the [API Reference](api_reference.md) for detailed method documentation
- Learn about [Transparency & Trust](transparency.md) features
- Join the community Discord for support

## Support

- GitHub Issues: Report bugs and feature requests
- Documentation: Detailed guides and API reference
- Community: Discord server for discussions

Happy Trading! 📈
