"""
Broker Adapter Example
======================

Demonstrates how to use the Interactive Brokers (IB) and OANDA broker
adapters through the unified Exchange interface.

All adapters share the same interface:
    - get_balance()
    - get_market_data(symbol, timeframe, limit)
    - place_order(symbol, side, amount, ...)
    - cancel_order(order_id)
    - check_connection()
    - get_supported_symbols()

This makes it easy to switch between brokers or run multiple brokers
simultaneously.

Usage:
    python examples/broker_adapter_example.py

Note:
    The adapters run in stub mode by default, returning mock data.
    To use live trading, install the required library and provide
    valid API credentials:
    
        pip install ib_insync      # For IB
        pip install oandapyV20     # For OANDA
"""

import sys
import os
import time
import json
from typing import Dict, Any

# Add project root to path so we can import trading modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_separator(title: str) -> None:
    """Print a formatted section separator."""
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_json(label: str, data: Any) -> None:
    """Print labeled JSON data."""
    print(f"\n  {label}:")
    print(f"    {json.dumps(data, indent=4)}")


def demonstrate_adapter(name: str, exchange: Any) -> None:
    """
    Demonstrate the full Exchange interface on a given adapter.
    
    Args:
        name: Human-readable adapter name
        exchange: An Exchange interface implementation
    """
    print_separator(f"{name} — Exchange Interface Demo")

    # 1. Check connection
    print(f"\n  ▶ Step 1: Check Connection")
    connected = exchange.check_connection()
    print(f"    Connected: {connected}")

    # 2. Get supported symbols
    print(f"\n  ▶ Step 2: Supported Symbols")
    symbols = exchange.get_supported_symbols()
    print(f"    Count: {len(symbols)}")
    for sym in symbols[:5]:
        print(f"      • {sym}")
    if len(symbols) > 5:
        print(f"      ... and {len(symbols) - 5} more")

    # 3. Get account balance
    print(f"\n  ▶ Step 3: Account Balance")
    balance = exchange.get_balance()
    for currency, amount in balance.items():
        print(f"      {currency}: {amount:>12,.2f}")

    # 4. Get market data
    print(f"\n  ▶ Step 4: Market Data (OHLCV)")
    symbol = symbols[0] if symbols else "EUR_USD"
    data = exchange.get_market_data(symbol, "1h", limit=5)
    print(f"    Symbol: {symbol}  |  Timeframe: 1h  |  Candles: {len(data)}")
    for candle in data:
        print(
            f"      {candle['timestamp']}  "
            f"O:{candle['open']:<10.5f}  "
            f"H:{candle['high']:<10.5f}  "
            f"L:{candle['low']:<10.5f}  "
            f"C:{candle['close']:<10.5f}  "
            f"V:{candle['volume']:<8}"
        )

    # 5. Place a market order
    print(f"\n  ▶ Step 5: Place Market Order")
    order = exchange.place_order(
        symbol=symbol,
        side="buy",
        amount=1000,
        order_type="market",
    )
    print(f"    Order ID:   {order['id']}")
    print(f"    Status:     {order['status']}")
    print(f"    Filled:     {order['filled']}")
    print(f"    Remaining:  {order['remaining']}")

    # 6. Place a limit order
    print(f"\n  ▶ Step 6: Place Limit Order")
    limit_order = exchange.place_order(
        symbol=symbol,
        side="sell",
        amount=1000,
        price=100.0,
        order_type="limit",
    )
    print(f"    Order ID:   {limit_order['id']}")
    print(f"    Status:     {limit_order['status']}")

    # 7. Cancel the limit order
    print(f"\n  ▶ Step 7: Cancel Order")
    cancel_result = exchange.cancel_order(limit_order["id"])
    print(f"    Cancelled:  {cancel_result}")

    # 8. Broker-specific features
    print(f"\n  ▶ Step 8: Broker-Specific Features")
    if hasattr(exchange, "get_positions"):
        positions = exchange.get_positions()
        print(f"    Positions:  {len(positions)}")
        for pos in positions:
            print(
                f"      {pos.get('symbol', pos.get('instrument', 'N/A'))}:  "
                f"{pos.get('quantity', pos.get('units', 'N/A'))}  "
                f"P&L: {pos.get('unrealized_pnl', 'N/A')}"
            )

    if hasattr(exchange, "get_open_trades"):
        trades = exchange.get_open_trades()
        print(f"    Open Trades: {len(trades)}")
        for trade in trades:
            print(
                f"      {trade['instrument']}:  "
                f"{trade['units']} units @ "
                f"{trade['price']}  "
                f"P&L: {trade['unrealized_pnl']}"
            )

    if hasattr(exchange, "get_instrument_details"):
        details = exchange.get_instrument_details(symbol)
        if details:
            print(f"    Instrument details for {symbol}:")
            print(
                f"      Type: {details['type']}, "
                f"Pip: 10^{details.get('pip_location', '?')}, "
                f"Margin: {details.get('margin_rate', '?')}"
            )

    print(f"\n  ✅ {name} demo complete!")


def main():
    """
    Run the broker adapter example.
    
    Demonstrates both IB and OANDA adapters through their common
    Exchange interface.
    """
    print_separator("Broker Adapter Demo")
    print(
        "  This example demonstrates how to use multiple broker adapters\n"
        "  through the unified Exchange interface.\n"
    )
    print(
        "  Running in STUB mode — all data is simulated.\n"
        "  To use live data:\n"
        "    - Install ib_insync and start TWS/IB Gateway for IB\n"
        "    - Install oandapyV20 and configure API key for OANDA\n"
    )

    # ---- IB Adapter ----
    from trading.ib_adapter import IBAdapter

    ib = IBAdapter(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        account="DU1234567",
    )
    demonstrate_adapter("Interactive Brokers (IB)", ib)
    ib.disconnect()

    # ---- OANDA Adapter ----
    from trading.oanda_adapter import OANDAdapter

    oanda = OANDAdapter(
        api_key="your-api-token-here",
        environment="practice",
        account_id="101-001-1234567-001",
    )
    demonstrate_adapter("OANDA (Forex)", oanda)
    oanda.disconnect()

    # ---- Comparison ----
    print_separator("Adapter Comparison Summary")
    print(
        "  Both adapters implement the same Exchange interface:\n"
        "\n"
        "  Feature              | IBAdapter          | OANDAdapter\n"
        "  ---------------------|--------------------|---------------------\n"
        "  Broker Type          | Stocks/Options/    | Forex/Metals/CFDs\n"
        "                      | Futures/Forex      |\n"
        "  API Library          | ib_insync          | oandapyV20\n"
        "  Connection           | TWS/Gateway socket | REST API (HTTPS)\n"
        "  Authentication       | Session-based      | Bearer token\n"
        "  Paper Trading        | TWS paper account  | practice env\n"
        "  Order Types          | MKT, LMT, STP, ... | MARKET, LIMIT\n"
        "  Symbol Format        | AAPL, EUR.USD      | EUR_USD, XAU_USD\n"
    )

    print("  ✅ All broker adapter demos completed successfully!")
    print()


if __name__ == "__main__":
    main()