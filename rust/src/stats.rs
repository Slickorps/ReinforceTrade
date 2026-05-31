//! # Statistical Calculators
//!
//! High-performance statistical calculations for financial time series data.
//! Provides mean, variance, covariance, correlation, and standard deviation
//! with numerically stable single-pass algorithms.

use serde::{Deserialize, Serialize};

/// Summary statistics for a single series.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeriesStats {
    /// Number of observations
    pub count: usize,
    /// Arithmetic mean
    pub mean: f64,
    /// Variance (population)
    pub variance: f64,
    /// Standard deviation (population)
    pub std_dev: f64,
    /// Minimum value
    pub min: f64,
    /// Maximum value
    pub max: f64,
    /// Sum of all values
    pub sum: f64,
}

impl Default for SeriesStats {
    fn default() -> Self {
        Self {
            count: 0,
            mean: 0.0,
            variance: 0.0,
            std_dev: 0.0,
            min: f64::MAX,
            max: f64::MIN,
            sum: 0.0,
        }
    }
}

/// Result of a pair-wise statistical analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PairStats {
    /// Covariance between the two series
    pub covariance: f64,
    /// Pearson correlation coefficient
    pub correlation: f64,
    /// Beta of series A relative to series B
    pub beta: f64,
}

/// Compute summary statistics for a slice of values.
///
/// Uses Welford's online algorithm for numerically stable variance calculation.
///
/// # Arguments
///
/// * `values` - Slice of f64 values
///
/// # Returns
///
/// `Some(SeriesStats)` if the slice is non-empty, `None` otherwise.
pub fn compute_series_stats(values: &[f64]) -> Option<SeriesStats> {
    let n = values.len();
    if n == 0 {
        return None;
    }

    let mut stats = SeriesStats::default();
    let mut mean = 0.0;
    let mut m2 = 0.0; // Sum of squared differences from current mean

    for (i, &val) in values.iter().enumerate() {
        stats.count = i + 1;
        stats.sum += val;

        if val < stats.min {
            stats.min = val;
        }
        if val > stats.max {
            stats.max = val;
        }

        // Welford's algorithm
        let delta = val - mean;
        mean += delta / (i + 1) as f64;
        let delta2 = val - mean;
        m2 += delta * delta2;
    }

    stats.mean = mean;
    stats.variance = m2 / n as f64;
    stats.std_dev = stats.variance.sqrt();

    Some(stats)
}

/// Compute covariance and correlation between two series.
///
/// Both slices must have the same length.
///
/// # Arguments
///
/// * `a` - First series
/// * `b` - Second series
///
/// # Returns
///
/// `Some(PairStats)` if both slices are non-empty and same length, `None` otherwise.
pub fn compute_pair_stats(a: &[f64], b: &[f64]) -> Option<PairStats> {
    let n = a.len();
    if n == 0 || n != b.len() {
        return None;
    }

    // Compute means
    let mean_a = a.iter().sum::<f64>() / n as f64;
    let mean_b = b.iter().sum::<f64>() / n as f64;

    // Compute covariance and variances
    let mut cov = 0.0;
    let mut var_a = 0.0;
    let mut var_b = 0.0;

    for i in 0..n {
        let da = a[i] - mean_a;
        let db = b[i] - mean_b;
        cov += da * db;
        var_a += da * da;
        var_b += db * db;
    }

    cov /= n as f64;
    var_a /= n as f64;
    var_b /= n as f64;

    let correlation = if var_a > 0.0 && var_b > 0.0 {
        cov / (var_a.sqrt() * var_b.sqrt())
    } else {
        0.0
    };

    let beta = if var_a > 0.0 { cov / var_a } else { 0.0 };

    Some(PairStats {
        covariance: cov,
        correlation,
        beta,
    })
}

/// Compute a simple moving average (SMA) over a window.
///
/// # Arguments
///
/// * `values` - Input series
/// * `window` - Window size
///
/// # Returns
///
/// Vector of SMA values, padded with `f64::NAN` for the first `window - 1` positions.
pub fn simple_moving_average(values: &[f64], window: usize) -> Vec<f64> {
    if window == 0 || window > values.len() {
        return vec![f64::NAN; values.len()];
    }

    let mut result = vec![f64::NAN; window - 1];
    let mut sum: f64 = values[..window].iter().sum();

    result.push(sum / window as f64);

    for i in window..values.len() {
        sum += values[i] - values[i - window];
        result.push(sum / window as f64);
    }

    result
}

/// Compute an exponential moving average (EMA).
///
/// # Arguments
///
/// * `values` - Input series
/// * `period` - Smoothing period
///
/// # Returns
///
/// Vector of EMA values.
pub fn exponential_moving_average(values: &[f64], period: usize) -> Vec<f64> {
    if period == 0 || values.is_empty() {
        return vec![];
    }

    let k = 2.0 / (period + 1) as f64;
    let mut result = Vec::with_capacity(values.len());

    // Start with SMA as initial EMA value
    if values.len() >= period {
        let sma: f64 = values[..period].iter().sum::<f64>() / period as f64;
        result.push(sma);

        for &val in &values[period..] {
            let ema = val * k + result.last().unwrap() * (1.0 - k);
            result.push(ema);
        }
    } else {
        // Not enough data, use simple average as fallback
        let mut ema = values[0];
        result.push(ema);
        for &val in &values[1..] {
            ema = val * k + ema * (1.0 - k);
            result.push(ema);
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_series_stats_basic() {
        let values = vec![2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
        let stats = compute_series_stats(&values).unwrap();

        assert_eq!(stats.count, 8);
        assert!((stats.mean - 5.0).abs() < 1e-10);
        assert!((stats.variance - 4.0).abs() < 1e-10);
        assert!((stats.std_dev - 2.0).abs() < 1e-10);
        assert!((stats.min - 2.0).abs() < 1e-10);
        assert!((stats.max - 9.0).abs() < 1e-10);
        assert!((stats.sum - 40.0).abs() < 1e-10);
    }

    #[test]
    fn test_series_stats_empty() {
        assert!(compute_series_stats(&[]).is_none());
    }

    #[test]
    fn test_series_stats_single_value() {
        let stats = compute_series_stats(&[42.0]).unwrap();
        assert_eq!(stats.count, 1);
        assert!((stats.mean - 42.0).abs() < 1e-10);
        assert!((stats.variance - 0.0).abs() < 1e-10);
    }

    #[test]
    fn test_pair_stats_basic() {
        let a = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let b = vec![2.0, 4.0, 6.0, 8.0, 10.0];

        let stats = compute_pair_stats(&a, &b).unwrap();
        assert!((stats.correlation - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_pair_stats_inverse() {
        let a = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let b = vec![5.0, 4.0, 3.0, 2.0, 1.0];

        let stats = compute_pair_stats(&a, &b).unwrap();
        assert!((stats.correlation - (-1.0)).abs() < 1e-10);
    }

    #[test]
    fn test_sma_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let sma = simple_moving_average(&values, 3);

        assert!(sma[0].is_nan());
        assert!(sma[1].is_nan());
        assert!((sma[2] - 2.0).abs() < 1e-10); // (1+2+3)/3
        assert!((sma[3] - 3.0).abs() < 1e-10); // (2+3+4)/3
        assert!((sma[4] - 4.0).abs() < 1e-10); // (3+4+5)/3
    }

    #[test]
    fn test_ema_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let ema = exponential_moving_average(&values, 3);

        // First value should be SMA(3) = 2.0
        assert!((ema[0] - 2.0).abs() < 1e-10);
        // Subsequent values follow EMA formula
        assert!(ema.len() == 3);
    }
}