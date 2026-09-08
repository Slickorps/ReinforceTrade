from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class Exchange(ABC):
    @abstractmethod
    def __init__(self, api_key: str, secret: str):
        pass

    @abstractmethod
    def get_balance(self) -> Dict[str, float]:
        pass

    @abstractmethod
    def get_market_data(self, symbol: str, timeframe: str, limit: int) -> list:
        pass

    @abstractmethod
    def place_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass
