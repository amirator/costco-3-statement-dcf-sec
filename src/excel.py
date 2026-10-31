"""Write the model to an Excel workbook: Historicals, Projections, DCF (live formulas), Sensitivity."""
import pathlib
from openpyxl import Workbook
from openpyxl.styles import Font
from model import run

LINES = ["revenue", "ebit", "interest_expense", "pretax_income", "tax", "net_income", "da", "capex",
         "dividends", "buybacks", "cash", "receivables", "inventory", "ppe", "total_assets",
         "accounts_payable", "lt_debt", "total_liabilities", "total_equity"]


def sheet(ws, df, cols):
    ws.append(["$m"] + list(df.index)); ws["A1"].font = Font(bold=True)
    for c in cols:
        ws.append([c] + [round(float(x) / 1e6, 1) for x in df[c]])
    ws.column_dimensions["A"].width = 20


def build(out="reports/costco_3statement_dcf.xlsx"):
    h, p, dv, w, v, s, k = run()
    wb = Workbook()
    sheet(wb.active, h, LINES); wb.active.title = "Historicals (SEC)"
    sheet(wb.create_sheet("Projections"), p, LINES + ["balance_check"])
    d = wb.create_sheet("DCF")
    d.append(["Input", "Value"])
    d.append(["WACC", round(w, 6)]); d.append(["Terminal growth", k["assumptions"]["terminal_growth"]])
    d.append(["Cash ($m)", round(h.cash.iloc[-1] / 1e6, 1)]); d.append(["LT debt ($m)", round(h.lt_debt.iloc[-1] / 1e6, 1)])
    d.append(["Diluted shares (m)", round(h.diluted_shares.iloc[-1] / 1e6, 3)])
    d.append([]); d.append(["Year", "t", "FCFF ($m)", "Discount factor", "PV ($m)"])
    for i, (yr, f) in enumerate(zip(p.index, v["fcff"]), start=1):
        r = d.max_row + 1
        d.append([yr, i, round(f / 1e6, 1), f"=1/(1+$B$2)^B{r}", f"=C{r}*D{r}"])
    last = d.max_row
    d.append([]); d.append(["Sum PV FCFF", f"=SUM(E9:E{last})"])
    d.append(["Terminal value", f"=C{last}*(1+B3)/(B2-B3)"])
    d.append(["PV terminal", f"=B{last+3}*D{last}"])
    d.append(["Enterprise value", f"=B{last+2}+B{last+4}"])
    d.append(["Equity value", f"=B{last+5}+B4-B5"])
    d.append(["Value per share ($)", f"=B{last+6}/B6"])
    d.column_dimensions["A"].width = 22
    ss = wb.create_sheet("Sensitivity ($-share)")
    ss.append([""] + list(s.columns))
    for idx, row in s.round(2).iterrows():
        ss.append([idx] + list(row))
    pathlib.Path(out).parent.mkdir(exist_ok=True); wb.save(out)
    return out


if __name__ == "__main__":
    print(build())
