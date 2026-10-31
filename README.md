# Costco: linked 3-statement model + DCF from SEC EDGAR XBRL

[![ci](https://github.com/amirator/costco-3-statement-dcf-sec/actions/workflows/ci.yml/badge.svg)](https://github.com/amirator/costco-3-statement-dcf-sec/actions/workflows/ci.yml)

**Author:** Amir Khan. This is a portfolio project in financial modelling. It is not investment advice.

## Problem
FP&A and corporate-finance roles expect you to build a three-statement model that balances and a DCF on top of it, using source filings rather than numbers copied from a finance website. This repo does that end to end in code. It pulls Costco Wholesale Corp's audited 10-K figures straight from SEC EDGAR, projects linked income statement, balance sheet and cash-flow statements, and values the company with a free-cash-flow-to-firm (FCFF) DCF.

## Data
- **SEC EDGAR XBRL Company Facts API**, CIK 0000909832: `https://data.sec.gov/api/xbrl/companyfacts/CIK0000909832.json`. Only 10-K facts are used, and where a figure was restated, the latest filing wins.
- Historical years: FY2021 to FY2026 (Costco's fiscal year ends around 1 September).
- `data/facts_fy.csv` is the tidy extract (22 line items × 6 years, each with the us-gaap tag it came from). The raw JSON is git-ignored, and `ingest/fetch_sec.py` re-downloads it with the SEC-required contact User-Agent.

## Method
1. `src/extract.py` maps us-gaap tags to line items and keeps full-year (350–380 day) flows and year-end instants.
2. `src/model.py` derives drivers from the last 3 years: EBIT margin, D&A, capex and working capital as % of revenue, tax rate, payout ratios. It then projects FY2027E to FY2031E. Cash comes from the cash-flow statement and equity rolls forward with net income less dividends and buybacks, so the balance sheet balances by construction. The test suite enforces this.
3. FCFF = EBIT·(1−t) + D&A − capex − ΔNWC. This is discounted at a CAPM-based WACC, with a Gordon-growth terminal value and a WACC × g sensitivity grid.
4. `src/excel.py` writes `reports/costco_3statement_dcf.xlsx`. The DCF sheet uses **live Excel formulas** (discount factors, terminal value, EV to equity bridge), so a reviewer can change WACC or g in the workbook.

## Findings (from the filings)
- Revenue grew from $195.9bn (FY2021) to **$303.2bn (FY2026)**, a 3-year CAGR of 7.8%. Net income in FY2026 was $9.23bn.
- Margins are thin: EBIT margin was 3.85% in FY2026 (3-year average 3.76%). Accounts payable (7.4% of revenue) is larger than inventory plus receivables (7.9%), so **net working capital is negative**: suppliers finance the inventory.
- The dividend line has spikes in FY2021, FY2024, which are special dividends. Projected dividends use the FY2026 regular payout ratio (26.6%) instead of an average that the specials would inflate.
- Historical balance check (assets − liabilities − equity): max |gap| $0.0m. Projected max |gap|: 2.29e-05 (floating-point zero).

## Valuation output (driven by stated assumptions)
| Item | Value |
|---|---|
| WACC (rf 4.3%, β 0.8, ERP 5.0%, D/V 2%) | 8.19% |
| Terminal growth | 3.0% |
| Projected FCFF FY2027E–FY2031E ($bn) | 4.6, 5.9, 6.2, 6.6, 6.9 |
| Enterprise value | $115.3bn (terminal value = 79% of EV) |
| Equity value | $131.6bn |
| **Implied value per share** | **$296** (sensitivity range $229–$447) |

**How to read this:** a plain FCFF DCF with a 5-year fade to 4% growth and a 3% terminal rate gives a per-share value far below the price Costco has traded at in recent years. The model doesn't say the stock is overvalued. It shows that the market is pricing in much longer high growth and membership-fee durability than a mechanical 5-year DCF captures. That gap is the discussion point. The WACC inputs are illustrative assumptions, not live market data, and no market price is pulled into the model.

## Skills demonstrated
Three-statement linkage (IS → CF → BS), DCF/FCFF, WACC/CAPM, sensitivity analysis, XBRL/SEC EDGAR API extraction, pandas, openpyxl Excel output with live formulas, pytest, GitHub Actions CI.

## How to run
```bash
pip install -r requirements.txt
python ingest/fetch_sec.py        # optional: refresh raw EDGAR JSON (needs SEC-allowed network)
python src/extract.py             # -> data/facts_fy.csv
python src/model.py && python src/excel.py && python src/readme.py
python -m pytest -q
```

## Caveats
- The forward drivers are simple historical averages chosen by the author. This is not a consensus forecast.
- Debt is held flat, other assets and liabilities are held flat, and leases are not modelled separately.
- The DCF sheet's formulas were not recalculated in Excel during CI. openpyxl writes them and the tests check their structure. The Python DCF is the tested source of truth.

MIT licence.
