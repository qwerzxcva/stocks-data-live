#!/usr/bin/env python3
"""refetch_constituents.py — rebuild the board membership tables.

The constituents directories were lost when the local data tree was cleared,
which severed the stock -> board link. This re-pulls every board's membership
and writes data/sector/{industry,concept}_constituents/<BK>.json.

Endpoint strategy: the eastmoney board endpoint refuses connections from this
container after a few hundred requests, and the block is per-IP rather than
per-host, so simply swapping push2his for push2delay does not help. This script
therefore probes a list of endpoints once up front, keeps the ones that answer,
and rotates through them per request. If nothing answers it exits non-zero and
points at build_constituents.py, which derives membership from the TradingView
grouping instead of hammering a blocked host.

Run from GitHub Actions (North America egress) the eastmoney endpoints are
reachable, which is what workflows/board-constituents.yml uses.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}

# probed in order; the first that answers becomes the primary, the rest are
# tried in rotation when a request fails
ENDPOINTS = [
    "https://push2his.eastmoney.com/api/qt/clist/get",
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://push2ex.eastmoney.com/api/qt/clist/get",
]


def log(m):
    print(f"[cons] {m}", flush=True)


def probe(endpoints):
    """Return the endpoints that answered a real request, best first."""
    good = []
    for ep in endpoints:
        url = f"{ep}?fs=b:BK0420&fields=f12,f14&pn=1&pz=1"
        try:
            req = urllib.request.Request(url, headers=UA)
            d = json.load(urllib.request.urlopen(req, timeout=15))
            if d.get("data") and d["data"].get("diff"):
                good.append(ep)
                log(f"  reachable: {ep.split('/')[2]}")
            else:
                log(f"  answered but empty: {ep.split('/')[2]}")
        except Exception as e:
            log(f"  unreachable: {ep.split('/')[2]} ({type(e).__name__})")
        time.sleep(0.3)
    return good


def fetch(bk, endpoints, retries=3):
    """Membership for one board, rotating endpoints on failure."""
    for attempt in range(retries):
        ep = endpoints[attempt % len(endpoints)]
        url = f"{ep}?fs=b:{bk}&fields=f12,f13,f14&pn=1&pz=500"
        try:
            req = urllib.request.Request(url, headers=UA)
            d = json.load(urllib.request.urlopen(req, timeout=25))
            if d.get("data"):
                mem = [{"code": v["f12"], "market": v.get("f13"),
                        "name": v.get("f14")}
                       for v in d["data"]["diff"].values()]
                return {"bk": bk, "n": d["data"].get("total"),
                        "members": mem, "source": ep.split("/")[2]}
        except Exception:
            pass
        time.sleep(1.0 * (attempt + 1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-probe", action="store_true",
                    help="assume the endpoints are reachable")
    a = ap.parse_args()

    if a.skip_probe:
        endpoints = ENDPOINTS
    else:
        log("probing endpoints...")
        endpoints = probe(ENDPOINTS)
        if not endpoints:
            log("no eastmoney endpoint answered from this network.")
            log("Use build_constituents.py (TradingView grouping) instead, or "
                "run workflows/board-constituents.yml on GitHub Actions.")
            return 2

    total_ok = total_fail = 0
    for kind in ("industry", "concept"):
        src = os.path.join(ROOT, "data", "sector", f"{kind}.json")
        dst = os.path.join(ROOT, "data", "sector", f"{kind}_constituents")
        if not os.path.exists(src):
            log(f"{kind}.json missing; run build_market_db.py --boards first")
            continue
        os.makedirs(dst, exist_ok=True)
        boards = json.load(open(src, encoding="utf-8"))["boards"]
        ok = fail = 0
        for b in boards:
            r = fetch(b["bk"], endpoints)
            if r:
                with open(os.path.join(dst, f"{b['bk']}.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(r, f, ensure_ascii=False)
                ok += 1
            else:
                fail += 1
            time.sleep(0.12)
        total_ok += ok
        total_fail += fail
        log(f"{kind}: {ok} ok, {fail} fail, of {len(boards)}")

    log(f"total: {total_ok} ok, {total_fail} fail")
    return 0 if total_ok else 3


if __name__ == "__main__":
    sys.exit(main())
