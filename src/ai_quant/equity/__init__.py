"""Deterministic, provenance-preserving Equity Research domain."""

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.climate import (
    build_climate_metrics,
    climate_intensity,
    normalize_emissions,
)
from ai_quant.equity.formatting import format_metric
from ai_quant.equity.fundamentals import (
    capex_to_revenue,
    cash_conversion,
    compound_annual_growth,
    estimated_cash_distribution,
    free_cash_flow,
    leverage,
    margin,
    net_debt,
    payout_ratio,
    return_on_equity,
    year_over_year_growth,
)
from ai_quant.equity.models import (
    FORMULA_VERSION,
    Company,
    ConcordanceCheck,
    EquityValidationError,
    FiscalPeriod,
    Formula,
    FundamentalAnalysis,
    MetricValue,
    SourceReference,
    unavailable_metric,
)
from ai_quant.equity.repository import EquityRepository, load_equity_repository
from ai_quant.equity.valuation import (
    ValuationAnalysis,
    build_valuation_analysis,
    dividend_yield,
    enterprise_value,
    fcf_yield,
    market_capitalization,
    valuation_multiple,
)

__all__ = [
    "FORMULA_VERSION",
    "Company",
    "ConcordanceCheck",
    "EquityValidationError",
    "EquityRepository",
    "FiscalPeriod",
    "Formula",
    "FundamentalAnalysis",
    "MetricValue",
    "SourceReference",
    "ValuationAnalysis",
    "build_climate_metrics",
    "build_valuation_analysis",
    "capex_to_revenue",
    "cash_conversion",
    "climate_intensity",
    "compound_annual_growth",
    "dividend_yield",
    "enterprise_value",
    "estimated_cash_distribution",
    "fcf_yield",
    "format_metric",
    "free_cash_flow",
    "leverage",
    "load_equity_repository",
    "margin",
    "market_capitalization",
    "net_debt",
    "normalize_emissions",
    "payout_ratio",
    "return_on_equity",
    "unavailable_metric",
    "valuation_multiple",
    "year_over_year_growth",
    "build_fundamental_analysis",
]
