"""Turn SEC EDGAR XBRL companyfacts JSON into a tidy fiscal-year table (one value per line item per FY)."""
import datetime as dt, json, pathlib, sys
import pandas as pd

# line item -> candidate us-gaap tags (first tag with data wins per year)
FLOWS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
    "ebit": ["OperatingIncomeLoss"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating"],
    "pretax_income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
    "tax": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss"],
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
}
INSTANTS = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "receivables": ["ReceivablesNetCurrent"],
    "inventory": ["InventoryNet"],
    "ppe": ["PropertyPlantAndEquipmentNet"],
    "total_assets": ["Assets"],
    "accounts_payable": ["AccountsPayableCurrent"],
    "lt_debt": ["LongTermDebtNoncurrent"],
    "total_liabilities": ["Liabilities"],
    "total_equity": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "StockholdersEquity"],
}
SHARES = {"diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"]}


def _facts(gaap, tag, unit):
    return gaap.get(tag, {}).get("units", {}).get(unit, [])


def _days(f):
    return (dt.date.fromisoformat(f["end"]) - dt.date.fromisoformat(f["start"])).days


def pick(gaap, tags, unit, flow):
    """Return {fy_end: (value, tag)} from 10-K filings; latest filing wins (captures restatements).
    Earlier tags take priority; later tags only fill years the earlier ones miss."""
    merged = {}
    for tag in tags:
        out = {}
        for f in sorted(_facts(gaap, tag, unit), key=lambda f: f["filed"]):
            if f.get("form") != "10-K":
                continue
            if flow and not (350 <= _days(f) <= 380):
                continue
            if not flow and "start" in f:
                continue
            out[f["end"]] = (f["val"], tag)
        for k, v in out.items():
            merged.setdefault(k, v)
    return merged


def extract(companyfacts: dict, n_years: int = 6) -> pd.DataFrame:
    gaap = companyfacts["facts"]["us-gaap"]
    rows = []
    for group, unit, flow in ((FLOWS, "USD", True), (INSTANTS, "USD", False), (SHARES, "shares", True)):
        for line, tags in group.items():
            for end, (val, tag) in pick(gaap, tags, unit, flow).items():
                rows.append({"fy_end": end, "line": line, "value": float(val), "tag": tag})
    df = pd.DataFrame(rows)
    rev_ends = sorted(df.loc[df.line == "revenue", "fy_end"].unique())[-n_years:]
    df = df[df.fy_end.isin(rev_ends)].sort_values(["fy_end", "line"]).reset_index(drop=True)
    return df


def main(src="data/raw/companyfacts.json", out="data/facts_fy.csv"):
    df = extract(json.loads(pathlib.Path(src).read_text()))
    df.to_csv(out, index=False)
    print(df.pivot(index="line", columns="fy_end", values="value"))


if __name__ == "__main__":
    main(*sys.argv[1:])
