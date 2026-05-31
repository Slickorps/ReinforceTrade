//! # OHLCV Aggregator
//!
//! Converts tick-level trade data into OHLCV (Open, High, Low, Close, Volume)
//! candlesticks for arbitrary timeframes.
//!
//! ## Usage
//!
//! ```rust
//! use reforcetrade_engine::aggregator::{OhlcvAggregator, OhlcvCandle};
//!
//! let mut agg = OhlcvAggregator::new(60); // 1-minute candles
//! agg.add_trade(1625097600.0, 35000.0, 0.5);
//! agg.add_trade(1625097610.0, 35100.0, 1.2);
//! let candle = agg.finalize_current();
//! ```

use serde::{Deserialize, Serialize};

/// A single OHLCV candlestick.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OhlcvCandle {
    /// Open time (Unix timestamp in seconds)
    pub open_time: f64,
    /// Close time (Unix timestamp in seconds)
    pub close_time: f64,
    /// Opening price
    pub open: f64,
    /// Highest price
    pub high: f64,
    /// Lowest price
    pub low: f64,
    /// Closing price (last trade price)
    pub close: f64,
    /// Total volume
    pub volume: f64,
    /// Number of trades in this candle
    pub trade_count: u64,
}

impl Default for OhlcvCandle {
    fn default() -> Self {
        Self {
            open_time: 0.0,
            close_time: 0.0,
            open: 0.0,
            high: f64::MIN,
            low: f64::MAX,
            close: 0.0,
            volume: 0.0,
            trade_count: 0,
        }
    }
}

/// Aggregates tick trades into OHLCV candles for a given timeframe.
pub struct OhlcvAggregator {
    /// Candle duration in seconds
    timeframe_secs: f64,
    /// Current candle being built
    current: OhlcvCandle,
    /// Completed candles
    candles: Vec<OhlcvCandle>,
}

impl OhlcvAggregator {
    /// Create a new aggregator for the given timeframe.
    ///
    /// # Arguments
    ///
    /// * `timeframe_secs` - Candle duration in seconds (e.g., 60 for 1m, 300 for 5m)
    pub fn new(timeframe_secs: u64) -> Self {
        Self {
            timeframe_secs: timeframe_secs as f64,
            current: OhlcvCandle::default(),
            candles: Vec::new(),
        }
    }

    /// Add a single trade tick.
    ///
    /// # Arguments
    ///
    /// * `timestamp` - Trade timestamp in Unix seconds (with decimal sub-seconds)
    /// * `price` - Trade price
    /// * `volume` - Trade volume (in base currency units)
    pub fn add_trade(&mut self, timestamp: f64, price: f64, volume: f64) {
        let candle_start = (timestamp / self.timeframe_secs).floor() * self.timeframe_secs;
        let candle_end = candle_start + self.timeframe_secs;

        // If this trade belongs to a new candle, finalize the current one
        if self.current.trade_count > 0 && (timestamp - self.current.close_time).abs() > 1e-9 {
            let last_start = (self.current.close_time / self.timeframe_secs).floor()
                * self.timeframe_secs;
            if (candle_start - last_start).abs() > 1e-9 {
                self.finalize_current();
            }
        }

        // Initialize new candle if needed
        if self.current.trade_count == 0 {
            self.current.open_time = candle_start;
            self.current.close_time = candle_end;
            self.current.open = price;
            self.current.high = price;
            self.current.low = price;
            self.current.close = price;
            self.current.volume = volume;
            self.current.trade_count = 1;
        } else {
            // Update existing candle
            if price > self.current.high {
                self.current.high = price;
            }
            if price < self.current.low {
                self.current.low = price;
            }
            self.current.close = price;
            self.current.volume += volume;
            self.current.trade_count += 1;
        }
    }

    /// Finalize the current candle and return it.
    pub fn finalize_current(&mut self) -> Option<OhlcvCandle> {
        if self.current.trade_count == 0 {
            return None;
        }
        let candle = self.current.clone();
        self.candles.push(candle.clone());
        self.current = OhlcvCandle::default();
        Some(candle)
    }

    /// Get all completed candles.
    pub fn candles(&self) -> &[OhlcvCandle] {
        &self.candles
    }

    /// Consume the aggregator and return all completed candles.
    pub fn into_candles(mut self) -> Vec<OhlcvCandle> {
        self.finalize_current();
        self.candles
    }

    /// Clear all candles (reset state).
    pub fn reset(&mut self) {
        self.current = OhlcvCandle::default();
        self.candles.clear();
    }

    /// Number of completed candles.
    pub fn len(&self) -> usize {
        self.candles.len()
    }

    /// Check if no candles have been completed yet.
    pub fn is_empty(&self) -> bool {
        self.candles.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_single_trade_creates_candle() {
        let mut agg = OhlcvAggregator::new(60);
        agg.add_trade(1625097600.0, 35000.0, 1.0);
        let candle = agg.finalize_current().unwrap();

        assert_eq!(candle.open, 35000.0);
        assert_eq!(candle.high, 35000.0);
        assert_eq!(candle.low, 35000.0);
        assert_eq!(candle.close, 35000.0);
        assert_eq!(candle.volume, 1.0);
        assert_eq!(candle.trade_count, 1);
    }

    #[test]
    fn test_multiple_trades_same_candle() {
        let mut agg = OhlcvAggregator::new(60);
        agg.add_trade(1625097600.0, 35000.0, 1.0);
        agg.add_trade(1625097610.0, 35100.0, 2.0);
        agg.add_trade(1625097620.0, 34900.0, 0.5);

        let candle = agg.finalize_current().unwrap();

        assert_eq!(candle.open, 35000.0);
        assert_eq!(candle.high, 35100.0);
        assert_eq!(candle.low, 34900.0);
        assert_eq!(candle.close, 34900.0);
        assert_eq!(candle.volume, 3.5);
        assert_eq!(candle.trade_count, 3);
    }

    #[test]
    fn test_multiple_candles() {
        let mut agg = OhlcvAggregator::new(60);
        // Candle 1: timestamp 0-59
        agg.add_trade(0.0, 100.0, 1.0);
        agg.add_trade(30.0, 102.0, 2.0);
        // Candle 2: timestamp 60-119
        agg.add_trade(60.0, 103.0, 1.5);
        agg.add_trade(90.0, 101.0, 0.5);

        let candles = agg.into_candles();
        assert_eq!(candles.len(), 2);

        assert_eq!(candles[0].open, 100.0);
        assert_eq!(candles[0].close, 102.0);
        assert_eq!(candles[0].volume, 3.0);

        assert_eq!(candles[1].open, 103.0);
        assert_eq!(candles[1].close, 101.0);
        assert_eq!(candles[1].volume, 2.0);
    }

    #[test]
    fn test_empty_aggregator() {
        let mut agg = OhlcvAggregator::new(60);
        assert!(agg.finalize_current().is_none());
        assert!(agg.is_empty());
        assert_eq!(agg.len(), 0);
    }
}