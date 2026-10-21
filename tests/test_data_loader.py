import csv
import os
import tempfile
import unittest
from unittest.mock import Mock

import pandas as pd

from data import DataLoader


def make_rows(n=60, start=100.0):
    """Deterministic OHLCV rows."""
    rows = []
    ts = 1609459200
    for i in range(n):
        close = start + i
        rows.append({
            'timestamp': ts + i * 3600,
            'open': close - 0.5,
            'high': close + 1.0,
            'low': close - 1.0,
            'close': close,
            'volume': 1000 + i,
        })
    return rows


def write_csv(path, rows, fieldnames):
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestDataLoader(unittest.TestCase):

    def setUp(self):
        self.loader = DataLoader(exchange_name='binance')

    def test_initialization(self):
        self.assertEqual(self.loader.exchange_name, 'binance')
        self.assertIsNotNone(self.loader.exchange)

    def test_load_from_csv(self):
        rows = make_rows(10)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'data.csv')
            write_csv(path, rows, ['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            data = self.loader.load_from_csv(path)

        self.assertEqual(len(data), 10)
        self.assertIn('close', data[0])
        self.assertIn('timestamp', data[0])
        self.assertEqual(data[0]['timestamp'], rows[0]['timestamp'])

    def test_load_from_csv_fills_missing_volume(self):
        rows = [{k: v for k, v in r.items() if k != 'volume'} for r in make_rows(5)]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'data.csv')
            write_csv(path, rows, ['timestamp', 'open', 'high', 'low', 'close'])
            data = self.loader.load_from_csv(path)

        self.assertEqual(len(data), 5)
        self.assertEqual(data[0]['volume'], 0)

    def test_load_from_csv_missing_required_column_raises(self):
        rows = [{k: v for k, v in r.items() if k != 'close'} for r in make_rows(3)]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'data.csv')
            write_csv(path, rows, ['timestamp', 'open', 'high', 'low', 'volume'])
            with self.assertRaises(ValueError):
                self.loader.load_from_csv(path)

    def test_fetch_historical_data(self):
        self.loader.exchange = Mock()
        self.loader.exchange.fetch_ohlcv.return_value = [
            [1609459200000, 100.0, 101.0, 99.0, 100.5, 10.0],
            [1609462800000, 100.5, 102.0, 100.0, 101.5, 12.0],
        ]

        data = self.loader.fetch_historical_data('BTC/USDT', timeframe='1h', limit=2,
                                                 start_date='2021-01-01')

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['timestamp'], 1609459200)
        self.assertEqual(data[0]['close'], 100.5)
        call = self.loader.exchange.fetch_ohlcv.call_args
        self.assertEqual(call.kwargs['since'], 1609459200000)

    def test_fetch_historical_data_propagates_errors(self):
        self.loader.exchange = Mock()
        self.loader.exchange.fetch_ohlcv.side_effect = RuntimeError('api down')
        with self.assertRaises(RuntimeError):
            self.loader.fetch_historical_data('BTC/USDT')

    def test_preprocess_adds_indicators(self):
        df = self.loader.preprocess_data(make_rows(60))
        for column in ('sma_20', 'sma_50', 'rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_lower'):
            self.assertIn(column, df.columns)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df['timestamp']))
        self.assertEqual(int(df.isna().sum().sum()), 0)

    def test_preprocess_without_indicators(self):
        df = self.loader.preprocess_data(make_rows(30), add_technical_indicators=False)
        self.assertNotIn('sma_20', df.columns)
        self.assertIn('close', df.columns)

    def test_split_train_test(self):
        df = self.loader.preprocess_data(make_rows(100), add_technical_indicators=False)
        train, test = self.loader.split_train_test(df, train_ratio=0.8)
        self.assertEqual(len(train), 80)
        self.assertEqual(len(test), 20)
        self.assertIsInstance(train[0], dict)


if __name__ == '__main__':
    unittest.main()
