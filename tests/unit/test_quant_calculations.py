from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from ai_quant.quant import (
    MarketSnapshot,
    PriceObservation,
    QuantValidationError,
    ReturnMatrix,
    annualized_covariance,
    annualized_volatility,
    build_return_matrix,
    correlation,
    cumulative_returns,
    drawdown,
    expected_shortfall,
    historical_annualized_returns,
    historical_var,
    maximum_drawdown,
    parametric_var,
)


def make_snapshot(
    values: dict[str, tuple[Decimal | None, ...]],
    *,
    snapshot_id: str = "test-snapshot",
) -> MarketSnapshot:
    start = date(2026, 1, 5)
    observations = tuple(
        PriceObservation(start + timedelta(days=index), instrument, price)
        for instrument, prices in values.items()
        for index, price in enumerate(prices)
    )
    instruments = tuple(values)
    return MarketSnapshot.create(
        snapshot_id=snapshot_id,
        instruments=instruments,
        observations=observations,
        base_currency="CHF",
        currencies=tuple((instrument, "CHF") for instrument in instruments),
        provider="unit-test",
        analysis_cutoff=datetime(2026, 1, 10, tzinfo=UTC),
        retrieved_at=datetime(2026, 1, 10, tzinfo=UTC),
        adjustment_policy="Synthetic adjusted closes.",
        artifact_uri="memory://unit-test",
    )


def test_manual_simple_returns_cumulative_and_annualization() -> None:
    snapshot = make_snapshot({"A": (Decimal("100"), Decimal("110"), Decimal("121"))})

    returns = build_return_matrix(snapshot)

    assert np.asarray(returns.values) == pytest.approx(np.asarray(((0.1,), (0.1,))))
    assert cumulative_returns(returns) == pytest.approx((0.21,))
    assert historical_annualized_returns(returns, annualization_factor=2) == pytest.approx(
        (0.21,)
    )
    assert annualized_volatility(returns, annualization_factor=2) == pytest.approx((0.0,))


def test_constant_prices_have_zero_returns_volatility_and_drawdown() -> None:
    snapshot = make_snapshot(
        {"A": (Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100"))}
    )
    returns = build_return_matrix(snapshot)

    assert returns.values == ((0.0,), (0.0,), (0.0,))
    assert annualized_volatility(returns) == (0.0,)
    assert maximum_drawdown(tuple(row[0] for row in returns.values)) == 0.0


def test_increasing_series_has_no_drawdown() -> None:
    returns = (0.02, 0.03, 0.01)

    assert drawdown(returns) == pytest.approx((0.0, 0.0, 0.0))
    assert maximum_drawdown(returns) == 0.0


def test_manual_peak_to_trough_drawdown() -> None:
    returns = (0.10, -0.20, 95 / 88 - 1)

    assert drawdown(returns) == pytest.approx((0.0, -0.20, 95 / 110 - 1))
    assert maximum_drawdown(returns) == pytest.approx(0.20)


def test_extreme_loss_and_expected_shortfall_loss_convention() -> None:
    returns = (-0.50, -0.10, -0.02, 0.01, 0.03, 0.04)

    var = historical_var(returns, 0.95)
    shortfall = expected_shortfall(returns, 0.95)

    assert var > 0.0
    assert shortfall >= var
    assert shortfall == pytest.approx(0.50)


def test_var_supports_multiple_confidence_levels() -> None:
    returns = (-0.08, -0.04, -0.01, 0.0, 0.02, 0.03, 0.05, 0.06)

    historical_80 = historical_var(returns, 0.80)
    historical_95 = historical_var(returns, 0.95)
    gaussian_80 = parametric_var(returns, 0.80)
    gaussian_95 = parametric_var(returns, 0.95)

    assert historical_95 >= historical_80
    assert gaussian_95 >= gaussian_80


def test_missing_prices_are_not_filled_and_incomplete_calendars_are_dropped() -> None:
    snapshot = make_snapshot(
        {
            "A": (
                Decimal("100"),
                Decimal("101"),
                Decimal("102"),
                Decimal("103"),
                Decimal("104"),
            ),
            "B": (
                Decimal("50"),
                Decimal("51"),
                None,
                Decimal("52"),
                Decimal("53"),
            ),
        }
    )

    returns = build_return_matrix(snapshot)

    assert len(returns.values) == 2
    assert len(returns.dropped_dates) == 3
    assert returns.dates[-1] == date(2026, 1, 9)


def test_asset_without_prices_is_rejected() -> None:
    snapshot = MarketSnapshot.create(
        snapshot_id="missing-asset",
        instruments=("A", "B"),
        observations=(
            PriceObservation(date(2026, 1, 5), "A", Decimal("100")),
            PriceObservation(date(2026, 1, 6), "A", Decimal("101")),
            PriceObservation(date(2026, 1, 7), "A", Decimal("102")),
        ),
        base_currency="CHF",
        currencies=(("A", "CHF"), ("B", "CHF")),
        provider="unit-test",
        analysis_cutoff=datetime(2026, 1, 10, tzinfo=UTC),
        retrieved_at=datetime(2026, 1, 10, tzinfo=UTC),
        adjustment_policy="test",
        artifact_uri="memory://missing-asset",
    )

    with pytest.raises(QuantValidationError, match="without adjusted prices: B"):
        build_return_matrix(snapshot)


def test_insufficient_history_is_explicit() -> None:
    snapshot = make_snapshot({"A": (Decimal("100"), Decimal("101"))})

    with pytest.raises(QuantValidationError, match="Insufficient aligned history"):
        build_return_matrix(snapshot)


def test_covariance_and_correlation_match_independent_pandas_implementation() -> None:
    matrix = ReturnMatrix(
        dates=(date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)),
        instruments=("A", "B"),
        values=((0.01, 0.02), (-0.02, 0.01), (0.03, -0.01), (0.00, 0.02)),
        dropped_dates=(),
    )
    frame = pd.DataFrame(matrix.values, columns=matrix.instruments)

    covariance = annualized_covariance(matrix)
    correlations = correlation(matrix)

    assert np.asarray(covariance.values) == pytest.approx(frame.cov().to_numpy() * 252)
    assert np.asarray(correlations.values) == pytest.approx(frame.corr().to_numpy())


def test_snapshot_hash_is_canonical_and_model_is_frozen() -> None:
    first = make_snapshot({"A": (Decimal("100"), Decimal("101"), Decimal("102"))})
    second = make_snapshot({"A": (Decimal("100"), Decimal("101"), Decimal("102"))})

    assert first.content_sha256 == second.content_sha256
    assert first.compute_content_sha256() == first.content_sha256
    with pytest.raises(FrozenInstanceError):
        first.snapshot_id = "changed"  # type: ignore[misc]
