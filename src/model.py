"""Linked 3-statement projection + FCFF DCF built on SEC EDGAR facts (data/facts_fy.csv).

Every historical number comes from Costco's 10-K XBRL facts. Every forward number is driven by the
ASSUMPTIONS below, which are the author's illustrative choices, not forecasts or investment advice.
"""
import json, pathlib
import numpy as np
import pandas as pd

ASSUMPTIONS = {
    "years": 5,
    "terminal_growth": 0.030,
    "growth_fade_to": 0.040,        # revenue growth fades linearly from trailing 3y CAGR to this in year 5
    "risk_free": 0.043,             # assumption (approx. 10y US Treasury level), not pulled live
    "equity_risk_premium": 0.050,   # assumption
    "beta": 0.80,                   # assumption (low-beta consumer staple)
    "pre_tax_cost_of_debt": 0.040,  # assumption
    "debt_weight": 0.02,            # assumption: target D/V; Costco's debt is small vs. market cap
}


def load_hist(path="data/facts_fy.csv") -> pd.DataFrame:
    d = pd.read_csv(path).pivot(index="fy_end", columns="line", values="value").sort_index()
    d.index = [f"FY{e[:4]}" for e in d.index]  # Costco FY ends ~1 Sep, so the end year is the FY label
    d["other_assets"] = d.total_assets - d.cash - d.receivables - d.inventory - d.ppe
    d["other_liabilities"] = d.total_liabilities - d.accounts_payable - d.lt_debt
    d["nwc"] = d.receivables + d.inventory - d.accounts_payable
    d["tax_rate"] = d.tax / d.pretax_income
    d["other_income"] = d.pretax_income - d.ebit + d.interest_expense
    return d


def drivers(h: pd.DataFrame) -> dict:
    last3 = h.iloc[-3:]
    rev = h.revenue
    return {
        "cagr_3y": (rev.iloc[-1] / rev.iloc[-4]) ** (1 / 3) - 1,
        "ebit_margin": (last3.ebit / last3.revenue).mean(),
        "da_pct_rev": (last3.da / last3.revenue).mean(),
        "capex_pct_rev": (last3.capex / last3.revenue).mean(),
        "recv_pct_rev": (last3.receivables / last3.revenue).mean(),
        "inv_pct_rev": (last3.inventory / last3.revenue).mean(),
        "ap_pct_rev": (last3.accounts_payable / last3.revenue).mean(),
        "tax_rate": last3.tax_rate.mean(),
        "interest_rate": (h.interest_expense.iloc[-1] / h.lt_debt.iloc[-2]),
        # latest year has no special dividend, so its payout is the regular-dividend run rate
        "dividend_payout": h.dividends.iloc[-1] / h.net_income.iloc[-1],
        "buyback_pct_ni": (last3.buybacks / last3.net_income).mean(),
    }


def project(h: pd.DataFrame, a=ASSUMPTIONS) -> tuple[pd.DataFrame, dict]:
    dv = drivers(h)
    n = a["years"]
    g = np.linspace(dv["cagr_3y"], a["growth_fade_to"], n)
    last = h.iloc[-1]
    rows, prev = [], last
    y0 = int(h.index[-1][2:])
    for i in range(n):
        r = {}
        r["revenue"] = prev.revenue * (1 + g[i])
        r["ebit"] = r["revenue"] * dv["ebit_margin"]
        r["da"] = r["revenue"] * dv["da_pct_rev"]
        r["lt_debt"] = prev.lt_debt  # debt held flat
        r["interest_expense"] = prev.lt_debt * dv["interest_rate"]
        r["pretax_income"] = r["ebit"] - r["interest_expense"]  # no other income assumed going forward
        r["tax"] = r["pretax_income"] * dv["tax_rate"]
        r["net_income"] = r["pretax_income"] - r["tax"]
        r["receivables"] = r["revenue"] * dv["recv_pct_rev"]
        r["inventory"] = r["revenue"] * dv["inv_pct_rev"]
        r["accounts_payable"] = r["revenue"] * dv["ap_pct_rev"]
        r["capex"] = r["revenue"] * dv["capex_pct_rev"]
        r["ppe"] = prev.ppe + r["capex"] - r["da"]
        r["other_assets"] = prev.other_assets
        r["other_liabilities"] = prev.other_liabilities
        r["dividends"] = r["net_income"] * dv["dividend_payout"]
        r["buybacks"] = r["net_income"] * dv["buyback_pct_ni"]
        d_nwc = (r["receivables"] + r["inventory"] - r["accounts_payable"]) - prev.nwc
        r["cfo"] = r["net_income"] + r["da"] - d_nwc
        r["cfi"] = -r["capex"]
        r["cff"] = -(r["dividends"] + r["buybacks"])
        r["cash"] = prev.cash + r["cfo"] + r["cfi"] + r["cff"]
        r["total_equity"] = prev.total_equity + r["net_income"] - r["dividends"] - r["buybacks"]
        r["nwc"] = r["receivables"] + r["inventory"] - r["accounts_payable"]
        r["total_assets"] = r["cash"] + r["receivables"] + r["inventory"] + r["ppe"] + r["other_assets"]
        r["total_liabilities"] = r["accounts_payable"] + r["lt_debt"] + r["other_liabilities"]
        r["balance_check"] = r["total_assets"] - r["total_liabilities"] - r["total_equity"]
        r["revenue_growth"] = g[i]
        r["d_nwc"] = d_nwc
        r["diluted_shares"] = last.diluted_shares  # buybacks roughly offset dilution historically
        rows.append(r)
        prev = pd.Series(r)
    p = pd.DataFrame(rows, index=[f"FY{y0 + i + 1}E" for i in range(n)])
    return p, dv


