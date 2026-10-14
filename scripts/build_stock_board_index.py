#!/usr/bin/env python3
"""build_stock_board_index.py — reverse index from stock code to its boards.

The constituents files map board -> members. The site needs the other
direction: given a stock, which boards is it in. This builds that index from
the constituents files when they carry real membership, and falls back to the
TradingView grouping in master/universe.json when they do not (the eastmoney
endpoint is blocked from some networks).

Output: data/sector/stock_to_board.json
"""
import glob
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log(m):
    print(f"[idx] {m}", flush=True)


def bare(code):
    c = str(code)
    return c[2:] if c[:2] in ("sh", "sz", "bj") else c


def from_constituents():
    """board -> members, kept only when membership is real."""
    idx = defaultdict(lambda: {"industry": [], "concept": [], "tv": []})
    filled = 0
    for kind in ("industry", "concept"):
        for f in sorted(glob.glob(os.path.join(
                ROOT, "data", "sector", f"{kind}_constituents", "*.json"))):
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            mem = d.get("members") or []
            if not mem:
                continue
            filled += 1
            name = d.get("name") or d.get("bk")
            for m in mem:
                code = bare(m.get("code"))
                if code:
                    idx[code][kind].append(name)
    return idx, filled


def from_tv():
    """Fallback: the TradingView grouping carried in the master table."""
    up = os.path.join(ROOT, "data", "master", "universe.json")
    if not os.path.exists(up):
        return {}, 0
    stocks = json.load(open(up, encoding="utf-8"))["stocks"]
    idx = defaultdict(lambda: {"industry": [], "concept": [], "tv": []})
    for code, v in stocks.items():
        if v.get("sector_tv"):
            idx[code]["tv"].append(v["sector_tv"])
        if v.get("industry_tv"):
            idx[code]["tv"].append(v["industry_tv"])
    return idx, len(idx)


def main():
    idx, filled = from_constituents()
    source = "eastmoney-constituents"
    if not filled:
        log("no constituents carry members; falling back to the TV grouping")
        idx, n = from_tv()
        source = "tradingview-grouping"
        log(f"tv grouping covers {n} stocks")

    # merge the TV grouping in as a third channel so a stock always shows
    # something even when only one source is populated
    tv_idx, _ = from_tv()
    for code, v in tv_idx.items():
        for t in v["tv"]:
            if t not in idx[code]["tv"]:
                idx[code]["tv"].append(t)

    for v in idx.values():
        for k in ("industry", "concept", "tv"):
            v[k] = sorted(set(v[k]))

    out = os.path.join(ROOT, "data", "sector", "stock_to_board.json")
    json.dump({"generated_by": "build_stock_board_index.py",
               "source": source, "n_constituents_filled": filled,
               "n_stocks": len(idx), "stocks": idx},
              open(out, "w", encoding="utf-8"), ensure_ascii=False)
    log(f"-> {out} ({len(idx)} stocks, source={source})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
