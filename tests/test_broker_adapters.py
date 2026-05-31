"""
Unit tests for broker adapters (IB and OANDA) and the BrokerFactory.

All adapters run in stub mode during tests — no live connections are made.
Tests verify interface compliance, data shape, and error handling.
"""

import sys
import os
import pytest
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading.exchange import Exchange
from trading.ib_adapter import IBAdapter
from trading.oanda_adapter import OANDAdapter
from trading.broker_factory import create_exchange, list_supported_brokers


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def ib_adapter() -> IBAdapter:
    """Return an IBAdapter instance in stub mode."""
    return IBAdapter(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        account="DU1234567",
    )


@pytest.fixture
def oanda_adapter() -> OANDAdapter:
    """Return an OANDAdapter instance in stub mode."""
    return OANDAdapter(
        api_key="test-token",
        environment="practice",
        account_id="101-001-1234567-001",
    )


# ======================================================================
# Interface compliance tests (both adapters)
# ======================================================================

class TestInterfaceCompliance:
    """Verify both adapters implement the Exchange interface correctly."""

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_is_exchange(self, adapter_fixture, request):
        """Both adapters must be instances of Exchange."""
        adapter = request.getfixturevalue(adapter_fixture)
        assert isinstance(adapter, Exchange), (
            f"{type(adapter).__name__} does not implement Exchange"
        )

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_check_connection(self, adapter_fixture, request):
        """Connection check must return True after establishing connection in stub mode."""
        adapter = request.getfixturevalue(adapter_fixture)
        # Initially disconnected
        assert adapter.check_connection() is False
        # Establish stub connection
        assert adapter._ensure_connected() is True
        assert adapter.check_connection() is True

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_get_balance_returns_dict(self, adapter_fixture, request):
        """Balance must be a dict with currency keys and float values."""
        adapter = request.getfixturevalue(adapter_fixture)
        balance = adapter.get_balance()
        assert isinstance(balance, dict)
        assert len(balance) > 0
        for currency, amount in balance.items():
            assert isinstance(currency, str)
            assert isinstance(amount, (int, float))

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_get_supported_symbols(self, adapter_fixture, request):
        """Supported symbols must be a non-empty list of strings."""
        adapter = request.getfixturevalue(adapter_fixture)
        symbols = adapter.get_supported_symbols()
        assert isinstance(symbols, list)
        assert len(symbols) > 0
        for sym in symbols:
            assert isinstance(sym, str)

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_get_market_data_shape(self, adapter_fixture, request):
        """Market data must return a list of OHLCV dicts."""
        adapter = request.getfixturevalue(adapter_fixture)
        symbols = adapter.get_supported_symbols()
        symbol = symbols[0]
        data = adapter.get_market_data(symbol, "1h", limit=5)

        assert isinstance(data, list)
        assert len(data) == 5

        required_keys = {"timestamp", "open", "high", "low", "close", "volume"}
        for candle in data:
            assert isinstance(candle, dict)
            assert required_keys.issubset(candle.keys()), (
                f"Missing keys: {required_keys - set(candle.keys())}"
            )
            assert isinstance(candle["timestamp"], int)
            assert isinstance(candle["volume"], int)
            for k in ("open", "high", "low", "close"):
                assert isinstance(candle[k], (int, float))

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_place_market_order(self, adapter_fixture, request):
        """Market orders must return a dict with expected fields."""
        adapter = request.getfixturevalue(adapter_fixture)
        symbols = adapter.get_supported_symbols()
        symbol = symbols[0]

        order = adapter.place_order(
            symbol=symbol, side="buy", amount=1000, order_type="market"
        )

        assert isinstance(order, dict)
        assert "id" in order
        assert "symbol" in order
        assert "side" in order
        assert order["side"] == "buy"
        assert "status" in order
        assert "filled" in order
        assert "remaining" in order

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_place_limit_order(self, adapter_fixture, request):
        """Limit orders must require a price parameter."""
        adapter = request.getfixturevalue(adapter_fixture)
        symbols = adapter.get_supported_symbols()
        symbol = symbols[0]

        order = adapter.place_order(
            symbol=symbol, side="sell", amount=500,
            price=100.0, order_type="limit",
        )

        assert isinstance(order, dict)
        assert order["side"] == "sell"
        assert order["type"] == "limit"
        assert "price" in order

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_place_limit_order_missing_price_raises(self, adapter_fixture, request):
        """Limit orders without price must raise ValueError."""
        adapter = request.getfixturevalue(adapter_fixture)
        symbols = adapter.get_supported_symbols()
        symbol = symbols[0]

        with pytest.raises(ValueError, match="Price is required"):
            adapter.place_order(
                symbol=symbol, side="buy", amount=100,
                price=None, order_type="limit",
            )

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_cancel_order(self, adapter_fixture, request):
        """Cancel order must return True in stub mode."""
        adapter = request.getfixturevalue(adapter_fixture)
        result = adapter.cancel_order("test-order-123")
        assert result is True

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_disconnect(self, adapter_fixture, request):
        """Disconnect must not raise."""
        adapter = request.getfixturevalue(adapter_fixture)
        adapter.disconnect()
        assert adapter._connected is False

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_invalid_side_raises(self, adapter_fixture, request):
        """Invalid order side must raise ValueError."""
        adapter = request.getfixturevalue(adapter_fixture)
        with pytest.raises(ValueError, match="Invalid side"):
            adapter.place_order(symbol="AAPL", side="invalid", amount=1)

    @pytest.mark.parametrize("adapter_fixture", ["ib_adapter", "oanda_adapter"])
    def test_invalid_order_type_raises(self, adapter_fixture, request):
        """Invalid order type must raise ValueError."""
        adapter = request.getfixturevalue(adapter_fixture)
        with pytest.raises(ValueError, match="Invalid order type"):
            adapter.place_order(
                symbol="AAPL", side="buy", amount=1,
                order_type="invalid",
            )