def wacc(a=ASSUMPTIONS, tax_rate=0.25) -> float:
    ke = a["risk_free"] + a["beta"] * a["equity_risk_premium"]
    kd = a["pre_tax_cost_of_debt"] * (1 - tax_rate)
    return (1 - a["debt_weight"]) * ke + a["debt_weight"] * kd


def dcf(p: pd.DataFrame, h: pd.DataFrame, dv: dict, w: float, tg: float) -> dict:
    fcff = p.ebit * (1 - dv["tax_rate"]) + p.da - p.capex - p.d_nwc
    t = np.arange(1, len(p) + 1)
    disc = (1 + w) ** -t
    pv = float((fcff * disc).sum())
    tv = float(fcff.iloc[-1] * (1 + tg) / (w - tg))
    pv_tv = tv * disc[-1]
    ev = pv + pv_tv
    last = h.iloc[-1]
    eq = ev + last.cash - last.lt_debt
    return {"fcff": fcff.round(0).tolist(), "pv_fcff": pv, "terminal_value": tv, "pv_terminal": pv_tv,
            "enterprise_value": ev, "equity_value": eq, "per_share": eq / last.diluted_shares,
            "tv_share_of_ev": pv_tv / ev}


def sensitivity(p, h, dv, w0, tg0):
    ws = [round(w0 + d, 4) for d in (-0.01, -0.005, 0, 0.005, 0.01)]
    gs = [round(tg0 + d, 4) for d in (-0.01, -0.005, 0, 0.005, 0.01)]
    return pd.DataFrame([[dcf(p, h, dv, w, g)["per_share"] for g in gs] for w in ws],
                        index=[f"WACC {w:.1%}" for w in ws], columns=[f"g {g:.1%}" for g in gs])


def run(facts="data/facts_fy.csv", out="reports"):
    h = load_hist(facts)
    p, dv = project(h)
    w = wacc(tax_rate=dv["tax_rate"])
    v = dcf(p, h, dv, w, ASSUMPTIONS["terminal_growth"])
    s = sensitivity(p, h, dv, w, ASSUMPTIONS["terminal_growth"])
    hl = h.iloc[-1]
    k = {
        "company": "Costco Wholesale Corp", "cik": "0000909832",
        "hist_years": list(h.index), "proj_years": list(p.index),
        "fy_latest": h.index[-1],
        "revenue_latest_bn": hl.revenue / 1e9, "revenue_first_bn": h.revenue.iloc[0] / 1e9,
        "net_income_latest_bn": hl.net_income / 1e9,
        "ebit_margin_latest": hl.ebit / hl.revenue,
        "special_dividend_years": [y for y in h.index if h.dividends[y] > 2 * h.dividends.median()],
        "hist_balance_max_abs_m": float((h.total_assets - h.total_liabilities - h.total_equity).abs().max() / 1e6),
        "proj_balance_max_abs": float(p.balance_check.abs().max()),
        "drivers": dv, "assumptions": ASSUMPTIONS, "wacc": w,
        "revenue_proj_final_bn": p.revenue.iloc[-1] / 1e9,
        **{k_: v[k_] for k_ in ("pv_fcff", "terminal_value", "pv_terminal", "enterprise_value", "equity_value", "per_share", "tv_share_of_ev")},
        "fcff_proj_bn": [x / 1e9 for x in v["fcff"]],
        "sens_min": float(s.values.min()), "sens_max": float(s.values.max()),
    }
    o = pathlib.Path(out); o.mkdir(exist_ok=True)
    (o / "kpis.json").write_text(json.dumps(k, indent=2, default=float))
    s.round(2).to_csv(o / "sensitivity.csv")
    return h, p, dv, w, v, s, k


if __name__ == "__main__":
    *_, k = run()
    print(json.dumps({x: k[x] for x in ("wacc", "per_share", "enterprise_value", "tv_share_of_ev", "proj_balance_max_abs", "sens_min", "sens_max", "special_dividend_years")}, indent=1, default=float))
    print(json.dumps(k["drivers"], indent=1))
