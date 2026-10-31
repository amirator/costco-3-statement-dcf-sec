"""Fetch SEC EDGAR XBRL company facts + submissions for Costco (CIK 909832). Writes data/raw + manifest."""
import os, datetime as dt, hashlib, json, pathlib, sys, time
import requests

CIK = "0000909832"
UA = {"User-Agent": os.environ.get("SEC_UA", "Amir Khan amirator@outlook.com")}  # SEC fair-access policy: name + contact email
URLS = {"companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json",
        "submissions": f"https://data.sec.gov/submissions/CIK{CIK}.json"}

def main(out="data/raw"):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True); man = {}
    for name, url in URLS.items():
        r = requests.get(url, headers=UA, timeout=120); r.raise_for_status()
        p = out / f"{name}.json"; p.write_bytes(r.content)
        man[name] = {"url": url, "bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest(),
                     "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        time.sleep(0.5)
    (out / "manifest.json").write_text(json.dumps(man, indent=2))
    print(json.dumps(man, indent=2))

if __name__ == "__main__":
    main(*sys.argv[1:])
