#!/usr/bin/env python3
# THS probe — 同花顺接口实测 (AGENTS.md §4: 正确 UA/Referer + 1-2 QPS)
import json
import sys
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}
OUT = "/tmp/ths_probe_%s.json"


def probe(name, url, hdr=None, timeout=15):
    h = dict(UA)
    h.update(hdr or {})
    t = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
        b = r.read()
        print(f"{name:36s} -> {r.status} {len(b)}B {time.time()-t:.1f}s", flush=True)
        return {"name": name, "url": url, "status": r.status, "bytes": len(b),
                "secs": round(time.time() - t, 2), "sample": b[:400].decode("utf-8", "replace")}
    except Exception as e:
        print(f"{name:36s} -> ERR {type(e).__name__} {str(e)[:90]}", flush=True)
        return {"name": name, "url": url, "error": f"{type(e).__name__} {e}"}


THS_HDR = {"Referer": "http://q.10jqka.com.cn/", "Host": "q.10jqka.com.cn"}
D_HDR = {"Referer": "http://d.10jqka.com.cn", "Host": "d.10jqka.com.cn"}
DATA_HDR = {"Referer": "http://data.10jqka.com.cn/", "Host": "data.10jqka.com.cn"}
NEWS_HDR = {"Referer": "https://news.10jqka.com.cn/realtimenews.html", "Host": "news.10jqka.com.cn"}

TARGETS = [
    # ── 已有 registry 记录的复核 ──
    ("ths_industry_list", "http://q.10jqka.com.cn/thshy/index/field/199112/order/desc/page/1/ajax/1/", THS_HDR),
    ("ths_concept_list", "http://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/1/ajax/1/", THS_HDR),
    ("ths_strong_stocks", "http://zx.10jqka.com.cn/event/api/getharden/date/20261014/orderby/date/orderway/desc/charset/GBK/", {"Referer": "http://zx.10jqka.com.cn/"}),
    ("ths_industry_detail", "http://q.10jqka.com.cn/thshy/detail/code/881272/", THS_HDR),
    ("ths_concept_detail", "http://q.10jqka.com.cn/gn/detail/code/301558/", THS_HDR),
    # ── 新候选 (akshare 源码里挖出来的) ──
    ("ths_bk_kline_industry", "https://d.10jqka.com.cn/v4/line/bk_881272/01/2026.js", D_HDR),
    ("ths_bk_kline_concept", "https://d.10jqka.com.cn/v4/line/bk_301558/01/2026.js", D_HDR),
    ("ths_lhb_yybpm", "https://data.10jqka.com.cn/ifmarket/lhbyyb/type/1/tab/btcz/field/xsjs/sort/desc/page/1/", DATA_HDR),
    ("ths_ipo_xgsr", "https://data.10jqka.com.cn/ipo/xgsr/field/SSRQ/order/desc/page/1/ajax/1/free/1/", DATA_HDR),
    ("ths_ipo_syg", "https://data.10jqka.com.cn/ipo/syg/field/invest/order/desc/page/1/ajax/1/free/1/", DATA_HDR),
    ("ths_rank_lxsz", "https://data.10jqka.com.cn/rank/lxsz/field/lxts/order/desc/page/1/ajax/1/free/1/", DATA_HDR),
    ("ths_rank_lxxd", "https://data.10jqka.com.cn/rank/lxxd/field/lxts/order/desc/page/1/ajax/1/free/1/", DATA_HDR),
    ("ths_rank_cxsl", "https://data.10jqka.com.cn/rank/cxsl/field/count/order/desc/ajax/1/free/1/page/1/free/1/", DATA_HDR),
    ("ths_rank_ljqd", "https://data.10jqka.com.cn/rank/ljqd/field/count/order/desc/ajax/1/free/1/page/1/free/1/", DATA_HDR),
    ("ths_funds_hyzjl", "http://data.10jqka.com.cn/funds/hyzjl/field/tradezdf/order/desc/ajax/1/free/1/", DATA_HDR),
    ("ths_funds_gnzjl", "http://data.10jqka.com.cn/funds/gnzjl/field/tradezdf/order/desc/ajax/1/free/1/", DATA_HDR),
    ("ths_funds_ggzjl", "http://data.10jqka.com.cn/funds/ggzjl/field/zdf/order/desc/ajax/1/free/1/", DATA_HDR),
    ("ths_funds_ddzz", "http://data.10jqka.com.cn/funds/ddzz/order/desc/ajax/1/free/1/", DATA_HDR),
    ("ths_news_push", "https://news.10jqka.com.cn/tapp/news/push/stock?page=1&tag=&track=website", NEWS_HDR),
    ("ths_basic_finance", "https://basic.10jqka.com.cn/api/stock/finance/000063_benefit.json", {"Referer": "https://basic.10jqka.com.cn/", "Host": "basic.10jqka.com.cn"}),
]


def main():
    results = []
    for name, url, hdr in TARGETS:
        results.append(probe(name, url, hdr))
        time.sleep(0.7)  # 1-2 QPS
    ts = time.strftime("%Y%m%d")
    with open(OUT % ts, "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "targets": results},
                  f, ensure_ascii=False, indent=2)
    print(f"\n=== 落盘: {OUT % ts} ===")


if __name__ == "__main__":
    main()
