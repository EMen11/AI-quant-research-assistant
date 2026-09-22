from datetime import date
from decimal import Decimal

import pytest

from ai_quant.market_data import (
    FrozenMarketDataProvider,
    MarketDataError,
    MarketSeries,
    PricePoint,
)


def test_frozen_provider_returns_requested_series_in_order() -> None:
    provider = FrozenMarketDataProvider.demo()

    series = provider.get_series(("DEMO-BETA", "DEMO-ALPHA"))

    assert [item.symbol for item in series] == ["DEMO-BETA", "DEMO-ALPHA"]
    assert all(item.provider == "frozen-demo-fixture" for item in series)


def test_frozen_provider_reports_missing_symbol() -> None:
    provider = FrozenMarketDataProvider.demo()

    with pytest.raises(MarketDataError, match="MISSING"):
        provider.get_series(("DEMO-ALPHA", "MISSING"))


def test_empty_market_series_has_explicit_error() -> None:
    series = MarketSeries(symbol="EMPTY", currency="CHF", provider="test", points=())

    with pytest.raises(MarketDataError, match="empty"):
        _ = series.latest


def test_price_point_preserves_decimal_value() -> None:
    point = PricePoint(observed_on=date(2026, 9, 18), close=Decimal("101.25"))

    assert point.close == Decimal("101.25")
