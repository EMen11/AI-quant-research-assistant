# Quantitative methodology — Block 2

## Scope and interpretation

The Quant Core is deterministic Python code. It neither forecasts prices nor emits buy/sell
signals or recommendations. The demo uses a synthetic, versioned adjusted-close CSV and makes no
market-data or LLM network call. Historical estimates describe only the frozen observation window.

An analysis contains exactly one immutable `MarketSnapshot`. Its canonical SHA-256 covers the
instruments, adjusted prices (including explicit nulls), date range, daily frequency, currencies,
provider, retrieval timestamp, adjustment policy, artifact URI and schema version. The snapshot is
loaded once through `SnapshotRun`; any later request returns the same object and a different
portfolio request is rejected.
The lineage hash is intentionally sensitive to the exact source decimal representation, so values
such as `Decimal("100.0")` and `Decimal("100.00")` produce different hashes.

## Data conventions

- **Price:** synthetic adjusted close, strictly positive when present.
- **Frequency:** daily observations.
- **Currency:** one base currency; Block 2 performs no FX conversion.
- **Reference date:** `PortfolioDefinition.analysis_cutoff`; later observations are excluded.
- **Missing values:** prices are never forward-filled or interpolated. Prices are first aligned on
  the union of dates. Simple returns are computed with `fill_method=None`, then every return row
  containing at least one missing value is removed. Removed dates remain recorded in
  `ReturnMatrix.dropped_dates`.
- **Minimum history:** at least two complete aligned return rows are required for the default
  analysis, sample volatility and covariance.
- **Annualization:** 252 trading days per year, fixed in `TRADING_DAYS_PER_YEAR`.
- **Precision:** fixture prices use `Decimal`; numerical calculations use IEEE-754 `float64`.

The complete-case policy deliberately trades sample size for one common date matrix. It prevents
different metrics or assets from silently using different windows. It can introduce selection bias
when missingness is systematic, so the number of missing prices and dropped return dates is shown.

## Return matrix

The single return convention is the arithmetic/simple return:

\[
r_{t,i} = \frac{P_{t,i}}{P_{t-1,i}} - 1
\]

It is a unitless decimal per trading day. A value of `-0.02` means a 2% loss. All downstream
calculations receive the same immutable `ReturnMatrix`; none recalculates or downloads prices.

## Metrics

| Metric | Formula and convention | Unit / frequency / horizon | Assumptions and missing values |
|---|---|---|---|
| Cumulative return | \(\prod_t(1+r_t)-1\). Positive is a gain; negative is a loss. | Decimal return over all complete daily rows. | Simple returns; no cash flows or fees. Complete-case rows only. |
| Historical annualized return | \((1+R_{cum})^{252/n}-1\). This is a geometric annualization of observed performance, not an expected return or forecast. | Decimal return per year; daily input; full observed horizon. | Stationarity is not claimed. Complete-case rows only. |
| Annualized volatility | \(s(r)\sqrt{252}\), where \(s\) is sample standard deviation with `ddof=1`. | Decimal volatility per year; daily input. | IID scaling is an approximation; at least two returns. |
| Drawdown | Wealth \(W_t=\prod_{j\le t}(1+r_j)\); \(D_t=W_t/\max_{j\le t}(W_j)-1\). | Decimal, non-positive; each complete daily row. | Initial wealth is 1. No interpolation. |
| Maximum drawdown | \(-\min_t D_t\). | Positive decimal loss magnitude over the full snapshot period. | Path-dependent historical statistic, not a probability. |
| Historical VaR | \(\max(0,-Q_{1-c}(r))\), using NumPy's linear sample quantile. | Positive decimal loss; one trading day; confidence `c`. | Empirical distribution represents the sample; complete-case daily portfolio returns. |
| Parametric VaR | \(\max(0,-(\bar r+z_{1-c}s))\), with sample `s` and Gaussian quantile `z`. | Positive decimal loss; one trading day; confidence `c`. | Daily returns are approximated by a normal distribution; at least two returns. |
| Expected Shortfall | \(\max(0,-E[r\mid r\le Q_{1-c}(r)])\). Observations equal to the threshold are included. | Positive decimal loss; one trading day; confidence `c`. | Historical tail estimator; small samples can leave very few tail observations. |
| Covariance | Sample covariance (`ddof=1`) multiplied by 252. | Decimal² per year; daily input. | Common complete-case matrix and square-root-of-time framework. |
| Correlation | Pearson sample correlation of daily simple returns. | Unitless coefficient in `[-1,1]`; daily input. | Undefined for zero-variance assets; such assets are identified by optimizer diagnostics. |
| Portfolio return | \(r_{p,t}=w^Tr_t\), with fixed long-only weights summing to one; all portfolio metrics then use the formulas above. | Same units and horizons as their component metric. | No rebalancing costs, taxes, slippage or FX conversion. |
| Historical Sharpe ratio | \((R_{ann,hist}-r_f)/\sigma_{ann}\). | Unitless annualized ratio. | Historical annualized return is not a forecast. Omitted when volatility is zero. |

VaR and Expected Shortfall use a **positive loss convention**: a reported `0.03` means a 3% loss
threshold or tail loss. Expected Shortfall should be at least historical VaR for the same empirical
tail under this convention, subject to floating-point tolerance.

## Risk-free-rate assumption

`RiskFreeRate` requires an annual decimal value, currency, date and descriptive source. The demo
uses `1.00% CHF`, dated `2026-09-18`, labelled **Synthetic Block 2 demo assumption; fixed fixture,
not a real-time quote**. It is used in the historical Sharpe ratio and Markowitz objective. It must
not be described as a current market rate.

## Markowitz scenario

The optimizer maximizes the in-sample historical Sharpe ratio:

\[
\max_w \frac{w^T(252\bar r)-r_f}{\sqrt{w^T(252\Sigma)w}}
\]

subject to:

\[
\sum_i w_i=1,\qquad w_{min}\le w_i\le w_{max},\qquad 0\le w_i\le1.
\]

Expected returns in this objective are arithmetic historical daily means multiplied by 252. They
are inputs to a mathematical scenario, not predictions. SLSQP receives an equal-weight initial
point. Assets with non-finite or effectively zero sample variance are excluded and reported.

`OptimizationDiagnostics` always records solver success/status/message, convergence, constraint
and bound checks, weight sum, excluded assets, iteration count and failure cause. Weights are
returned only when the solver succeeds and every post-solve check passes. There is no silent
equal-weight fallback. Infeasible bounds are rejected before calling the solver.

## Reproducibility and limitations

- The canonical snapshot hash detects changed content or lineage metadata.
- Two analyses of the same snapshot, portfolio and risk-free assumption must compare equal.
- A frozen snapshot is reproducible but is not proof that the source was point-in-time or free of
  survivorship/look-ahead bias.
- The short synthetic history is suitable for executable examples, not investment inference.
- Gaussian VaR can understate skewed or heavy-tailed risk; historical VaR/ES are sample-sensitive.
- Markowitz is highly sensitive to estimated means and covariance and is shown only as a
  constrained mathematical scenario.
- No predictive backtest is performed in Block 2.
