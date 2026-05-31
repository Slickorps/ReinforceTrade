//! # Financial Metrics
//!
//! High-performance calculations for common financial metrics used in
//! backtesting and strategy evaluation, including Sharpe ratio, Sortino ratio,
//! maximum drawdown, and more.

use serde::{Deserialize, Serialize};
use crate::stats;

/// Financial performance metrics for a trading strategy.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FinancialMetrics {
    /// Total return as a decimal (e.g., 0.15 = 15%)
    pub total_return: f64,
    /// Annualized return as a decimal
    pub annualized_return: f64,
    /// Annualized volatility as a decimal
    pub annualized_volatility: f64,
    /// Sharpe ratio (risk-free rate assumed 0)
    pub sharpe_ratio: f64,
    /// Sortino ratio (downside deviation only)
    pub sortino_ratio: f64,
    /// Maximum drawdown as a decimal (e.g., 0.25 = 25% loss)
    pub max_drawdown: f64,
    /// Calmar ratio (annualized return / max drawdown)
    pub calmar_ratio: f64,
    /// Win rate as a decimal
    pub win_rate: f64,
    /// Profit factor (gross profit / gross loss)
    pub profit_factor: f64,
    /// Total number of trades
    pub total_trades: u64,
}

impl Default for FinancialMetrics {
    fn default() -> Self {
        Self {
            total_return: 0.0,
            annualized_return: 0.0,
            annualized_volatility: 0.0,
            sharpe_ratio: 0.0,
            sortino_ratio: 0.0,
            max_drawdown: 0.0,
            calmar_ratio: 0.0,
            win_rate: 0.0,
            profit_factor: 0.0,
            total_trades: 0,
        }
    }
}

/// Compute annualized Sharpe ratio from daily returns.
///
/// `sharpe = mean(returns - rf) / std(returns) * sqrt(periods_per_year)`
///
/// # Arguments
///
/// * `returns` - Slice of periodic returns (e.g., daily)
/// * `risk_free_rate` - Annual risk-free rate (e.g., 0.05 for 5%)
/// * `periods_per_year` - Number of periods in a year (252 for daily, 52 for weekly, 12 for monthly)
///
/// # Returns
///
/// Annualized Sharpe ratio.
pub fn sharpe_ratio(returns: &[f64], risk_free_rate: f64, periods_per_year: f64) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }

    let rf_per_period = risk_free_rate / periods_per_year;
    let excess_returns: Vec<f64> = returns.iter().map(|r| r - rf_per_period).collect();

    match stats::compute_series_stats(&excess_returns) {
        Some(stats) if stats.std_dev > 0.0 => {
            (stats.mean / stats.std_dev) * periods_per_year.sqrt()
        }
        _ => 0.0,
    }
}

/// Compute Sortino ratio using only downside deviation.
///
/// # Arguments
///
/// * `returns` - Slice of periodic returns
/// * `risk_free_rate` - Annual risk-free rate
/// * `periods_per_year` - Number of periods in a year
///
/// # Returns
///
/// Annualized Sortino ratio.
pub fn sortino_ratio(returns: &[f64], risk_free_rate: f64, periods_per_year: f64) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }

    let rf_per_period = risk_free_rate / periods_per_year;
    let n = returns.len() as f64;

    // Mean return
    let mean_return = returns.iter().sum::<f64>() / n;

    // Downside deviation (only negative excess returns)
    let mut downside_sum = 0.0;
    let mut downside_count = 0;

    for &r in returns {
        let excess = r - rf_per_period;
        if excess < mean_return {
            downside_sum += (excess - mean_return).powi(2);
            downside_count += 1;
        }
    }

    if downside_count == 0 {
        return 0.0;
    }

    let downside_dev = (downside_sum / n).sqrt();
    if downside_dev <= 0.0 {
        return 0.0;
    }

    let excess_return = mean_return - rf_per_period;
    (excess_return / downside_dev) * periods_per_year.sqrt()
}

