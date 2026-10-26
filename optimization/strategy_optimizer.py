import itertools
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from backtesting.enhanced_backtester import EnhancedBacktester
from strategies.multi_agent_strategy import MultiAgentStrategy
from strategies.risk_manager import RiskManager
from utils.logger import logger
import json
import os

class StrategyOptimizer:
    """
    Strategy parameter optimization using grid search and genetic algorithm.
    Finds optimal parameters for multi-agent strategy.
    """
    def __init__(self, data: List[Dict[str, Any]], initial_balance: float = 10000):
        self.data = data
        self.initial_balance = initial_balance
        self.results: List[Dict[str, Any]] = []
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_score: float = -np.inf
        
    def grid_search(self, param_grid: Dict[str, List[Any]], metric: str = 'sharpe_ratio') -> Tuple[Dict[str, Any], float]:
        """
        Perform grid search over parameter space.
        
        Args:
            param_grid: Dictionary of parameter names and their possible values
            metric: Metric to optimize ('sharpe_ratio', 'total_return', 'win_rate', etc.)
        """
        logger.info(f"Starting grid search with {len(list(itertools.product(*param_grid.values())))} combinations")
        
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        best_params: Optional[Dict[str, Any]] = None
        best_score = -np.inf
        all_results = []
        
        for i, combination in enumerate(itertools.product(*param_values)):
            params = dict(zip(param_names, combination))
            logger.info(f"Testing combination {i+1}: {params}")
            
            # Create strategy with these parameters
            strategy = self._create_strategy_with_params(params)
            risk_manager = RiskManager()
            backtester = EnhancedBacktester(strategy, self.initial_balance, risk_manager)
            
            # Run backtest
            results = backtester.run(self.data)
            
            # Calculate score
            score = self._calculate_score(results, metric)
            
            result_entry = {
                'params': params,
                'score': score,
                'metrics': {
                    'total_return': results.get('total_return', 0),
                    'sharpe_ratio': results.get('sharpe_ratio', 0),
                    'win_rate': results.get('win_rate', 0),
                    'max_drawdown': results.get('max_drawdown', 0),
                    'profit_factor': results.get('profit_factor', 0),
                    'total_trades': results.get('total_trades', 0)
                }
            }
            all_results.append(result_entry)
            
            if score > best_score:
                best_score = score
                best_params = params.copy()
                logger.info(f"New best score: {score:.4f} with params: {params}")
        
        self.results = all_results
        self.best_params = best_params
        self.best_score = best_score
        
        logger.info(f"Grid search completed. Best params: {best_params}, Score: {best_score:.4f}")
        return best_params or {}, float(best_score)
    
    def genetic_algorithm(self, param_bounds: Dict[str, Tuple[float, float]], 
                         population_size: int = 20, 
                         generations: int = 10,
                         mutation_rate: float = 0.1,
                         metric: str = 'sharpe_ratio') -> Tuple[Dict[str, Any], float]:
        """
        Optimize strategy parameters using genetic algorithm.
        More efficient than grid search for large parameter spaces.
        """
        logger.info(f"Starting genetic algorithm optimization: {population_size} individuals, {generations} generations")
        
        # Initialize population
        population = self._initialize_population(param_bounds, population_size)
        
        for generation in range(generations):
            logger.info(f"Generation {generation + 1}/{generations}")
            
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                score = self._evaluate_individual(individual, metric)
                fitness_scores.append(score)
            
            # Track best individual
            best_idx = np.argmax(fitness_scores)
            if fitness_scores[best_idx] > self.best_score:
                self.best_score = fitness_scores[best_idx]
                self.best_params = population[best_idx].copy()
                logger.info(f"Generation {generation + 1} best score: {self.best_score:.4f}")
            
            # Create next generation
            new_population = []
            
            # Elitism: keep best individuals
            elite_count = max(1, population_size // 5)
            sorted_indices = np.argsort(fitness_scores)[::-1]
            for i in range(elite_count):
                new_population.append(population[sorted_indices[i]].copy())
            
            # Generate rest through crossover and mutation
            while len(new_population) < population_size:
                parent1 = self._tournament_selection(population, fitness_scores)
                parent2 = self._tournament_selection(population, fitness_scores)
                
                child = self._crossover(parent1, parent2)
                child = self._mutate(child, param_bounds, mutation_rate)
                
                new_population.append(child)
            
            population = new_population
        
        logger.info(f"Genetic algorithm completed. Best params: {self.best_params}, Score: {self.best_score:.4f}")
        return self.best_params or {}, float(self.best_score)
    
    def _create_strategy_with_params(self, params: Dict[str, Any]) -> MultiAgentStrategy:
        """Create strategy instance with given parameters"""
        strategy = MultiAgentStrategy(
            use_rl=params.get('use_rl', True),
            confidence_threshold=params.get('confidence_threshold', 0.6)
        )
        
        # Update strategy parameters
        if 'stop_loss_pct' in params:
            strategy.stop_loss_pct = params['stop_loss_pct']
        if 'take_profit_pct' in params:
            strategy.take_profit_pct = params['take_profit_pct']
        if 'max_position_size' in params:
            strategy.max_position_size = params['max_position_size']
        
        return strategy
    
    def _calculate_score(self, results: Dict[str, Any], metric: str) -> float:
        """Calculate optimization score from backtest results"""
        if metric == 'sharpe_ratio':
            return results.get('sharpe_ratio', 0)
        elif metric == 'total_return':
            return results.get('total_return', 0)
        elif metric == 'win_rate':
            return results.get('win_rate', 0)
        elif metric == 'calmar_ratio':
            return results.get('calmar_ratio', 0)
        elif metric == 'profit_factor':
            return results.get('profit_factor', 0)
        elif metric == 'combined':
            # Combined score with multiple factors
            sharpe = results.get('sharpe_ratio', 0)
            returns = results.get('total_return', 0)
            win_rate = results.get('win_rate', 0)
            drawdown = results.get('max_drawdown', 1)  # Avoid division by zero
            
            # Weighted combination
            score = (sharpe * 0.3 + returns * 0.3 + win_rate * 0.2 - drawdown * 0.2)
            return score
        else:
            return results.get(metric, 0)
    
    def _initialize_population(self, param_bounds: Dict[str, Tuple[float, float]], size: int) -> List[Dict[str, Any]]:
        """Initialize random population for genetic algorithm"""
        population = []
        for _ in range(size):
            individual = {}
            for param, (min_val, max_val) in param_bounds.items():
                individual[param] = np.random.uniform(min_val, max_val)
            population.append(individual)
        return population
    
    def _evaluate_individual(self, individual: Dict[str, Any], metric: str) -> float:
        """Evaluate fitness of an individual"""
        strategy = self._create_strategy_with_params(individual)
        risk_manager = RiskManager()
        backtester = EnhancedBacktester(strategy, self.initial_balance, risk_manager)
        
        results = backtester.run(self.data)
        return self._calculate_score(results, metric)
    
    def _tournament_selection(self, population: List[Dict[str, Any]], fitness_scores: List[float], tournament_size: int = 3) -> Dict[str, Any]:
        """Select individual using tournament selection"""
        indices = np.random.choice(len(population), tournament_size, replace=False)
        winner_idx = indices[np.argmax([fitness_scores[i] for i in indices])]
        return population[winner_idx].copy()
    
    def _crossover(self, parent1: Dict[str, Any], parent2: Dict[str, Any]) -> Dict[str, Any]:
        """Perform crossover between two parents"""
        child = {}
        for param in parent1.keys():
            # Uniform crossover
            if np.random.random() < 0.5:
                child[param] = parent1[param]
            else:
                child[param] = parent2[param]
        return child
    
    def _mutate(self, individual: Dict[str, Any], param_bounds: Dict[str, Tuple[float, float]], mutation_rate: float) -> Dict[str, Any]:
        """Mutate individual"""
        for param, value in individual.items():
            if np.random.random() < mutation_rate:
                min_val, max_val = param_bounds[param]
                # Gaussian mutation
                mutation = np.random.normal(0, (max_val - min_val) * 0.1)
                individual[param] = np.clip(value + mutation, min_val, max_val)
        return individual
    
    def save_results(self, output_path: str = "optimization/results.json"):
        """Save optimization results to file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        output = {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'all_results': self.results,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Optimization results saved to {output_path}")
    
    def get_optimization_report(self) -> str:
        """Generate human-readable optimization report"""
        report = []
        report.append("=" * 60)
        report.append("STRATEGY OPTIMIZATION REPORT")
        report.append("=" * 60)
        report.append(f"Best Parameters:")
        for param, value in (self.best_params or {}).items():
            report.append(f"  {param}: {value}")
        report.append(f"\nBest Score: {self.best_score:.4f}")
        report.append(f"\nTop 5 Configurations:")
        
        # Sort results by score
        sorted_results = sorted(self.results, key=lambda x: x['score'], reverse=True)[:5]
        
        for i, result in enumerate(sorted_results, 1):
            report.append(f"\n{i}. Score: {result['score']:.4f}")
            report.append(f"   Return: {result['metrics']['total_return']:.2%}")
            report.append(f"   Sharpe: {result['metrics']['sharpe_ratio']:.2f}")
            report.append(f"   Win Rate: {result['metrics']['win_rate']:.1%}")
        
        return "\n".join(report)
