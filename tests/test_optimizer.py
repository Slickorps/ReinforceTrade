import json
import os
import tempfile
import unittest

from optimization import StrategyOptimizer, WalkForwardValidator
from optimization.walk_forward_validation import TimeSeriesCrossValidator


def make_trend_data(n=120, start=100.0, drift=0.004):
    data = []
    price = start
    for i in range(n):
        price *= 1 + drift + 0.0005 * ((i % 3) - 1)
        data.append({
            'timestamp': 1609459200 + i * 3600,
            'open': price,
            'high': price * 1.001,
            'low': price * 0.999,
            'close': price,
            'volume': 1000.0,
        })
    return data


class TestStrategyOptimizer(unittest.TestCase):

    def setUp(self):
        self.data = make_trend_data()
        self.optimizer = StrategyOptimizer(self.data, initial_balance=10000)

    def test_grid_search_returns_best_params_and_records_results(self):
        param_grid = {
            'confidence_threshold': [0.55, 0.6],
            'max_position_size': [0.05],
        }

        best_params, best_score = self.optimizer.grid_search(param_grid)

        self.assertIsInstance(best_params, dict)
        self.assertIn('confidence_threshold', best_params)
        self.assertEqual(best_params['max_position_size'], 0.05)
        self.assertIsInstance(best_score, (int, float))
        self.assertEqual(len(self.optimizer.results), 2)
        entry = self.optimizer.results[0]
        self.assertIn('params', entry)
        self.assertIn('score', entry)
        self.assertIn('total_trades', entry['metrics'])

    def test_save_results_writes_json(self):
        self.optimizer.grid_search({'confidence_threshold': [0.6], 'max_position_size': [0.05]})

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'results.json')
            self.optimizer.save_results(path)
            with open(path, encoding='utf-8') as fh:
                payload = json.load(fh)

        self.assertIn('best_params', payload)
        self.assertIn('best_score', payload)
        self.assertIn('all_results', payload)
        self.assertIn('timestamp', payload)
        self.assertEqual(len(payload['all_results']), 1)

    def test_get_optimization_report(self):
        self.optimizer.grid_search({'confidence_threshold': [0.6], 'max_position_size': [0.05]})
        report = self.optimizer.get_optimization_report()

        self.assertIn('STRATEGY OPTIMIZATION REPORT', report)
        self.assertIn('Best Parameters', report)
        self.assertIn('Best Score', report)

    def test_calculate_score_supports_all_metrics(self):
        results = {
            'sharpe_ratio': 1.5,
            'total_return': 0.2,
            'win_rate': 0.6,
            'calmar_ratio': 2.0,
            'profit_factor': 1.8,
            'max_drawdown': 0.1,
            'custom_metric': 42,
        }

        self.assertEqual(self.optimizer._calculate_score(results, 'sharpe_ratio'), 1.5)
        self.assertEqual(self.optimizer._calculate_score(results, 'total_return'), 0.2)
        self.assertEqual(self.optimizer._calculate_score(results, 'win_rate'), 0.6)
        self.assertEqual(self.optimizer._calculate_score(results, 'calmar_ratio'), 2.0)
        self.assertEqual(self.optimizer._calculate_score(results, 'profit_factor'), 1.8)
        self.assertEqual(self.optimizer._calculate_score(results, 'custom_metric'), 42)
        # combined = 1.5*0.3 + 0.2*0.3 + 0.6*0.2 - 0.1*0.2
        self.assertAlmostEqual(
            self.optimizer._calculate_score(results, 'combined'), 0.61, places=6
        )

    def test_genetic_algorithm_smoke(self):
        bounds = {'confidence_threshold': (0.5, 0.7)}

        best_params, best_score = self.optimizer.genetic_algorithm(
            bounds, population_size=4, generations=1, mutation_rate=1.0
        )

        self.assertIn('confidence_threshold', best_params)
        self.assertGreaterEqual(best_params['confidence_threshold'], 0.5)
        self.assertLessEqual(best_params['confidence_threshold'], 0.7)
        self.assertIsInstance(best_score, (int, float))


class TestWalkForwardValidator(unittest.TestCase):

    def setUp(self):
        self.data = make_trend_data(120)
        self.validator = WalkForwardValidator(self.data, train_size=60, test_size=30)

    def test_run_walk_forward_without_param_grid(self):
        results = self.validator.run_walk_forward()

        self.assertIn('window_results', results)
        self.assertIn('aggregate', results)
        self.assertIn('is_robust', results)
        self.assertEqual(len(results['window_results']), 2)
        aggregate = results['aggregate']
        for key in ('avg_oos_return', 'avg_oos_sharpe', 'robustness_score',
                    'positive_windows', 'total_windows'):
            self.assertIn(key, aggregate)
        self.assertEqual(aggregate['total_windows'], 2)
        self.assertIsInstance(results['is_robust'], bool)

    def test_run_walk_forward_with_grid_optimization(self):
        validator = WalkForwardValidator(self.data, train_size=60, test_size=60)

        results = validator.run_walk_forward(param_grid={'confidence_threshold': [0.6]})

        self.assertEqual(len(results['window_results']), 1)
        self.assertIn('best_params', results['window_results'][0])

    def test_summary_before_and_after_run(self):
        self.assertEqual(self.validator.get_validation_summary(),
                         'No validation results available')

        self.validator.run_walk_forward()
        summary = self.validator.get_validation_summary()

        self.assertIn('WALK-FORWARD VALIDATION SUMMARY', summary)
        self.assertIn('Robustness Metrics', summary)

    def test_save_validation_report(self):
        self.validator.run_walk_forward()

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'walk_forward.json')
            self.validator.save_validation_report(path)
            with open(path, encoding='utf-8') as fh:
                payload = json.load(fh)

        self.assertIn('window_results', payload)
        self.assertIn('aggregate', payload)
        self.assertIn('configuration', payload)
        self.assertEqual(payload['configuration']['train_size'], 60)


class TestTimeSeriesCrossValidator(unittest.TestCase):

    def test_expanding_window_splits(self):
        data = list(range(100))
        splits = TimeSeriesCrossValidator(n_splits=4, expanding=True).split(data)

        self.assertEqual(len(splits), 4)
        self.assertEqual(len(splits[0][0]), 20)
        self.assertEqual(len(splits[0][1]), 20)
        self.assertEqual(len(splits[-1][0]), 80)

    def test_rolling_window_splits(self):
        data = list(range(100))
        splits = TimeSeriesCrossValidator(n_splits=4, expanding=False).split(data)

        # Last window has no room for a non-empty test set
        self.assertEqual(len(splits), 3)
        for train, test in splits:
            self.assertEqual(len(train), 40)
            self.assertEqual(len(test), 20)


if __name__ == '__main__':
    unittest.main()