/// Compute maximum drawdown from a cumulative equity curve.
///
/// # Arguments
///
/// * `equity_curve` - Slice of cumulative equity values (e.g., portfolio values over time)
///
/// # Returns
///
/// Maximum drawdown as a positive decimal (e.g., 0.25 means 25% peak-to-trough loss).
pub fn max_drawdown(equity_curve: &[f64]) -> f64 {
    if equity_curve.len() < 2 {
        return 0.0;
    }

    let mut peak = equity_curve[0];
    let mut max_dd = 0.0;

    for &value in equity_curve.iter().skip(1) {
        if value > peak {
            peak = value;
        }
        let dd = (peak - value) / peak;
        if dd > max_dd {
            max_dd = dd;
        }
    }

    max_dd
}

/// Compute drawdown series from an equity curve.
///
/// # Arguments
///
/// * `equity_curve` - Cumulative equity values
///
/// # Returns
///
/// Vector of drawdown values for each point (0.0 = no drawdown).
pub fn drawdown_series(equity_curve: &[f64]) -> Vec<f64> {
    if equity_curve.is_empty() {
        return vec![];
    }

    let mut peak = equity_curve[0];
    let mut dds = Vec::with_capacity(equity_curve.len());

    for &value in equity_curve {
        if value > peak {
            peak = value;
        }
        dds.push(if peak > 0.0 {
            (peak - value) / peak
        } else {
            0.0
        });
    }

    dds
}

/// Compute profit factor (gross profit / gross loss).
///
/// # Arguments
///
/// * `trade_returns` - Slice of individual trade P&L values (positive = win, negative = loss)
///
/// # Returns
///
/// Profit factor. Returns `f64::MAX` if no losing trades.
pub fn profit_factor(trade_returns: &[f64]) -> f64 {
    let mut gross_profit = 0.0;
    let mut gross_loss = 0.0;

    for &r in trade_returns {
        if r > 0.0 {
            gross_profit += r;
        } else {
            gross_loss += r.abs();
        }
    }

    if gross_loss == 0.0 {
        if gross_profit > 0.0 {
            return f64::MAX;
        }
        return 0.0;
    }

    gross_profit / gross_loss
}

/// Compute win rate from a series of trade returns.
///
/// # Arguments
///
/// * `trade_returns` - Individual trade P&L values
///
/// # Returns
///
/// Win rate as a decimal (0.0 to 1.0).
pub fn win_rate(trade_returns: &[f64]) -> f64 {
    if trade_returns.is_empty() {
        return 0.0;
    }

    let wins = trade_returns.iter().filter(|&&r| r > 0.0).count();
    wins as f64 / trade_returns.len() as f64
}

