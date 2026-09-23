# Sustainable finance corpus methodology

## Scope and trust boundary

Block 4 provides a small, versioned climate corpus for offline demonstrations and
deterministic tests. It covers two 2025 issuer reports: Bachem Holding AG and Siegfried
Holding AG. The committed records state what those issuers published; they do not establish
the physical truth, completeness or cross-company comparability of the reported data.

Only the issuer pages and exact PDFs below are source authorities. Search engines,
aggregators and secondary sources are outside this corpus. The LLM does not extract,
correct, verify or approve any observation. Python validates closed schemas, hashes,
references, publication cutoffs and supported unit conversions. Human page-by-page
verification of all 12 `SustainabilityObservation` records has been completed against the
official report pages. The two separate `ClimateTarget` records remain on the checklist.

## Official source manifest

| Issuer | Official report page | Requested and final PDF URL | Publication date used | Exact SHA-256 | PDF pages |
|---|---|---|---|---|---:|
| Bachem | [Reports and presentations](https://www.bachem.com/about-bachem/investor-hub/reports-and-presentations/) | [Bachem Annual Report 2025](https://www.bachem.com/wp-content/uploads/2026/03/Bachem-Annual-report-2025-EN.pdf) | [2026-03-12, exact](https://www.bachem.com/wp-content/uploads/2026/03/Media-Release-Financial-Year-2025_final.pdf) | `acd34aee09ad95bd29e0a527b841b7158c4886f2f1f33c1ce9618b9e39ca1751` | 106 |
| Siegfried | [Sustainability](https://www.siegfried.ch/sustainability/) | [Sustainability Report 2025](https://www.siegfried.ch/app/uploads/2026/02/Siegfried_2025_AR_Sustainability_Report_EN.pdf) | 2026-02-20, exact | `d6475053473b146882c8758e3133b4d5de4b4886158572215376f9adc81622bb` | 62 |

Both report files were accessed at `2026-09-22T23:50:36Z`; neither request redirected.
Siegfried states its publication date on PDF page 3. The official Bachem media release is
dated March 12, 2026 and states that the complete Annual Report 2025 can be viewed and
downloaded on the Bachem website. This is the publication-date evidence used for cutoff.
The annual report's separate March 2, 2026 Board approval date is retained in the manifest
evidence text but is not treated as its publication date. The former March 15 server
`Last-Modified` proxy is no longer used.

The full PDFs and extracted page text live under ignored `data/` paths. They must never be
staged because redistribution rights are not asserted. The committed manifest records the
local filename, requested URL, final URL, access timestamp, page count and exact byte hash.
A changed upstream file therefore fails verification instead of silently changing lineage.

## Repeatable local acquisition and verification

Run from the repository root. The first two downloads are the corpus documents; the third is
the official publication-date evidence:

```bash
mkdir -p data/source_documents
curl --fail --location --proto '=https' \
  --output data/source_documents/bachem-annual-report-2025-en.pdf \
  'https://www.bachem.com/wp-content/uploads/2026/03/Bachem-Annual-report-2025-EN.pdf'
curl --fail --location --proto '=https' \
  --output data/source_documents/siegfried-sustainability-report-2025-en.pdf \
  'https://www.siegfried.ch/app/uploads/2026/02/Siegfried_2025_AR_Sustainability_Report_EN.pdf'
curl --fail --location --proto '=https' \
  --output data/source_documents/bachem-media-release-financial-year-2025-final.pdf \
  'https://www.bachem.com/wp-content/uploads/2026/03/Media-Release-Financial-Year-2025_final.pdf'
uv run --frozen python -m ai_quant.sustainability.cli verify-pdfs
uv run --frozen python -m ai_quant.sustainability.cli extract
uv run --frozen python -m ai_quant.sustainability.cli \
  verify-artifacts --cutoff 2026-03-12
```

Extraction is local, deterministic and page-by-page with `pypdf`; `fonttools` is included
because the official PDFs contain CFF Type 1 fonts whose encodings require it for complete
text parsing. No OCR, embedding model, LLM or network request participates in extraction.
An empty text page is retained as `ocr_required_not_supported`, never guessed or discarded.

`pdf_page` is the one-based physical PDF index. `printed_page` is the page number printed by
the issuer and may differ or be absent. Both are stored explicitly. Extracted page artifacts
are local diagnostics under ignored `data/extracted_pages/`; the curated annotations are the
reviewable committed artifact.

## Versioned artifacts

All committed corpus files are under `src/ai_quant/fixtures/sustainability/`:

- `manifest.v1.json`: two exact source identities;
- `observations.v1.jsonl`: 12 actual observations, six per issuer;
- `targets.v1.json`: two issuer-reported targets, separate from actual observations;
- `assurance.v1.json`: metric-specific assurance assessments;
- `comparisons.v1.json`: explicit pairwise comparability decisions;
- `coverage_report.v1.json`: bounded searches, exclusions and review state.

Every observation records issuer, document ID/title/year/hash, publication and reporting
periods, PDF and printed pages, a short exact excerpt, raw label, `Decimal` value, unit,
coverage status, actual/target kind, issuer/code origin, Scope 2 method, organizational
boundary, methodology, restatement and assurance status. Runtime loading rejects unknown
document IDs, changed hashes and inconsistent document metadata before applying the cutoff.

## Coverage semantics

The five closed statuses must not be collapsed:

- `reported_value`: the issuer printed a non-zero numeric value;
- `reported_zero`: the issuer explicitly printed zero;
- `not_found`: the bounded documented search did not identify the item;
- `explicitly_not_published`: the source explicitly says the item is not published;
- `ambiguous`: a label or cell exists but does not support a unique numeric interpretation.

`not_found` is not a zero and is not proof that the issuer publishes nothing elsewhere.
`reported_zero` requires an exact decimal zero and a unit. Actual observations and climate
targets use separate models. `issuer_reported` and `code_derived` values are also explicit;
the current curated observations are issuer-reported.

Scope 2 records require either `location_based` or `market_based`. The method is part of the
record and of every comparability assessment; the two methods are never merged.

## Units, cutoff and comparison rules

Numeric values use `Decimal`. Python permits only exact factor conversions within the same
dimension: `ktCO2e`↔`tCO2e` and `TJ`↔`GJ`; percent remains percent. Energy, emissions and
shares are mutually incompatible. No conversion can make unlike definitions comparable.
The source spellings `tCO2eq` and `ktCO2eq` are stored as the canonical equivalent labels
`tCO2e` and `ktCO2e`; this is a notation-only mapping, while the exact printed spelling is
retained in each short excerpt.

A document is eligible only when its recorded publication date is on or before the research
cutoff. The reporting year is never substituted for publication date. Records inherit and
must match their source document publication date and exact hash.

Pairwise comparison is a versioned assessment across all of these dimensions:

1. organizational boundary;
2. reporting period;
3. unit compatibility;
4. Scope 2 method;
5. absolute, intensity or share basis;
6. restatement status;
7. assurance coverage;
8. indicator definition or methodology.

The three same-indicator cross-issuer pairs in version 1 are only partially comparable.
Units and periods align or convert, but corporate boundaries, scale, restatement treatment,
assurance and some methodological details differ. Bachem renewable fuel and Siegfried
renewable electricity are explicitly not comparable even though their energy units convert.
The corpus supports traceable reading, not issuer ranking.

## Assurance and known limits

Assurance is metric-specific. Bachem's selected, check-marked sustainability indicators are
linked to a limited-assurance statement; the corpus does not extend that conclusion to an
unmarked metric. Siegfried explicitly states that the non-financial report was not subjected
to external audit. Financial-statement audit references do not assure these climate values.
An issuer claim of external target validation is preserved as an issuer claim unless an
independent registry source is added to a later corpus version.

## Human review checklist

The completed review supplied for Block 4 confirms all 12 `SustainabilityObservation`
records: Bachem 6/6 and Siegfried 6/6 for values, units, pages, Scope 2 methods and assurance
statuses. Confirmed pagination is Bachem PDF page 33 / printed page 31, Siegfried emissions
page 57 / 57, and Siegfried energy page 58 / 58.

The targets are separate records and are not included in that count. They remain to be
checked independently:

| Target ID | Issuer | Target | Base → target year | PDF / printed page | Short excerpt | Review status |
|---|---|---:|---|---|---|---|
| `target-bachem-scope-one-two-2030` | Bachem | 44% | 2023 → 2030 | 30 / 28 | “Reducing absolute Scope 1 and 2 GHG emissions” | To check |
| `target-siegfried-scope-one-two-2033` | Siegfried | 66.89% | 2020 → 2033 | 9 / 9 | “reduce absolute scope 1 and 2 GHG emissions” | To check |

Version 1 is intentionally narrow: two English-language PDFs, one reporting year, 12 actual
observations, two targets and three explicit coverage findings. It does not prove exhaustive
issuer disclosure, validate physical measurements, normalize group size, or authorize a
financial recommendation. The completed observation review does not imply that the two
separate targets have been checked or that any issuer statement is physically true.