# ======================================================================
# IBAdapter-specific tests
# ======================================================================

class TestIBAdapterSpecific:
    """Tests for IBAdapter-specific features."""

    def test_ib_get_positions(self, ib_adapter: IBAdapter):
        """IBAdapter must expose get_positions()."""
        positions = ib_adapter.get_positions()
        assert isinstance(positions, list)
        if positions:
            pos = positions[0]
            assert "symbol" in pos
            assert "quantity" in pos
            assert "unrealized_pnl" in pos

    def test_ib_get_next_order_id(self, ib_adapter: IBAdapter):
        """get_next_order_id must return an integer."""
        order_id = ib_adapter.get_next_order_id()
        assert isinstance(order_id, int)
        assert order_id > 0

    def test_ib_map_timeframe(self):
        """Mapping must produce valid IB bar size strings."""
        mappings = {
            "1m": "1 min",
            "5m": "5 mins",
            "15m": "15 mins",
            "30m": "30 mins",
            "1h": "1 hour",
            "4h": "4 hours",
            "1d": "1 day",
            "1w": "1 week",
        }
        for standard, ib_format in mappings.items():
            assert IBAdapter._map_timeframe(standard) == ib_format

    def test_ib_repr(self, ib_adapter: IBAdapter):
        """__repr__ must contain identifying info."""
        rep = repr(ib_adapter)
        assert "IBAdapter" in rep
        assert "127.0.0.1" in rep


# ======================================================================
# OANDAdapter-specific tests
# ======================================================================

class TestOANDAdapterSpecific:
    """Tests for OANDAdapter-specific features."""

    def test_oanda_get_open_trades(self, oanda_adapter: OANDAdapter):
        """OANDAdapter must expose get_open_trades()."""
        trades = oanda_adapter.get_open_trades()
        assert isinstance(trades, list)
        if trades:
            trade = trades[0]
            assert "instrument" in trade
            assert "units" in trade
            assert "unrealized_pnl" in trade

    def test_oanda_get_instrument_details(self, oanda_adapter: OANDAdapter):
        """get_instrument_details must return a dict with expected keys."""
        details = oanda_adapter.get_instrument_details("EUR_USD")
        assert isinstance(details, dict)
        assert "name" in details
        assert "pip_location" in details
        assert "margin_rate" in details

    def test_oanda_map_timeframe(self):
        """Mapping must produce valid OANDA granularity strings."""
        mappings = {
            "1m": "M1",
            "5m": "M5",
            "15m": "M15",
            "30m": "M30",
            "1h": "H1",
            "4h": "H4",
            "1d": "D",
            "1w": "W",
        }
        for standard, oanda_format in mappings.items():
            assert OANDAdapter._map_timeframe(standard) == oanda_format

    def test_oanda_repr(self, oanda_adapter: OANDAdapter):
        """__repr__ must contain identifying info."""
        rep = repr(oanda_adapter)
        assert "OANDAdapter" in rep
        assert "practice" in rep


# ======================================================================
# BrokerFactory tests
# ======================================================================

class TestBrokerFactory:
    """Tests for the BrokerFactory."""

    def test_list_supported_brokers(self):
        """Must return the expected list."""
        brokers = list_supported_brokers()
        assert isinstance(brokers, list)
        assert "ccxt" in brokers
        assert "ib" in brokers
        assert "oanda" in brokers

    def test_create_ccxt(self):
        """CCXT exchange creation must succeed with correct config."""
        exchange = create_exchange({
            "name": "ccxt",
            "exchange_id": "binance",
            "sandbox": True,
        })
        assert isinstance(exchange, Exchange)

    def test_create_ib(self):
        """IB adapter creation must succeed with correct config."""
        exchange = create_exchange({
            "name": "ib",
            "host": "127.0.0.1",
            "port": 7497,
            "client_id": 1,
        })
        assert isinstance(exchange, IBAdapter)

    def test_create_oanda(self):
        """OANDA adapter creation must succeed with correct config."""
        exchange = create_exchange({
            "name": "oanda",
            "api_key": "test-token",
            "environment": "practice",
        })
        assert isinstance(exchange, OANDAdapter)

    def test_create_unknown_broker_raises(self):
        """Unknown broker name must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown broker 'fake'"):
            create_exchange({"name": "fake"})

    def test_create_missing_name_raises(self):
        """Missing broker name must raise ValueError."""
        with pytest.raises(ValueError, match="Broker name is required"):
            create_exchange({})

    def test_create_ccxt_missing_exchange_id_raises(self):
        """CCXT config missing exchange_id must raise ValueError."""
        with pytest.raises(ValueError, match="exchange_id"):
            create_exchange({"name": "ccxt"})