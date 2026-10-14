#!/usr/bin/env python3
"""build_constituents.py — board membership from the master table.

The eastmoney board endpoint (push2his/push2delay clist?fs=b:<BK>) started
refusing connections from this container after a few hundred requests, and
akshare's board endpoints route through the same host. Rather than keep
hammering it, derive membership from the TradingView sector/industry mapping
that is already in master/universe.json (5309 stocks carry it).

This produces two artefacts:
  data/sector/industry_constituents/<BK>.json   eastmoney BK code -> members,
      mapped through a name bridge so existing BK consumers keep working
  data/sector/tv_groups.json                    the raw TV grouping, which is
      the source of truth when the BK bridge is unavailable

The BK bridge only covers boards whose name matches a TV sector/industry; the
rest stay empty and are reported, not silently dropped.
"""
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log(m):
    print(f"[cons] {m}", flush=True)


def norm(s):
    """Loose name match: strip spaces and common suffixes."""
    if not s:
        return ""
    s = str(s).replace(" ", "").replace("　", "")
    for suf in ("概念", "板块", "行业", "指数", "ETF", "LOF"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s.lower()


def main():
    up = os.path.join(ROOT, "data", "master", "universe.json")
    if not os.path.exists(up):
        log("master/universe.json missing")
        return 1
    stocks = json.load(open(up, encoding="utf-8"))["stocks"]

    by_sector = defaultdict(list)
    by_industry = defaultdict(list)
    for code, v in stocks.items():
        if v.get("sector_tv"):
            by_sector[v["sector_tv"]].append(code)
        if v.get("industry_tv"):
            by_industry[v["industry_tv"]].append(code)

    tv = {"sector": {k: sorted(v) for k, v in by_sector.items()},
          "industry": {k: sorted(v) for k, v in by_industry.items()}}
    outp = os.path.join(ROOT, "data", "sector", "tv_groups.json")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump({"generated_by": "build_constituents.py", "n_stocks": len(stocks),
               "n_sector": len(by_sector), "n_industry": len(by_industry),
               "groups": tv}, open(outp, "w", encoding="utf-8"),
              ensure_ascii=False)
    log(f"tv_groups.json: {len(by_sector)} sectors, {len(by_industry)} industries")

    # ── bridge eastmoney BK boards to TV groups by name ──
    # TV names are English, BK names are Chinese, so a verbatim match mostly
    # fails. Instead of shipping empty stubs, publish the TV grouping itself as
    # the membership source and keep a BK -> TV-name bridge where the Chinese
    # label happens to match.
    tv_by_norm = {}
    for scope in ("sector", "industry"):
        for name in tv[scope]:
            tv_by_norm.setdefault(norm(name), []).append((scope, name))

    for kind in ("industry", "concept"):
        src = os.path.join(ROOT, "data", "sector", f"{kind}.json")
        dst = os.path.join(ROOT, "data", "sector", f"{kind}_constituents")
        if not os.path.exists(src):
            log(f"{kind}.json missing; run build_market_db.py --boards")
            continue
        os.makedirs(dst, exist_ok=True)
        boards = json.load(open(src, encoding="utf-8"))["boards"]
        filled = empty = 0
        for b in boards:
            key = norm(b["name"])
            hits = tv_by_norm.get(key) or []
            members = []
            for scope, tvname in hits:
                for code in tv[scope][tvname]:
                    members.append({"code": code, "source": f"tv:{scope}",
                                    "group": tvname})
            payload = {
                "bk": b["bk"], "name": b["name"],
                "source": "tradingview-grouping" if members else "unmatched",
                "n": len(members),
                "members": members,
                "note": ("" if members else
                          "eastmoney board endpoint unreachable and no TV group "
                          "name matches this board; see tv_groups.json"),
            }
            with open(os.path.join(dst, f"{b['bk']}.json"), "w",
                      encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            if members:
                filled += 1
            else:
                empty += 1
        log(f"{kind}_constituents: {filled} filled, {empty} unmatched, "
            f"of {len(boards)}")

    # ── a usable stock -> board index for the site ──
    # The site needs the reverse lookup: given a stock, which boards is it in.
    idx = defaultdict(lambda: {"sector": [], "industry": []})
    for code, v in stocks.items():
        if v.get("sector_tv"):
            idx[code]["sector"].append(v["sector_tv"])
        if v.get("industry_tv"):
            idx[code]["industry"].append(v["industry_tv"])
    stock_to_board = os.path.join(ROOT, "data", "sector",
                                  "stock_to_board.json")
    json.dump({"generated_by": "build_constituents.py", "n": len(idx),
               "stocks": idx}, open(stock_to_board, "w", encoding="utf-8"),
              ensure_ascii=False)
    log(f"stock_to_board.json: {len(idx)} stocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
