//! # ReinforceTrade Engine
//!
//! High-performance Rust engine for quantitative trading calculations.
//! Provides OHLCV aggregation, statistical analysis, and financial metrics.
//!
//! ## Modules
//!
//! - `aggregator` - Tick-to-candle OHLCV aggregation
//! - `stats` - Statistical calculations (mean, variance, covariance)
//! - `metrics` - Financial metrics (Sharpe, Sortino, Max Drawdown)
//! - `py_bindings` - Python FFI bindings via PyO3

pub mod aggregator;
pub mod metrics;
pub mod stats;

#[cfg(feature = "pyo3")]
pub mod py_bindings;