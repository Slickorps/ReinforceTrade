#!/usr/bin/env python3
"""
Strategy Optimization Example
This example shows how to optimize strategy parameters using grid search and genetic algorithm.
"""

import sys
sys.path.insert(0, '..')

# Windows consoles often use a legacy code page (e.g. GBK) that cannot encode
# emoji glyphs used below; force UTF-8 output where supported.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from optimization import StrategyOptimizer, WalkForwardValidator
from utils import logger
import numpy as np

def generate_test_data(num_points=300):
    """Generate test data for optimization"""
    np.random.seed(456)
    data = []
    price = 50000
    
    for i in range(num_points):
        change = np.random.normal(0.0003, 0.018)
        price *= (1 + change)
        
        data.append({
            'timestamp': 1609459200 + i*3600,
            'open': price * (1 + np.random.normal(0, 0.001)),
            'high': price * (1 + abs(np.random.normal(0, 0.01))),
            'low': price * (1 - abs(np.random.normal(0, 0.01))),
            'close': price,
            'volume': 1000 + abs(np.random.normal(0, 350))
        })
    
    return data

def run_grid_search_example():
    """Example of grid search optimization"""
    logger.info("=" * 60)
    logger.info("Grid Search Optimization Example")
    logger.info("=" * 60)
    
    # Generate data
    logger.info("Generating test data...")
    data = generate_test_data(300)
    
    # Define parameter grid
    param_grid = {
        'confidence_threshold': [0.5, 0.6, 0.7],
        'stop_loss_pct': [0.03, 0.05, 0.07],
        'take_profit_pct': [0.08, 0.10, 0.12],
        'use_rl': [False]  # Set to True if RL models available
    }
    
    logger.info(f"Parameter combinations to test: {len(param_grid['confidence_threshold']) * len(param_grid['stop_loss_pct']) * len(param_grid['take_profit_pct'])}")
    
    # Create optimizer
    optimizer = StrategyOptimizer(data, initial_balance=10000)
    
    # Run grid search
    logger.info("Running grid search...")
    try:
        best_params, best_score = optimizer.grid_search(
            param_grid=param_grid,
            metric='sharpe_ratio'  # Optimize for Sharpe ratio
        )
        
        logger.info("Grid Search Results:")
        logger.info(f"Best Parameters: {best_params}")
        logger.info(f"Best Score (Sharpe): {best_score:.4f}")
        
        # Save results
        optimizer.save_results("optimization/grid_search_example.json")
        logger.info("Results saved to optimization/grid_search_example.json")
        
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        raise

def run_walk_forward_example():
    """Example of walk-forward validation"""
    logger.info("=" * 60)
    logger.info("Walk-Forward Validation Example")
    logger.info("=" * 60)
    
    # Generate data
    logger.info("Generating test data...")
    data = generate_test_data(500)
    
    # Create validator
    validator = WalkForwardValidator(
        data=data,
        train_size=150,
        test_size=50
    )
    
    # Define parameter grid (smaller for walk-forward)
    param_grid = {
        'confidence_threshold': [0.6, 0.7],
        'stop_loss_pct': [0.04, 0.06],
        'use_rl': [False]
    }
    
    # Run walk-forward validation
    logger.info("Running walk-forward validation...")
    try:
        results = validator.run_walk_forward(
            param_grid=param_grid,
            optimization_method='grid',
            metric='sharpe_ratio'
        )
        
        # Print summary
        summary = validator.get_validation_summary()
        logger.info("Walk-Forward Validation Summary:")
        logger.info(summary)
        
        # Save report
        validator.save_validation_report("optimization/walk_forward_example.json")
        logger.info("Report saved to optimization/walk_forward_example.json")
        
        # Check if strategy is robust
        if results.get('is_robust'):
            logger.info("✅ Strategy PASSED robustness test")
        else:
            logger.warning("⚠️ Strategy FAILED robustness test - may be overfitted")
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise

if __name__ == '__main__':
    import os
    os.makedirs('../optimization', exist_ok=True)
    
    # Run grid search
    run_grid_search_example()
    
    print("\n" + "=" * 60 + "\n")
    
    # Run walk-forward validation
    run_walk_forward_example()
    
    print("\n✅ Strategy optimization examples completed!")
