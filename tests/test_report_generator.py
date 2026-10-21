import os
import tempfile
import unittest

import matplotlib
matplotlib.use('Agg')

from backtesting import EnhancedBacktester
from reports import ReportGenerator
from strategies import MultiAgentStrategy


def make_trend_data(n=140, start=100.0, drift=0.004):
    """Deterministic uptrend OHLCV series."""
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


class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        backtester = EnhancedBacktester(
            MultiAgentStrategy(use_rl=False), initial_balance=10000
        )
        self.results = backtester.run(make_trend_data())
        self.generator = ReportGenerator(output_dir=self.tmp.name)

    def test_generate_full_report_writes_html_and_json(self):
        report_dir = self.generator.generate_full_report(self.results, strategy_name='TestStrategy')

        self.assertTrue(os.path.isdir(report_dir))
        html_path = os.path.join(report_dir, 'report.html')
        json_path = os.path.join(report_dir, 'data.json')
        self.assertTrue(os.path.exists(html_path))
        self.assertTrue(os.path.exists(json_path))

        with open(html_path, encoding='utf-8') as fh:
            html = fh.read()
        self.assertIn('TestStrategy', html)
        self.assertIn('<html>', html)

    def test_generate_full_report_writes_plots(self):
        report_dir = self.generator.generate_full_report(self.results)

        expected = [
            'equity_curve.png',
            'drawdown.png',
            'trade_distribution.png',
            'agent_signals.png',
            'cumulative_returns.png',
        ]
        for name in expected:
            self.assertTrue(
                os.path.exists(os.path.join(report_dir, name)),
                msg=f'missing plot: {name}',
            )

    def test_generate_full_report_default_strategy_name(self):
        report_dir = self.generator.generate_full_report(self.results)
        with open(os.path.join(report_dir, 'report.html'), encoding='utf-8') as fh:
            html = fh.read()
        self.assertIn('MultiAgentStrategy', html)

    def test_generate_summary_pdf_is_noop_placeholder(self):
        # Documented placeholder: no file is produced and nothing raises
        target = os.path.join(self.tmp.name, 'summary.pdf')
        result = self.generator.generate_summary_pdf(self.results, output_path=target)
        self.assertIsNone(result)
        self.assertFalse(os.path.exists(target))


if __name__ == '__main__':
    unittest.main()
