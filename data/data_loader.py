import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import ccxt
from datetime import datetime, timedelta
from utils.logger import logger

class DataLoader:
    """
    Handles loading and preprocessing of historical market data.
    Supports CSV files and live exchange data via CCXT.
    """
    def __init__(self, exchange_name: str = 'binance', api_key: Optional[str] = None, secret: Optional[str] = None):
        self.exchange_name = exchange_name
        if api_key and secret:
            self.exchange = getattr(ccxt, exchange_name)({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
            })
        else:
            self.exchange = getattr(ccxt, exchange_name)()

    def load_from_csv(self, filepath: str, date_column: str = 'timestamp', price_columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Load data from CSV file.
        Expected columns: timestamp, open, high, low, close, volume
        """
        try:
            df = pd.read_csv(filepath)
            logger.info(f"Loaded {len(df)} rows from {filepath}")

            # Convert timestamp if needed
            if date_column in df.columns:
                df[date_column] = pd.to_datetime(df[date_column])
                df['timestamp'] = df[date_column].astype(np.int64) // 10**9  # Convert to unix timestamp

            # Ensure required columns exist
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    logger.warning(f"Column {col} not found in CSV")
                    if col == 'volume':
                        df['volume'] = 0
                    else:
                        raise ValueError(f"Required column {col} missing from CSV")

            # Convert to list of dicts
            data = df[required_cols].to_dict('records')
            return data

        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            raise

    def fetch_historical_data(self, symbol: str, timeframe: str = '1h', limit: int = 1000,
                             start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch historical data from exchange.
        """
        try:
            if start_date:
                since = int(pd.to_datetime(start_date).timestamp() * 1000)
            else:
                since = None

            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)

            data = []
            for candle in ohlcv:
                data.append({
                    'timestamp': candle[0] // 1000,  # Convert to seconds
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'volume': candle[5]
                })

            logger.info(f"Fetched {len(data)} candles for {symbol}")
            return data

        except Exception as e:
            logger.error(f"Error fetching data from {self.exchange_name}: {e}")
            raise

    def preprocess_data(self, data: List[Dict[str, Any]], add_technical_indicators: bool = True) -> pd.DataFrame:
        """
        Preprocess raw data and add technical indicators.
        """
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

        if add_technical_indicators:
            # Add simple moving averages
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()

            # Add RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))

            # Add MACD
            ema_12 = df['close'].ewm(span=12).mean()
            ema_26 = df['close'].ewm(span=26).mean()
            df['macd'] = ema_12 - ema_26
            df['macd_signal'] = df['macd'].ewm(span=9).mean()

            # Add Bollinger Bands
            sma_20 = df['close'].rolling(window=20).mean()
            std_20 = df['close'].rolling(window=20).std()
            df['bb_upper'] = sma_20 + (std_20 * 2)
            df['bb_lower'] = sma_20 - (std_20 * 2)

        # Fill NaN values
        df = df.fillna(method='bfill').fillna(method='ffill').fillna(0)

        logger.info(f"Preprocessed data with {len(df)} rows and {len(df.columns)} columns")
        return df

    def split_train_test(self, data: pd.DataFrame, train_ratio: float = 0.8) -> tuple:
        """
        Split data into training and testing sets.
        """
        split_idx = int(len(data) * train_ratio)
        train_data = data[:split_idx].to_dict('records')
        test_data = data[split_idx:].to_dict('records')

        logger.info(f"Split data: {len(train_data)} train, {len(test_data)} test")
        return train_data, test_data
