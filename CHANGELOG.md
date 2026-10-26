# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Post-`v1.0.1` stabilization and test hardening.

### Added

- `pyproject.toml` with pytest, coverage, mypy, and flake8 configuration.
- `requirements-dev.txt` (pytest, pytest-cov, flake8, flake8-pyproject, mypy).
- `Makefile` `typecheck` target; Python targets now use `python -m` (Windows-safe).
- Test suites for `data_loader`, `report_generator`, `strategy_optimizer`,
  `walk_forward_validation`, `logger`, `web/app`, `TradingEnvironment`, and the
  WebSocket connect/reconnect/heartbeat lifecycle.
- Regression tests asserting backtests open trades on trending data.

### Fixed

- Backtests never opened trades: `Backtester`/`EnhancedBacktester` now pass a
  rolling `{'prices': [...]}` window to strategies, align the default risk limit
  with `max_position_size`, and release exposure on close.
- `TradingEnvironment` mixed units and price in PnL math; reward is now the
  change in mark-to-market equity.
- `TradingBot` now computes realized PnL (weighted average entry) and cancels
  open orders during graceful shutdown.
- `DataLoader.load_from_csv` treated epoch seconds as nanoseconds, corrupting
  `timestamp`; numeric and datetime columns are now handled correctly.
- JSON logging crashed (`KeyError: '@timestamp'`): the JSON sink no longer goes
  through Loguru's format/colorizer pipeline; sensitive fields are redacted and
  exceptions are serialized safely.
- `WalkForwardValidator.is_robust` returns a JSON-friendly `bool`.
- pandas 2.x deprecations (`fillna(method=...)`, monthly resample `'M'` → `'ME'`).
- Documentation referenced a non-existent `monitoring` package and stale APIs;
  examples now run on Windows consoles (UTF-8 stdout).

### Changed

- CI type check now targets the real package layout (`python -m mypy`, config in
  `pyproject.toml`) instead of the non-existent `src/`, and no longer masks
  failures with `|| true`.
- CI installs tooling from `requirements-dev.txt`.

### Tests

- 487 tests passing; overall coverage baseline 85%.

## [1.0.1] - 2026-09-28

### Fixed

- Migrated the RL environment to the Gymnasium API (`reset` → `(obs, info)`,
  `step` → 5-tuple, `render()` without `mode`).
- Updated call sites in `agents/training_pipeline.py` and
  `examples/train_rl_agent.py`.
- Modernized settings to Pydantic v2 (`SettingsConfigDict`) and added
  `pydantic-settings` to the runtime requirements.
- Fixed pre-existing failures across trading, risk, and backtesting modules
  (position IDs, `timedelta` import, order cancellation scope, drawdown peak
  tracking, risk-manager attribute mismatch, position-size cap, empty backtest
  results, market-order balance checks).

## [1.0.0] - 2026-06-30

- Initial release: multi-agent RL trading system with CCXT/IB/OANDA adapters,
  ML factor pipeline, Rust data engine, Go monitoring agent, SQL analytics,
  Flask/WebSocket dashboard, and CI/CD deployment.
