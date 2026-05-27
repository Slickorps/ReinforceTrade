.PHONY: help install test lint format clean docker-build docker-run rust-build rust-test rust-clean go-build go-test dashboard-install dashboard-build dashboard-watch web

help:
	@echo "ReinforceTrade - Multi-Language Quant Trading System"
	@echo ""
	@echo "=== Python ==="
	@echo "  install          - Install Python dependencies"
	@echo "  test             - Run all Python tests"
	@echo "  test-unit        - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  lint             - Run linting (flake8)"
	@echo "  format           - Format code (black)"
	@echo "  clean            - Clean temporary files"
	@echo "  backtest         - Run basic backtest example"
	@echo "  train            - Run RL training example"
	@echo "  optimize         - Run strategy optimization example"
	@echo ""
	@echo "=== Rust (High-Performance Engine) ==="
	@echo "  rust-build       - Build Rust engine (debug)"
	@echo "  rust-release     - Build Rust engine (release)"
	@echo "  rust-test        - Run Rust tests"
	@echo "  rust-clean       - Clean Rust build artifacts"
	@echo "  rust-install     - Install Rust engine as Python module"
	@echo ""
	@echo "=== Go (Monitoring Agent) ==="
	@echo "  go-build         - Build Go monitoring agent"
	@echo "  go-test          - Run Go tests"
	@echo "  go-clean         - Clean Go build artifacts"
	@echo ""
	@echo "=== TypeScript (Dashboard) ==="
	@echo "  dashboard-install - Install dashboard dependencies"
	@echo "  dashboard-build   - Build TypeScript dashboard"
	@echo "  dashboard-watch   - Watch TypeScript for changes"
	@echo ""
	@echo "=== Docker ==="
	@echo "  docker-build     - Build Docker image"
	@echo "  docker-run       - Run Docker container"
	@echo "  docker-stop      - Stop Docker container"
	@echo ""
	@echo "=== Web ==="
	@echo "  web              - Run web dashboard server"

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt 2>/dev/null || true

test:
	pytest tests/ -v --cov=. --cov-report=term-missing

test-unit:
	pytest tests/test_agents.py tests/test_strategies.py tests/test_backtesting.py -v

test-integration:
	pytest tests/test_integration.py -v

lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format:
	black . --line-length 100 2>/dev/null || echo "black not installed, skipping"

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/

docker-build:
	docker build -t reinforcetrade:latest .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

backtest:
	python examples/basic_backtest.py

train:
	python examples/train_rl_agent.py

optimize:
	python examples/optimize_strategy.py

web:
	python -c "from web.app import create_app; app = create_app(); app.run(host='0.0.0.0', port=8000, debug=True)"

dashboard-install:
	cd dashboard && npm install

dashboard-build:
	cd dashboard && npx tsc

dashboard-watch:
	cd dashboard && npx tsc --watch

# === Rust Targets ===

rust-build:
	cd rust && cargo build

rust-release:
	cd rust && cargo build --release

rust-test:
	cd rust && cargo test

rust-clean:
	cd rust && cargo clean

rust-install: rust-release
	cd rust && pip install maturin 2>/dev/null || true
	cd rust && maturin develop --release 2>/dev/null || \
		echo "Warning: maturin not available. Build the wheel with: cd rust && maturin build --release"

# === Go Targets ===

go-build:
	cd monitor && go build -o monitor-agent .

go-test:
	cd monitor && go test ./...

go-clean:
	rm -f monitor/monitor-agent
	rm -rf monitor/dist/

# === Web App ===

web-run:
	python -m web.app
