import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pytest
from extract import extract
from model import load_hist, project, dcf, wacc, ASSUMPTIONS
from readme import render

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def m():
    h = load_hist(ROOT / "data/facts_fy.csv"); p, dv = project(h)
    return h, p, dv


def test_history_balances(m):
    h, _, _ = m
    assert ((h.total_assets - h.total_liabilities - h.total_equity).abs() < 1).all()


def test_projection_balances_and_cash_ties(m):
    _, p, _ = m
    assert p.balance_check.abs().max() < 1e-3
    assert (p.cash.diff().iloc[1:] - (p.cfo + p.cfi + p.cff).iloc[1:]).abs().max() < 1e-3


def test_dcf_math(m):
    h, p, dv = m
    w = wacc(tax_rate=dv["tax_rate"]); v = dcf(p, h, dv, w, ASSUMPTIONS["terminal_growth"])
    assert v["enterprise_value"] == pytest.approx(v["pv_fcff"] + v["pv_terminal"])
    assert dcf(p, h, dv, w + 0.01, 0.03)["per_share"] < v["per_share"]
    assert dcf(p, h, dv, w, 0.035)["per_share"] > v["per_share"]


def test_extract_synthetic():
    def f(end, val, start=None, form="10-K", filed="2025-10-01"):
        d = {"end": end, "val": val, "form": form, "filed": filed}
        if start: d["start"] = start
        return d
    cf = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [f("2025-08-31", 100, "2024-09-01"), f("2025-05-31", 25, "2025-03-01"),
                                       f("2025-08-31", 101, "2024-09-01", filed="2026-10-01")]}},
        "Assets": {"units": {"USD": [f("2025-08-31", 50)]}}}}}
    df = extract(cf)
    assert df.loc[df.line == "revenue", "value"].tolist() == [101.0]  # restatement wins, quarter dropped
    assert df.loc[df.line == "total_assets", "value"].tolist() == [50.0]


def test_readme_in_sync():
    k = json.loads((ROOT / "reports/kpis.json").read_text())
    assert (ROOT / "README.md").read_text() == render(k)


def test_fetch_requires_sec_ua(monkeypatch):
    import importlib.util
    monkeypatch.delenv("SEC_UA", raising=False)
    spec = importlib.util.spec_from_file_location("fetch_sec", ROOT / "ingest/fetch_sec.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    with pytest.raises(SystemExit):
        mod.main("/tmp/never")
