try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
import os

class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///reinforcetrade.db")
    exchange_api_key: str = os.getenv("EXCHANGE_API_KEY", "")
    exchange_secret: str = os.getenv("EXCHANGE_SECRET", "")
    exchange_name: str = os.getenv("EXCHANGE_NAME", "binance")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    max_position_size: float = float(os.getenv("MAX_POSITION_SIZE", "0.1"))
    risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", "0.01"))

    class Config:
        env_file = ".env"

settings = Settings()
