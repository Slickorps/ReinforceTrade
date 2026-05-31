//! # Python FFI Bindings
//!
//! PyO3 bindings that expose the Rust engine to Python as a native module.
//! This allows Python backtesting code to call high-performance Rust functions
//! for CPU-intensive calculations.
//!
//! ## Usage (Python side)
//!
//! ```python
//! from reforcetrade_engine import compute_financial_metrics
//!
//! metrics = compute_financial_metrics(
//!     equity_curve=[100.0, 110.0, 105.0, 115.0],
//!     returns=[0.1, -0.045, 0.095],
//!     trade_returns=[10.0, -5.0, 15.0],
//!     risk_free_rate=0.05,
//!     periods_per_year=252
//! )
//! print(metrics.sharpe_ratio)
//! ```

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use crate::aggregator::{OhlcvAggregator, OhlcvCandle};
use crate::metrics::{self, FinancialMetrics};
use crate::stats::{self, SeriesStats, PairStats};

/// Python class wrapping the OHLCV aggregator.
#[pyclass(name = "OhlcvAggregator")]
struct PyOhlcvAggregator {
    inner: OhlcvAggregator,
}

#[pymethods]
impl PyOhlcvAggregator {
    #[new]
    fn new(timeframe_secs: u64) -> Self {
        Self {
            inner: OhlcvAggregator::new(timeframe_secs),
        }
    }

    fn add_trade(&mut self, timestamp: f64, price: f64, volume: f64) {
        self.inner.add_trade(timestamp, price, volume);
    }

    fn finalize_current(&mut self) -> Option<PyOhlcvCandle> {
        self.inner.finalize_current().map(|c| PyOhlcvCandle(c))
    }

    fn len(&self) -> usize {
        self.inner.len()
    }

    fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    fn reset(&mut self) {
        self.inner.reset();
    }

    fn __len__(&self) -> usize {
        self.inner.len()
    }
}

/// Python wrapper for OHLCV candle.
#[pyclass(name = "OhlcvCandle")]
#[derive(Clone)]
struct PyOhlcvCandle(OhlcvCandle);

#[pymethods]
impl PyOhlcvCandle {
    #[getter]
    fn open_time(&self) -> f64 {
        self.0.open_time
    }

    #[getter]
    fn close_time(&self) -> f64 {
        self.0.close_time
    }

    #[getter]
    fn open(&self) -> f64 {
        self.0.open
    }

    #[getter]
    fn high(&self) -> f64 {
        self.0.high
    }

    #[getter]
    fn low(&self) -> f64 {
        self.0.low
    }

    #[getter]
    fn close(&self) -> f64 {
        self.0.close
    }

    #[getter]
    fn volume(&self) -> f64 {
        self.0.volume
    }

    #[getter]
    fn trade_count(&self) -> u64 {
        self.0.trade_count
    }

    fn __repr__(&self) -> String {
        format!(
            "OhlcvCandle(o={:.2}, h={:.2}, l={:.2}, c={:.2}, v={:.2}, trades={})",
            self.0.open, self.0.high, self.0.low, self.0.close, self.0.volume, self.0.trade_count
        )
    }
}

/// Python wrapper for series statistics.
#[pyclass(name = "SeriesStats")]
#[derive(Clone)]
struct PySeriesStats(SeriesStats);

#[pymethods]
impl PySeriesStats {
    #[getter]
    fn count(&self) -> usize {
        self.0.count
    }

    #[getter]
    fn mean(&self) -> f64 {
        self.0.mean
    }

    #[getter]
    fn variance(&self) -> f64 {
        self.0.variance
    }

    #[getter]
    fn std_dev(&self) -> f64 {
        self.0.std_dev
    }

    #[getter]
    fn min(&self) -> f64 {
        self.0.min
    }

    #[getter]
    fn max(&self) -> f64 {
        self.0.max
    }

    #[getter]
    fn sum(&self) -> f64 {
        self.0.sum
    }

    fn __repr__(&self) -> String {
        format!(
            "SeriesStats(count={}, mean={:.4}, std={:.4}, min={:.4}, max={:.4})",
            self.0.count, self.0.mean, self.0.std_dev, self.0.min, self.0.max
        )
    }
}

/// Python wrapper for pair statistics.
#[pyclass(name = "PairStats")]
#[derive(Clone)]
struct PyPairStats(PairStats);

#[pymethods]
impl PyPairStats {
    #[getter]
    fn covariance(&self) -> f64 {
        self.0.covariance
    }

    #[getter]
    fn correlation(&self) -> f64 {
        self.0.correlation
    }

    #[getter]
    fn beta(&self) -> f64 {
        self.0.beta
    }

    fn __repr__(&self) -> String {
        format!(
            "PairStats(cov={:.4}, corr={:.4}, beta={:.4})",
            self.0.covariance, self.0.correlation, self.0.beta
        )
    }
}

/// Python wrapper for financial metrics.
#[pyclass(name = "FinancialMetrics")]
#[derive(Clone)]
struct PyFinancialMetrics(FinancialMetrics);

#[pymethods]
impl PyFinancialMetrics {
    #[getter]
    fn total_return(&self) -> f64 {
        self.0.total_return
    }

