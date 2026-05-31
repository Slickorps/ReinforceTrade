"""
Broker Factory — Unified adapter instantiation for CCXT, IB, and OANDA.

Provides a single entry point to create any supported broker adapter from
a configuration dictionary or environment variables. This enables runtime
switching between brokers without changing application code.

Usage:
    from trading.broker_factory import create_exchange, list_supported_brokers

    # Create from config dict
    exchange = create_exchange({
        "name": "ib",
        "host": "127.0.0.1",
        "port": 7497,
        "client_id": 1,
    })

    # Create CCXT exchange
    exchange = create_exchange({
        "name": "ccxt",
        "exchange_id": "binance",
        "api_key": "...",
        "secret": "...",
    })

    # List available brokers
    print(list_supported_brokers())
"""

from typing import Dict, Any, Optional
from .exchange import Exchange
from utils.logger import logger


def create_exchange(config: Dict[str, Any]) -> Exchange:
    """
    Create a broker adapter instance from a configuration dictionary.

    The configuration must include a ``name`` key identifying the broker type.
    Supported values: ``"ccxt"``, ``"ib"``, ``"oanda"``.

    Args:
        config: Broker configuration dictionary.
            Required key: ``name`` (str).
            Broker-specific keys are forwarded to the adapter constructor.

    Returns:
        An :class:`Exchange` adapter instance.

    Raises:
        ValueError: If the broker name is unknown or required keys are missing.
    """
    name = config.get("name", "").lower().strip()
    if not name:
        raise ValueError(
            "Broker name is required in config (key: 'name'). "
            f"Supported: {', '.join(list_supported_brokers())}"
        )

    if name == "ccxt":
        return _create_ccxt(config)
    elif name == "ib":
        return _create_ib(config)
    elif name == "oanda":
        return _create_oanda(config)
    else:
        raise ValueError(
            f"Unknown broker '{name}'. "
            f"Supported brokers: {', '.join(list_supported_brokers())}"
        )


def list_supported_brokers() -> list:
    """
    Return a list of supported broker names.

    Returns:
        List of strings: ``["ccxt", "ib", "oanda"]``
    """
    return ["ccxt", "ib", "oanda"]


# ---------------------------------------------------------------------------
# Internal constructors
# ---------------------------------------------------------------------------

def _create_ccxt(config: Dict[str, Any]) -> Exchange:
    """Create a CCXT exchange adapter."""
    from .ccxt_exchange import CCXTExchange

    exchange_name = config.get("exchange_id", "")
    if not exchange_name:
        raise ValueError("CCXT adapter requires 'exchange_id' in config")

    return CCXTExchange(
        api_key=config.get("api_key", ""),
        secret=config.get("secret", ""),
        exchange_name=exchange_name,
        sandbox=config.get("sandbox", True),
    )


def _create_ib(config: Dict[str, Any]) -> Exchange:
    """Create an Interactive Brokers adapter."""
    from .ib_adapter import IBAdapter

    return IBAdapter(
        api_key="",
        secret="",
        host=config.get("host", "127.0.0.1"),
        port=int(config.get("port", 7497)),
        client_id=int(config.get("client_id", 1)),
        account=config.get("account"),
    )


def _create_oanda(config: Dict[str, Any]) -> Exchange:
    """Create an OANDA adapter."""
    from .oanda_adapter import OANDAdapter

    return OANDAdapter(
        api_key=config.get("api_key", ""),
        secret=config.get("secret", ""),
        environment=config.get("environment", "practice"),
        account_id=config.get("account_id"),
    )