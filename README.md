# stocks-data-live (盘中/收盘快照与资金流)

## 用途
盘中快照 (15 分钟循环)、资金流、涨跌停池、板块资金、大宗交易、宏观报价、情绪指标。

## 数据来源
- 腾讯 `qt.gtimg.cn` 实时行情
- 东财 `push2.ex.eastmoney.com` 涨跌停池 (API rc=102 空时 fallback 到历史 json)
- 新浪资金流 `vip.stock.finance.sina.com.cn/MoneyFlow.ssl_qsfx_zjlrqs`
- 东财大宗交易 `datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DATA_BLOCKTRADE`

## 目录结构
```
data/
  market/          全市场快照 (all_YYYY-MM-DD.txt) + 多日资金流 (flow_*.txt)
  pool/            涨跌停池 (zt/dt/zb)_{date}.json
  capflow/         东财板块/个股资金流 (sector_*.txt, stock_*.txt)
  moneyflow/       新浪资金流 (latest.txt, 按 ticker 按日累积)
  sector/          新浪行业资金流 (latest.txt, GBK → UTF-8)
  blocktrade/      大宗交易 (latest.json + latest_summary.txt)
  snapshot/        watchlist 实时快照 (latest.txt)
  macro/           宏观报价 (美债/黄金/美元/人民币)
  research/        研究沉淀 (accum/hidden patterns)
  technicals/      技术指标缓存 (latest.json)
  mon/             监控快照 (20261009_HHMM.json)
  global/          全球指数实时报价 (quotes.txt)
  emotion/
    daily.jsonl    情绪指标 (涨停/跌停/炸板率)
```

## 监控
运行: `bash ~/workspace/stocks-tools/tools/monitor_loop.sh` → 每 15 分钟写入 `data/mon/{date}_{ts}.json` 并推送到 GitHub。
监控仓单: `stocks-data-live` (private)。
