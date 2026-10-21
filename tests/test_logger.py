import datetime
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from importlib import import_module

lg = import_module('utils.logger')


def make_record(exception=None, **extra):
    return {
        'time': datetime.datetime(2026, 1, 2, 3, 4, 5),
        'level': {'name': 'INFO', 'no': 20},
        'name': 'tests.test_logger',
        'message': 'hello world',
        'function': 'test_function',
        'line': 42,
        'extra': extra,
        'exception': exception,
    }


class TestLoggerInternals(unittest.TestCase):

    def tearDown(self):
        lg._trace_id.set('')
        lg._request_id.set('')

    def test_redact_sensitive_long_value(self):
        record = {'extra': {'api_key': 'abcdefghijklmnop', 'pnl': 5}}
        out = lg._redact_sensitive(record)

        self.assertEqual(out['extra']['api_key'], 'abcd****')
        self.assertEqual(out['extra']['pnl'], 5)
        # original record untouched
        self.assertEqual(record['extra']['api_key'], 'abcdefghijklmnop')

    def test_redact_sensitive_short_value(self):
        out = lg._redact_sensitive({'extra': {'secret': 'short'}})
        self.assertEqual(out['extra']['secret'], '****')

    def test_json_line_is_valid_json_and_redacts(self):
        payload = json.loads(lg._json_line(make_record(pnl=1.5, api_key='abcdefghijkl')))

        self.assertEqual(payload['message'], 'hello world')
        self.assertEqual(payload['level'], 'INFO')
        self.assertEqual(payload['logger'], 'tests.test_logger')
        self.assertEqual(payload['function'], 'test_function')
        self.assertEqual(payload['line'], 42)
        self.assertIn('@timestamp', payload)
        self.assertEqual(payload['extra']['api_key'], 'abcd****')

    def test_json_line_module_uses_extra_when_present(self):
        payload = json.loads(lg._json_line(make_record(module='backtest')))
        self.assertEqual(payload['module'], 'backtest')

    def test_json_line_includes_trace_and_request_ids(self):
        lg.set_trace_id('traceid1')
        lg.set_request_id('reqid1')

        payload = json.loads(lg._json_line(make_record()))

        self.assertEqual(payload['trace_id'], 'traceid1')
        self.assertEqual(payload['request_id'], 'reqid1')

    def test_json_line_serializes_exception(self):
        exc = SimpleNamespace(
            type=ZeroDivisionError,
            value=ZeroDivisionError('division by zero'),
            traceback=None,
        )
        payload = json.loads(lg._json_line(make_record(exception=exc)))

        self.assertEqual(payload['exception']['type'], 'ZeroDivisionError')
        self.assertEqual(payload['exception']['value'], 'division by zero')
        self.assertEqual(payload['exception']['traceback'], '')

    def test_json_sink_writes_single_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.json'
            with patch.object(lg, 'LOG_FILE_JSON', target):
                lg._json_sink(SimpleNamespace(record=make_record(pnl=2)))

            lines = target.read_text(encoding='utf-8').strip().splitlines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])['message'], 'hello world')

    def test_json_sink_swallows_write_errors(self):
        # Point at a directory that does not exist -> OSError is swallowed
        with patch.object(lg, 'LOG_FILE_JSON', Path('nonexistent_dir_xyz') / 'out.json'):
            lg._json_sink(SimpleNamespace(record=make_record()))  # must not raise

    def test_console_format_returns_template(self):
        template = lg._console_format({'level': SimpleNamespace(name='INFO')})
        self.assertIn('{message}', template)
        self.assertIn('{name}', template)

    def test_console_format_unknown_level_uses_default_colour(self):
        template = lg._console_format({'level': SimpleNamespace(name='CUSTOM')})
        self.assertIn('white', template)

    def test_trace_and_request_id_helpers(self):
        tid = lg.set_trace_id()
        self.assertTrue(tid)
        self.assertEqual(lg.get_trace_id(), tid)

        lg.set_trace_id('explicit')
        self.assertEqual(lg.get_trace_id(), 'explicit')

        rid = lg.set_request_id()
        self.assertTrue(rid)
        self.assertEqual(lg.get_request_id(), rid)

        lg.set_request_id('req-explicit')
        self.assertEqual(lg.get_request_id(), 'req-explicit')

    def test_get_log_file_path(self):
        self.assertIsInstance(lg.get_log_file_path(), Path)

    def test_structured_logger_bind_merges(self):
        bound = lg.logger.bind(module='m', env='test')
        self.assertEqual(bound._bound, {'module': 'm', 'env': 'test'})

    def test_structured_logger_log_filters_non_serializable(self):
        with patch.object(lg._base_logger, 'opt') as opt:
            lg.logger.info('message', pnl=1, bad=object())

        opt.assert_called_once_with(depth=2)
        call = opt.return_value.log.call_args
        self.assertEqual(call.args[0], 'INFO')
        self.assertEqual(call.args[1], 'message')
        self.assertEqual(call.kwargs['pnl'], 1)
        self.assertIsInstance(call.kwargs['bad'], str)

    def test_structured_logger_exception_uses_error(self):
        with patch.object(lg._base_logger, 'opt') as opt:
            lg.logger.exception('boom')

        opt.assert_called_once_with(depth=2, exception=True)
        opt.return_value.error.assert_called_once_with('boom')

    def test_is_serializable(self):
        self.assertTrue(lg._is_serializable({'a': [1, 'b', None, True, 1.5]}))
        self.assertFalse(lg._is_serializable({'a': object()}))
        self.assertFalse(lg._is_serializable(object()))


if __name__ == '__main__':
    unittest.main()
