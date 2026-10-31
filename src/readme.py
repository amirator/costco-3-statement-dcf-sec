"""Render README.md from reports/kpis.json so numbers never drift from the model output."""
import json, pathlib


def render(k: dict) -> str:
    a, dv = k["assumptions"], k["drivers"]
    hy, py = k["hist_years"], k["proj_years"]
    return f"""# Costco: linked 3-statement model + DCF from SEC EDGAR XBRL

[![ci](https://github.com/amirator/costco-3-statement-dcf-sec/actions/workflows/ci.yml/badge.svg)](https://github.com/amirator/costco-3-statement-dcf-sec/actions/workflows/ci.yml)

**Author:** Amir Khan. This is a portfolio project in financial modelling. It is not investment advice.

## Problem
FP&A and corporate-finance roles expect you to build a three-statement model that balances and a DCF on top of it, using source filings rather than numbers copied from a finance website. This repo does that end to end in code. It pulls {k['company']}'s audited 10-K figures straight from SEC EDGAR, projects linked income statement, balance sheet and cash-flow statements, and values the company with a free-cash-flow-to-firm (FCFF) DCF.

## Data
- **SEC EDGAR XBRL Company Facts API**, CIK {k['cik']}: `https://data.sec.gov/api/xbrl/companyfacts/CIK{k['cik']}.json`. Only 10-K facts are used, and where a figure was restated, the latest filing wins.
- Historical years: {hy[0]} to {hy[-1]} (Costco's fiscal year ends around 1 September).
- `data/facts_fy.csv` is the tidy extract (22 line items × 6 years, each with the us-gaap tag it came from). The raw JSON is git-ignored, and `ingest/fetch_sec.py` re-downloads it with the SEC-required contact User-Agent.

## Method
1. `src/extract.py` maps us-gaap tags to line items and keeps full-year (350–380 day) flows and year-end instants.
2. `src/model.py` derives drivers from the last 3 years: EBIT margin, D&A, capex and working capital as % of revenue, tax rate, payout ratios. It then projects {py[0]} to {py[-1]}. Cash comes from the cash-flow statement and equity rolls forward with net income less dividends and buybacks, so the balance sheet balances by construction. The test suite enforces this.
3. FCFF = EBIT·(1−t) + D&A − capex − ΔNWC. This is discounted at a CAPM-based WACC, with a Gordon-growth terminal value and a WACC × g sensitivity grid.
4. `src/excel.py` writes `reports/costco_3statement_dcf.xlsx`. The DCF sheet uses **live Excel formulas** (discount factors, terminal value, EV to equity bridge), so a reviewer can change WACC or g in the workbook.

## Findings (from the filings)
- Revenue grew from ${k['revenue_first_bn']:.1f}bn ({hy[0]}) to **${k['revenue_latest_bn']:.1f}bn ({hy[-1]})**, a 3-year CAGR of {dv['cagr_3y']:.1%}. Net income in {hy[-1]} was ${k['net_income_latest_bn']:.2f}bn.
- Margins are thin: EBIT margin was {k['ebit_margin_latest']:.2%} in {hy[-1]} (3-year average {dv['ebit_margin']:.2%}). Accounts payable ({dv['ap_pct_rev']:.1%} of revenue) is larger than inventory plus receivables ({dv['inv_pct_rev'] + dv['recv_pct_rev']:.1%}), so **net working capital is negative**: suppliers finance the inventory.
- The dividend line has spikes in {', '.join(k['special_dividend_years'])}, which are special dividends. Projected dividends use the {hy[-1]} regular payout ratio ({dv['dividend_payout']:.1%}) instead of an average that the specials would inflate.
- Historical balance check (assets − liabilities − equity): max |gap| ${k['hist_balance_max_abs_m']:.1f}m. Projected max |gap|: {k['proj_balance_max_abs']:.2e} (floating-point zero).

## Valuation output (driven by stated assumptions)
| Item | Value |
|---|---|
| WACC (rf {a['risk_free']:.1%}, β {a['beta']}, ERP {a['equity_risk_premium']:.1%}, D/V {a['debt_weight']:.0%}) | {k['wacc']:.2%} |
| Terminal growth | {a['terminal_growth']:.1%} |
| Projected FCFF {py[0]}–{py[-1]} ($bn) | {', '.join(f'{x:.1f}' for x in k['fcff_proj_bn'])} |
| Enterprise value | ${k['enterprise_value']/1e9:.1f}bn (terminal value = {k['tv_share_of_ev']:.0%} of EV) |
| Equity value | ${k['equity_value']/1e9:.1f}bn |
| **Implied value per share** | **${k['per_share']:.0f}** (sensitivity range ${k['sens_min']:.0f}–${k['sens_max']:.0f}) |

**How to read this:** a plain FCFF DCF with a 5-year fade to {a['growth_fade_to']:.0%} growth and a {a['terminal_growth']:.0%} terminal rate gives a per-share value far below the price Costco has traded at in recent years. The model doesn't say the stock is overvalued. It shows that the market is pricing in much longer high growth and membership-fee durability than a mechanical 5-year DCF captures. That gap is the discussion point. The WACC inputs are illustrative assumptions, not live market data, and no market price is pulled into the model.

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
"""


if __name__ == "__main__":
    k = json.loads(pathlib.Path("reports/kpis.json").read_text())
    pathlib.Path("README.md").write_text(render(k))
