import unittest
from unittest.mock import Mock

from web import app as webapp


class Order:
    def __init__(self, status):
        self.status = status

    def to_dict(self):
        return {'status': self.status}


class PositionStub:
    def to_dict(self):
        return {'symbol': 'BTC/USDT', 'unrealized_pnl': 1.23456789}


class TestWebApp(unittest.TestCase):

    def setUp(self):
        self._saved = dict(webapp._registry)
        for key in webapp._registry:
            webapp._registry[key] = None
        self.app = webapp.create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        webapp._registry.update(self._saved)

    def test_health(self):
        response = self.client.get('/api/health')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['status'], 'ok')
        self.assertFalse(any(payload['services'].values()))
        self.assertIn('timestamp', payload)

    def test_dashboard_renders(self):
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'html', response.data.lower())

    def test_metrics_not_configured(self):
        response = self.client.get('/api/metrics')
        self.assertEqual(response.status_code, 503)
        self.assertIn('error', response.get_json())

    def test_positions_not_configured(self):
        response = self.client.get('/api/positions')
        self.assertEqual(response.status_code, 503)

    def test_performance_not_configured(self):
        response = self.client.get('/api/performance')
        self.assertEqual(response.status_code, 503)

    def test_trades_with_no_sources(self):
        response = self.client.get('/api/trades')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['trades'], [])
        self.assertEqual(payload['count'], 0)

    def test_metrics_with_collector(self):
        collector = Mock()
        collector.get_summary.return_value = {'win_rate': 0.5}
        collector.get_completed_trades_dict.return_value = [{'id': 1}]
        webapp.set_metrics_collector(collector)

        response = self.client.get('/api/metrics?limit=10')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['summary'], {'win_rate': 0.5})
        self.assertEqual(payload['recent_trades'], [{'id': 1}])
        collector.get_completed_trades_dict.assert_called_once_with(10)

    def test_metrics_error_returns_500(self):
        collector = Mock()
        collector.get_summary.side_effect = RuntimeError('boom')
        webapp.set_metrics_collector(collector)

        response = self.client.get('/api/metrics')

        self.assertEqual(response.status_code, 500)
        self.assertIn('boom', response.get_json()['error'])

    def test_positions_with_tracker(self):
        tracker = Mock()
        tracker.get_all_positions.return_value = [PositionStub()]
        tracker.calculate_portfolio_value.return_value = {
            'total_unrealized_pnl': 1.23456789,
            'total_realized_pnl': 0.0,
            'total_pnl': 1.23456789,
            'total_position_value': 100.0,
            'active_positions': 1,
        }
        webapp.set_position_tracker(tracker)

        response = self.client.get('/api/positions')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['positions'][0]['unrealized_pnl'], 1.2346)
        self.assertEqual(payload['portfolio']['active_positions'], 1)

    def test_positions_error_returns_500(self):
        tracker = Mock()
        tracker.get_all_positions.side_effect = RuntimeError('boom')
        webapp.set_position_tracker(tracker)

        response = self.client.get('/api/positions')

        self.assertEqual(response.status_code, 500)

    def test_performance_with_tracker(self):
        tracker = Mock()
        tracker.get_performance_summary.return_value = {'sharpe_ratio': 1.23456}
        webapp.set_performance_tracker(tracker)

        response = self.client.get('/api/performance')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['performance']['sharpe_ratio'], 1.2346)

    def test_performance_error_returns_500(self):
        tracker = Mock()
        tracker.get_performance_summary.side_effect = RuntimeError('boom')
        webapp.set_performance_tracker(tracker)

        response = self.client.get('/api/performance')

        self.assertEqual(response.status_code, 500)

    def test_trades_from_order_manager(self):
        order_manager = Mock()
        order_manager.get_order_history.return_value = [Order('filled'), Order('canceled')]
        webapp.set_order_manager(order_manager)

        response = self.client.get('/api/trades')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['trades'][0]['status'], 'filled')

    def test_trades_fall_back_to_metrics_collector(self):
        collector = Mock()
        collector.get_completed_trades_dict.return_value = [{'id': 'x'}]
        webapp.set_metrics_collector(collector)

        response = self.client.get('/api/trades')
        payload = response.get_json()

        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['trades'], [{'id': 'x'}])

    def test_set_performance_tracker_also_sets_collector(self):
        tracker = Mock()
        tracker.collector = Mock()

        webapp.set_performance_tracker(tracker)

        registry = webapp.get_registry()
        self.assertIs(registry['performance_tracker'], tracker)
        self.assertIs(registry['metrics_collector'], tracker.collector)

    def test_get_registry_returns_copy(self):
        registry = webapp.get_registry()
        registry['order_manager'] = 'mutated'
        self.assertIsNone(webapp._registry['order_manager'])

    def test_get_json_param_clamping(self):
        with self.app.test_request_context('/?limit=9999'):
            self.assertEqual(webapp._get_json_param('limit', 50), 500)
        with self.app.test_request_context('/?limit=0'):
            self.assertEqual(webapp._get_json_param('limit', 50), 1)
        with self.app.test_request_context('/?limit=abc'):
            self.assertEqual(webapp._get_json_param('limit', 50), 50)
        with self.app.test_request_context('/'):
            self.assertEqual(webapp._get_json_param('limit', 50), 50)

    def test_cors_headers_present(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), '*')

    def test_positions_to_dict_handles_missing_to_dict(self):
        result = webapp._positions_to_dict([PositionStub(), object()])
        self.assertEqual(result[0]['symbol'], 'BTC/USDT')
        self.assertEqual(result[1], {})


if __name__ == '__main__':
    unittest.main()
