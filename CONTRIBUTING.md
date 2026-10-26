# Contributing to ReinforceTrade

Thanks for taking the time to contribute. This document covers local setup,
the checks CI runs, and the conventions used in this repository.

## Setup

Requirements: **Python 3.9-3.11**.

```bash
git clone <repo-url>
cd ReinforceTrade
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt   # pytest, coverage, flake8, mypy
cp .env.example .env                            # then fill in credentials
```

`.env` is optional: settings load defaults when it is absent. Never commit real
API keys; secrets are redacted from structured logs.

## Checks (same as CI)

```bash
python -m pytest tests/ -v --cov=. --cov-report=term-missing   # tests + coverage
python -m flake8 . --count --select=E9,F63,F7,F82              # fatal lint
python -m mypy                                                 # type check (config in pyproject.toml)
```

`make test`, `make lint`, and `make typecheck` wrap the same commands. Please
make sure all three pass before opening a pull request.

## Project layout

| Path | Purpose |
|------|---------|
| `agents/` | Multi-agent framework (Environment, ShortTerm, Trend, DecisionTower, RL) |
| `strategies/` | Strategy and risk management |
| `backtesting/` | Backtest engines |
| `optimization/` | Grid search, genetic algorithm, walk-forward validation |
| `environments/` | Gymnasium RL environment |
| `data/` | Data loading / preprocessing |
| `ml/` | ML factor pipeline |
| `reports/` | HTML report generation |
| `web/` | Flask dashboard + REST API |
| `trading/` | Exchange adapters, order/position management, WebSocket |
| `rust/` | High-performance data engine (optional) |
| `monitor/` | Go monitoring agent (optional) |
| `dashboard/` | TypeScript dashboard (optional) |

## Optional toolchains

- **Rust engine**: requires a Rust toolchain (`cargo`). Build/install with
  `make rust-build` / `make rust-install` (uses `maturin`). If `cargo` is not
  available the Python package still works without the native engine.
- **Go monitoring agent**: `make go-build`, `make go-test` (requires Go).
- **TypeScript dashboard**: `make dashboard-install && make dashboard-build`
  (requires Node.js).

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(trading): add realized PnL tracking
fix(env): correct position PnL math
test: raise coverage for zero-coverage modules
docs: reconcile documentation with implementation
ci: pin dev dependencies
```

Scopes in use: `env`, `trading`, `backtesting`, `logging`, `config`, `docs`,
`test`, `ci`.

## Pull request checklist

- [ ] `python -m pytest` passes
- [ ] `python -m mypy` reports no errors
- [ ] fatal flake8 checks pass
- [ ] new behaviour has tests
- [ ] `CHANGELOG.md` updated for user-visible changes
- [ ] no secrets, API keys, or generated `logs/` files committed

## Reporting bugs

Include the command you ran, the full traceback, your Python version, and
whether the Rust/Go/dashboard components were involved.