    #[getter]
    fn annualized_return(&self) -> f64 {
        self.0.annualized_return
    }

    #[getter]
    fn annualized_volatility(&self) -> f64 {
        self.0.annualized_volatility
    }

    #[getter]
    fn sharpe_ratio(&self) -> f64 {
        self.0.sharpe_ratio
    }

    #[getter]
    fn sortino_ratio(&self) -> f64 {
        self.0.sortino_ratio
    }

    #[getter]
    fn max_drawdown(&self) -> f64 {
        self.0.max_drawdown
    }

    #[getter]
    fn calmar_ratio(&self) -> f64 {
        self.0.calmar_ratio
    }

    #[getter]
    fn win_rate(&self) -> f64 {
        self.0.win_rate
    }

    #[getter]
    fn profit_factor(&self) -> f64 {
        self.0.profit_factor
    }

    #[getter]
    fn total_trades(&self) -> u64 {
        self.0.total_trades
    }

    fn __repr__(&self) -> String {
        format!(
            "FinancialMetrics(return={:.2%}, sharpe={:.2}, sortino={:.2}, mdd={:.2%})",
            self.0.total_return, self.0.sharpe_ratio, self.0.sortino_ratio, self.0.max_drawdown
        )
    }
}

// ---- Free functions exposed to Python ----

/// Compute summary statistics for a series of values.
#[pyfunction]
fn compute_series_stats(values: Vec<f64>) -> Option<PySeriesStats> {
    stats::compute_series_stats(&values).map(PySeriesStats)
}

/// Compute covariance and correlation between two series.
#[pyfunction]
fn compute_pair_stats(a: Vec<f64>, b: Vec<f64>) -> Option<PyPairStats> {
    stats::compute_pair_stats(&a, &b).map(PyPairStats)
}

/// Compute simple moving average.
#[pyfunction]
fn simple_moving_average(values: Vec<f64>, window: usize) -> Vec<f64> {
    stats::simple_moving_average(&values, window)
}

/// Compute exponential moving average.
#[pyfunction]
fn exponential_moving_average(values: Vec<f64>, period: usize) -> Vec<f64> {
    stats::exponential_moving_average(&values, period)
}

/// Compute annualized Sharpe ratio.
#[pyfunction]
fn sharpe_ratio(returns: Vec<f64>, risk_free_rate: f64, periods_per_year: f64) -> f64 {
    metrics::sharpe_ratio(&returns, risk_free_rate, periods_per_year)
}

/// Compute Sortino ratio.
#[pyfunction]
fn sortino_ratio(returns: Vec<f64>, risk_free_rate: f64, periods_per_year: f64) -> f64 {
    metrics::sortino_ratio(&returns, risk_free_rate, periods_per_year)
}

/// Compute maximum drawdown from an equity curve.
#[pyfunction]
fn max_drawdown(equity_curve: Vec<f64>) -> f64 {
    metrics::max_drawdown(&equity_curve)
}

/// Compute drawdown series from an equity curve.
#[pyfunction]
fn drawdown_series(equity_curve: Vec<f64>) -> Vec<f64> {
    metrics::drawdown_series(&equity_curve)
}

/// Compute profit factor from trade returns.
#[pyfunction]
fn profit_factor(trade_returns: Vec<f64>) -> f64 {
    metrics::profit_factor(&trade_returns)
}

/// Compute win rate from trade returns.
#[pyfunction]
fn win_rate(trade_returns: Vec<f64>) -> f64 {
    metrics::win_rate(&trade_returns)
}

/// Compute comprehensive financial metrics for a backtest.
#[pyfunction]
fn compute_all_metrics(
    equity_curve: Vec<f64>,
    returns: Vec<f64>,
    trade_returns: Vec<f64>,
    risk_free_rate: f64,
    periods_per_year: f64,
) -> PyFinancialMetrics {
    PyFinancialMetrics(metrics::compute_all_metrics(
        &equity_curve,
        &returns,
        &trade_returns,
        risk_free_rate,
        periods_per_year,
    ))
}

/// Register the Python module.
#[pymodule]
fn reforcetrade_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyOhlcvAggregator>()?;
    m.add_class::<PyOhlcvCandle>()?;
    m.add_class::<PySeriesStats>()?;
    m.add_class::<PyPairStats>()?;
    m.add_class::<PyFinancialMetrics>()?;

    m.add_function(wrap_pyfunction!(compute_series_stats, m)?)?;
    m.add_function(wrap_pyfunction!(compute_pair_stats, m)?)?;
    m.add_function(wrap_pyfunction!(simple_moving_average, m)?)?;
    m.add_function(wrap_pyfunction!(exponential_moving_average, m)?)?;
    m.add_function(wrap_pyfunction!(sharpe_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(sortino_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(max_drawdown, m)?)?;
    m.add_function(wrap_pyfunction!(drawdown_series, m)?)?;
    m.add_function(wrap_pyfunction!(profit_factor, m)?)?;
    m.add_function(wrap_pyfunction!(win_rate, m)?)?;
    m.add_function(wrap_pyfunction!(compute_all_metrics, m)?)?;

    Ok(())
}