/// Compute comprehensive financial metrics for a backtest.
///
/// # Arguments
///
/// * `equity_curve` - Portfolio equity curve over time
/// * `returns` - Periodic returns (same length as equity_curve - 1)
/// * `trade_returns` - Individual trade P&L values
/// * `risk_free_rate` - Annual risk-free rate
/// * `periods_per_year` - Periods per year for annualization
///
/// # Returns
///
/// Complete `FinancialMetrics` struct.
pub fn compute_all_metrics(
    equity_curve: &[f64],
    returns: &[f64],
    trade_returns: &[f64],
    risk_free_rate: f64,
    periods_per_year: f64,
) -> FinancialMetrics {
    let total_return = if equity_curve.len() >= 2 && equity_curve[0] > 0.0 {
        (equity_curve.last().unwrap() - equity_curve[0]) / equity_curve[0]
    } else {
        0.0
    };

    let num_periods = returns.len() as f64;
    let annualized_return = if num_periods > 0.0 && equity_curve[0] > 0.0 {
        (1.0 + total_return).powf(periods_per_year / num_periods) - 1.0
    } else {
        0.0
    };

    let sharpe = sharpe_ratio(returns, risk_free_rate, periods_per_year);
    let sortino = sortino_ratio(returns, risk_free_rate, periods_per_year);
    let max_dd = max_drawdown(equity_curve);
    let calmar = if max_dd > 0.0 {
        annualized_return / max_dd
    } else {
        0.0
    };

    // Volatility
    let annualized_vol = match stats::compute_series_stats(returns) {
        Some(s) if s.std_dev > 0.0 => s.std_dev * periods_per_year.sqrt(),
        _ => 0.0,
    };

    FinancialMetrics {
        total_return,
        annualized_return,
        annualized_volatility: annualized_vol,
        sharpe_ratio: sharpe,
        sortino_ratio: sortino,
        max_drawdown: max_dd,
        calmar_ratio: calmar,
        win_rate: win_rate(trade_returns),
        profit_factor: profit_factor(trade_returns),
        total_trades: trade_returns.len() as u64,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sharpe_ratio_constant_returns() {
        // Constant returns => zero volatility => 0 Sharpe
        let returns = vec![0.01; 100];
        let sharpe = sharpe_ratio(&returns, 0.0, 252.0);
        assert!(sharpe == 0.0);
    }

    #[test]
    fn test_sharpe_ratio_positive() {
        let returns = vec![0.001, 0.002, -0.001, 0.003, 0.001, 0.002];
        let sharpe = sharpe_ratio(&returns, 0.0, 252.0);
        assert!(sharpe > 0.0);
    }

    #[test]
    fn test_sharpe_ratio_negative() {
        let returns = vec![-0.01, -0.02, -0.015, -0.01];
        let sharpe = sharpe_ratio(&returns, 0.0, 252.0);
        assert!(sharpe < 0.0);
    }

    #[test]
    fn test_max_drawdown_simple() {
        let equity = vec![100.0, 110.0, 90.0, 95.0, 80.0, 85.0];
        let mdd = max_drawdown(&equity);
        // Peak = 110, trough = 80 => DD = (110-80)/110 ≈ 0.2727
        assert!((mdd - 0.272727).abs() < 1e-5);
    }

    #[test]
    fn test_max_drawdown_monotonic_up() {
        let equity = vec![100.0, 110.0, 120.0, 130.0];
        let mdd = max_drawdown(&equity);
        assert_eq!(mdd, 0.0);
    }

    #[test]
    fn test_max_drawdown_single_value() {
        assert_eq!(max_drawdown(&[100.0]), 0.0);
    }

    #[test]
    fn test_profit_factor() {
        let trades = vec![100.0, -50.0, 200.0, -30.0, 50.0];
        let pf = profit_factor(&trades);
        // Gross profit = 350, Gross loss = 80 => 4.375
        assert!((pf - 4.375).abs() < 1e-10);
    }

    #[test]
    fn test_profit_factor_all_wins() {
        assert_eq!(profit_factor(&[10.0, 20.0, 30.0]), f64::MAX);
    }

    #[test]
    fn test_win_rate() {
        let trades = vec![10.0, -5.0, 15.0, -3.0, 0.0, 8.0];
        let wr = win_rate(&trades);
        // 3 wins out of 6 (excluding 0 as not win)
        assert!((wr - 0.5).abs() < 1e-10);
    }

    #[test]
    fn test_drawdown_series() {
        let equity = vec![100.0, 110.0, 105.0, 95.0, 100.0];
        let dds = drawdown_series(&equity);
        assert!((dds[0] - 0.0).abs() < 1e-10);
        assert!((dds[1] - 0.0).abs() < 1e-10);
        assert!((dds[2] - (5.0 / 110.0)).abs() < 1e-10);
        assert!((dds[3] - (15.0 / 110.0)).abs() < 1e-10);
        assert!((dds[4] - (10.0 / 110.0)).abs() < 1e-10);
    }
}