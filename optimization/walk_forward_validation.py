from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from backtesting.enhanced_backtester import EnhancedBacktester
from strategies.multi_agent_strategy import MultiAgentStrategy
from strategies.risk_manager import RiskManager
from optimization.strategy_optimizer import StrategyOptimizer
from utils.logger import logger
import json
import os

class WalkForwardValidator:
    """
    Walk-forward validation for strategy robustness testing.
    Prevents overfitting by testing on out-of-sample data.
    """
    def __init__(self, data: List[Dict[str, Any]], train_size: int = 1000, test_size: int = 300):
        self.data = data
        self.train_size = train_size
        self.test_size = test_size
        self.results: List[Dict[str, Any]] = []
        
    def run_walk_forward(self, param_grid: Optional[Dict[str, List[Any]]] = None, 
                        optimization_method: str = 'grid',
                        metric: str = 'sharpe_ratio') -> Dict[str, Any]:
        """
        Run walk-forward validation with rolling window.
        
        Process:
        1. Train on in-sample data (optimization)
        2. Test on out-of-sample data (validation)
        3. Roll window forward and repeat
        """
        logger.info(f"Starting walk-forward validation with train_size={self.train_size}, test_size={self.test_size}")
        
        window_results = []
        total_data_points = len(self.data)
        window_start = 0
        window_num = 0
        
        while window_start + self.train_size + self.test_size <= total_data_points:
            window_num += 1
            train_end = window_start + self.train_size
            test_end = train_end + self.test_size
            
            # Split data
            train_data = self.data[window_start:train_end]
            test_data = self.data[train_end:test_end]
            
            logger.info(f"Window {window_num}: Training on {len(train_data)} points, Testing on {len(test_data)} points")
            
            # Optimize on training data
            if param_grid:
                optimizer = StrategyOptimizer(train_data)
                
                if optimization_method == 'grid':
                    best_params, _ = optimizer.grid_search(param_grid, metric=metric)
                elif optimization_method == 'genetic':
                    # Convert list values to bounds for GA
                    param_bounds = {}
                    for param, values in param_grid.items():
                        param_bounds[param] = (min(values), max(values))
                    best_params, _ = optimizer.genetic_algorithm(param_bounds, metric=metric)
            else:
                # Use default parameters
                best_params = {}
            
            # Test on out-of-sample data
            in_sample_results = self._test_strategy(train_data, best_params)
            out_of_sample_results = self._test_strategy(test_data, best_params)
            
            window_result: Dict[str, Any] = {
                'window': window_num,
                'train_start': window_start,
                'train_end': train_end,
                'test_end': test_end,
                'best_params': best_params,
                'in_sample': {
                    'sharpe': in_sample_results.get('sharpe_ratio', 0),
                    'return': in_sample_results.get('total_return', 0),
                    'max_dd': in_sample_results.get('max_drawdown', 0),
                    'trades': in_sample_results.get('total_trades', 0)
                },
                'out_of_sample': {
                    'sharpe': out_of_sample_results.get('sharpe_ratio', 0),
                    'return': out_of_sample_results.get('total_return', 0),
                    'max_dd': out_of_sample_results.get('max_drawdown', 0),
                    'trades': out_of_sample_results.get('total_trades', 0)
                }
            }
            
            window_results.append(window_result)
            
            # Log results
            logger.info(f"Window {window_num} Results:")
            logger.info(f"  In-Sample: Return={window_result['in_sample']['return']:.2%}, "
                       f"Sharpe={window_result['in_sample']['sharpe']:.2f}")
            logger.info(f"  Out-of-Sample: Return={window_result['out_of_sample']['return']:.2%}, "
                       f"Sharpe={window_result['out_of_sample']['sharpe']:.2f}")
            
            # Move window forward
            window_start += self.test_size
        
        self.results = window_results
        
        # Calculate aggregate statistics
        aggregate = self._calculate_aggregate_stats(window_results)
        
        final_results = {
            'window_results': window_results,
            'aggregate': aggregate,
            'is_robust': bool(aggregate['robustness_score'] > 0.5)
        }
        
        logger.info(f"Walk-forward validation completed. Robustness: {aggregate['robustness_score']:.2%}")
        
        return final_results
    
    def _test_strategy(self, data: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, Any]:
        """Test strategy on given data"""
        strategy = MultiAgentStrategy(
            use_rl=params.get('use_rl', True),
            confidence_threshold=params.get('confidence_threshold', 0.6)
        )
        
        # Update parameters
        if 'stop_loss_pct' in params:
            strategy.stop_loss_pct = params['stop_loss_pct']
        if 'take_profit_pct' in params:
            strategy.take_profit_pct = params['take_profit_pct']
        
        risk_manager = RiskManager()
        backtester = EnhancedBacktester(strategy, 10000, risk_manager)
        
        return backtester.run(data)
    
    def _calculate_aggregate_stats(self, window_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate aggregate statistics across all windows"""
        if not window_results:
            return {}
        
        # Extract out-of-sample results
        oos_returns = [w['out_of_sample']['return'] for w in window_results]
        oos_sharpes = [w['out_of_sample']['sharpe'] for w in window_results]
        oos_max_dds = [w['out_of_sample']['max_dd'] for w in window_results]
        
        # Compare in-sample vs out-of-sample
        is_returns = [w['in_sample']['return'] for w in window_results]
        is_sharpes = [w['in_sample']['sharpe'] for w in window_results]
        
        # Calculate degradation (how much performance drops OOS)
        return_degradation = np.mean(is_returns) - np.mean(oos_returns)
        sharpe_degradation = np.mean(is_sharpes) - np.mean(oos_sharpes)
        
        # Robustness score: how consistent is OOS performance
        consistency = 1 - (np.std(oos_returns) / (np.mean(np.abs(oos_returns)) + 1e-6))
        
        # Overfitting score: difference between IS and OOS
        overfitting = abs(return_degradation) / (np.mean(np.abs(is_returns)) + 1e-6)
        
        # Robustness score combines consistency and low overfitting
        robustness_score = max(0, (consistency * 0.5 + (1 - min(overfitting, 1)) * 0.5))
        
        return {
            'avg_oos_return': np.mean(oos_returns),
            'avg_oos_sharpe': np.mean(oos_sharpes),
            'avg_oos_max_dd': np.mean(oos_max_dds),
            'std_oos_return': np.std(oos_returns),
            'return_degradation': return_degradation,
            'sharpe_degradation': sharpe_degradation,
            'consistency_score': consistency,
            'overfitting_score': overfitting,
            'robustness_score': robustness_score,
            'positive_windows': sum(1 for r in oos_returns if r > 0),
            'total_windows': len(window_results)
        }
    
    def save_validation_report(self, output_path: str = "optimization/walk_forward_report.json"):
        """Save walk-forward validation report"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        final_results = {
            'window_results': self.results,
            'aggregate': self._calculate_aggregate_stats(self.results),
            'timestamp': datetime.now().isoformat(),
            'configuration': {
                'train_size': self.train_size,
                'test_size': self.test_size,
                'total_data': len(self.data)
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(final_results, f, indent=2)
        
        logger.info(f"Walk-forward validation report saved to {output_path}")
    
    def get_validation_summary(self) -> str:
        """Generate human-readable validation summary"""
        if not self.results:
            return "No validation results available"
        
        aggregate = self._calculate_aggregate_stats(self.results)
        
        report = []
        report.append("=" * 70)
        report.append("WALK-FORWARD VALIDATION SUMMARY")
        report.append("=" * 70)
        report.append(f"Total Windows: {aggregate['total_windows']}")
        report.append(f"Positive Windows: {aggregate['positive_windows']}")
        report.append("")
        report.append("Out-of-Sample Performance:")
        report.append(f"  Average Return: {aggregate['avg_oos_return']:.2%}")
        report.append(f"  Average Sharpe: {aggregate['avg_oos_sharpe']:.2f}")
        report.append(f"  Average Max DD: {aggregate['avg_oos_max_dd']:.2%}")
        report.append(f"  Return Std Dev: {aggregate['std_oos_return']:.2%}")
        report.append("")
        report.append("Robustness Metrics:")
        report.append(f"  Consistency Score: {aggregate['consistency_score']:.2%}")
        report.append(f"  Overfitting Score: {aggregate['overfitting_score']:.2%}")
        report.append(f"  Return Degradation: {aggregate['return_degradation']:.2%}")
        report.append(f"  Robustness Score: {aggregate['robustness_score']:.2%}")
        report.append("")
        report.append(f"IS ROBUST: {'YES' if aggregate['robustness_score'] > 0.5 else 'NO'}")
        
        return "\n".join(report)

class TimeSeriesCrossValidator:
    """
    Time series cross-validation for time-dependent data.
    Uses expanding window or rolling window approach.
    """
    def __init__(self, n_splits: int = 5, expanding: bool = True):
        self.n_splits = n_splits
        self.expanding = expanding
        
    def split(self, data: List[Dict[str, Any]]) -> List[Tuple[List[Dict], List[Dict]]]:
        """
        Generate train/test splits for time series.
        Returns list of (train_data, test_data) tuples.
        """
        n_samples = len(data)
        splits = []
        
        if self.expanding:
            # Expanding window: train set grows
            test_size = n_samples // (self.n_splits + 1)
            for i in range(1, self.n_splits + 1):
                train_end = i * test_size
                test_end = min((i + 1) * test_size, n_samples)
                
                train_data = data[:train_end]
                test_data = data[train_end:test_end]
                
                splits.append((train_data, test_data))
        else:
            # Rolling window: fixed train size
            test_size = n_samples // (self.n_splits + 1)
            train_size = test_size * 2  # 2x test size
            
            for i in range(self.n_splits):
                train_start = i * test_size
                train_end = train_start + train_size
                test_end = min(train_end + test_size, n_samples)
                
                if test_end > train_end:
                    train_data = data[train_start:train_end]
                    test_data = data[train_end:test_end]
                    splits.append((train_data, test_data))
        
        return splits
