# A 股生态数据源普查报告

**生成时间**: 2026-10-13 19:05 CST
**探测环境**: Alpine aarch64 Docker 容器，零凭据，无代理
**配套 JSON**: `data_source_catalog_20261013.json`

---

## 结论速览

| 域 | 总数 | 可用 (ok/degraded) | 拦截 (waf/unavailable) | 未验证 |
|---|---|---|---|---|
| 实时行情 | 6 | 4 | 2 (东财 push2) | 0 |
| K线 | 6 | 6 | 0 | 0 |
| 资金流/龙虎榜 | 4 | 4 | 0 | 0 |
| 财务 | 5 | 5 | 0 | 0 |
| 新闻/舆情 | 4 | 2 | 0 | 0 |
| 基金/ETF | 3 | 3 | 0 | 0 |
| 事件(公告) | 4 | 2 | 2 | 0 |
| 社交 | 4 | 1 | 3 | 0 |
| 交易所官方 | 2 | 0 | 0 | 2 |
| **合计** | **38** | **27** | **7** | **2** |

---

## 数据源目录（按域分节）

### 一、实时行情

| 源 | 域名 | 鉴权 | 状态 | 探测证据 | 接入方式 | 限频建议 |
|---|---|---|---|---|---|---|
| 腾讯实时行情 | qt.gtimg.cn | 零凭据 | ✅ 可用 | HTTP 200, 60码/批, ~200B | direct_json | 50 req/s, ~1750次后501 |
| 新浪实时行情 | hq.sinajs.cn | 零凭据+Referer | ✅ 可用 | HTTP 200, gbk, 需Referer: finance.sina.com.cn | direct_json | 同腾讯 |
| 东财个股行情 | push2.eastmoney.com | 零凭据 | ❌ WAF拦截 | ERR: ConnectionResetError (TLS reset) | direct_json | 不适用 |
| 东财板块clist | push2.eastmoney.com | 零凭据 | ❌ WAF拦截 | ERR: ConnectionResetError (~20次后封) | direct_json | 不适用 |
| 抖音热搜 | aweme.snssdk.com | 零凭据+移动UA | ✅ 可用 | HTTP 200, JSON 30+条 | direct_json | 30s/次 |
| TradingView | scanner.tradingview.com | 零凭据 | ✅ 可用 | HTTP 200, POST, 7476只 | direct_json (POST) | 10 req/min |

**降级链**：东财 push2 WAF 拦截 → 行业映射用 `industry_map_tv.json`（TV 全量），资金流用涨停池主题聚类占比

### 二、K线

| 源 | 域名 | 鉴权 | 状态 | 探测证据 | 接入方式 | 限频建议 |
|---|---|---|---|---|---|---|
| 腾讯日K(qfq) | web.ifzq.gtimg.cn | 零凭据 | ✅ 可用 | HTTP 200, 全史 ~6000根/股, 指数8740根 | direct_json | 并发10, 0.15s间隔 |
| 东财日K(push2his) | push2his.eastmoney.com | 零凭据 | ✅ 可用 | HTTP 200, 381B, dktotal=6019(茅台) | direct_json | 10 req/s |
| 新浪日K(akshare) | hq.sinajs.cn | 零凭据 | ✅ 可用 | rows=6019, dt=0.79s | library(akshare) | 同新浪 |
| 东财日K(akshare) | push2his.eastmoney.com | 零凭据 | ✅ 可用 | rows=489(2024起), dt=0.25s | library(akshare) | 10 req/s |
| 腾讯指数全史 | web.ifzq.gtimg.cn | 零凭据 | ✅ 可用 | rows=8740(上证1990起), dt=14.24s | direct_json | 10 req/min |
| 新浪ETF日K | akshare | 零凭据 | ✅ 可用 | rows=3294, dt=0.27s | library(akshare) | 10 req/min |

**注意**：push2his 域**不在** push2 WAF 封锁范围内，可直接使用；东方财富 K 线接口是替代腾讯的降级候选

### 三、资金流/龙虎榜

| 源 | 端点 | 鉴权 | 状态 | 探测证据 | 关键字段 |
|---|---|---|---|---|---|
| 东财龙虎榜 | datacenter-web.eastmoney.com | 零凭据 | ✅ 可用 | HTTP 200, 50行, 2026-10-13 | BILLBOARD_DEAL_AMT, EXPLAIN, D1/D5_ADJCHRATE |
| 东财大宗交易 | datacenter-web.eastmoney.com | 零凭据 | ✅ 可用 | HTTP 200, 50行, 2026-10-13 | DEAL_PRICE, PREMIUM_RATIO, BUYER/SELLER_NAME |
| 东财两融余额 | datacenter-web.eastmoney.com | 零凭据 | ✅ 可用 | sortColumns=dim_date（不带 filter） | DIM_DATE, RZYE, RQYE |
| 东财涨跌停池 | push2ex.eastmoney.com | 零凭据 | ✅ 可用 | HTTP 200, tc 权威计数 | code/name/连板/封板时间 |

**重要发现**（2026-10-13 新探测）：
- 龙虎榜 datacenter 接口**不带 filter** 直接按 `sortColumns=TRADE_DATE&sortTypes=-1` 可以取到最新 50 条数据
- 带 `filter=(TRADE_DATE='2026-10-10')` 时返回"返回数据为空"——原因：日期横杠格式，但当日凌晨数据尚未生成
- **结论：使用不带 filter + sortColumns=TRADE_DATE desc 的写法最稳定**

### 四、财务数据

| 源 | 鉴权 | 状态 | 探测证据 | 字段覆盖 |
|---|---|---|---|---|
| 同花顺财务摘要 (v1) | 零凭据 | ✅ 可用 | rows=103, dt=0.90s | 净利润/扣非/收入/ROE/毛利率/负债率 |
| 同花顺财务摘要 v2 | 零凭据 | ✅ 可用 | rows=1200, dt=0.26s | metric_name/value/yoy/mom（长表，适合入库） |
| 同花顺行业板块 | 零凭据 | ✅ 可用 | rows=90, dt=0.22s | 90 个行业 name+code |
| 同花顺概念板块 | 零凭据 | ✅ 可用 | rows=375, dt=8.27s | 375 个概念 name+code |
| 国家统计局(CPI/GDP) | 零凭据 | ✅ 可用 | CPI rows=224, GDP rows=82 | 月度CPI/季度GDP 同比环比 |

**同花顺域名零 WAF**：ths90.10jqka.com.cn 和 d.10jqka.com.cn 均无 WAF，稳定可用

### 五、新闻与舆情

| 源 | 状态 | 探测证据 | 备注 |
|---|---|---|---|
| 新浪 7x24 | 🟡 降级 | HTTP 200 但 data=[] zhibo_id missing (113B) | 降级链：远端 data-news 兜底 |
| 东财 7x24 (np-listapi) | 🟡 降级 | 需 req_trace=UUID 参数；不带则 404 | 容器内 567/400 居多 |
| 远端 news 仓 | ✅ 可用 | 部分日期 404（未生成属正常） | 由远端 CI 每日生成 |
| 抖音热搜 | ✅ 可用 | HTTP 200 JSON 30+条 | 移动端 UA 必带 |

### 六、基金/ETF

| 源 | 状态 | 探测证据 | 关键字段 |
|---|---|---|---|
| 东财基金持仓 (pingzhongdata JS) | ✅ 可用 | HTTP 200, 521KB JS literal | stockCodes(前10大重仓)/fund_Rate/fund_minsg |
| 东财 ETF 净值 (akshare) | ✅ 可用 | rows=784, 511280 全史 | 单位净值/累计净值/日增长率 |
| 东财混合基金排行 | ✅ 可用 | HTML 解析 49 条 | KOL 抱团方向代理指标 |

### 七、事件（公告/停复牌/定增）

| 源 | 状态 | 探测证据 | 备注 |
|---|---|---|---|
| 巨潮资讯 (cninfo.com.cn) | ❌ 本容器不可用 | HTTP 500 | 国内网络可能正常，需本地测试 |
| 东财公告 API (np-ann) | 🟡 降级 | HTTP 200 返回 HTML SPA 壳 | 需 XHR 头（未验证） |
| 深交所 API | ❌ 本容器不可用 | HTTP 500 | CATALOGID 可能已变更 |
| 上交所 API | 🟡 未验证 | HTTP 200 但 data=null | sqlId 可能需配合 session |

### 八、社交/舆情

| 源 | 鉴权要求 | 状态 | 探测证据 | 替代方案 |
|---|---|---|---|---|
| 抖音热搜 | 零凭据+移动UA | ✅ 可用 | HTTP 200, 30+条 | — |
| 小红书 | cookie+浏览器渲染 | ❌ 不可零凭据接入 | 所有 API 路径 404 | 同花顺概念板块 |
| 雪球热榜 | xq_a_token cookie | ❌ 不可零凭据接入 | 404/400 anti-bot JS | 东财股吧 |
| 腾讯新闻作者页 | 浏览器渲染 | ❌ 不可零凭据接入 | SPA 壳，后端 404 | 新浪新闻 |

---

## 与已知结论矛盾/补充处

### 新发现（此前 sources_registry.py 未记录）

1. **东财 datacenter 不带 filter 可直接查最新数据**
   - `sortColumns=TRADE_DATE&sortTypes=-1` 不带 filter 参数
   - 2026-10-13 实测取到 50 行 2026-10-13 数据
   - 带 `filter=(TRADE_DATE='2026-10-10')` 时返回空（当日凌晨数据未出，需回退）

2. **em_margin 正确排序字段是 `dim_date` 非 `TRADE_DATE`**
   - `collect_market_extras.py` 已有正确实现，但 sources_registry 中未注明

3. **akshare 安装验证 (v1.19.1)**
   - 东财 push2 域所有接口（`stock_zh_a_spot_em`/`board_industry_name_em` 等）：ConnectionResetError，与已有 WAF 结论一致
   - 同花顺（`stock_financial_abstract_new_ths`/`stock_board_concept_name_ths`）：全部正常，**同花顺域名零 WAF**
   - 新浪/腾讯接口：全部正常
   - 东财 datacenter 域（`stock_lhb_detail_em`）：可用，底层走 datacenter-web.eastmoney.com

4. **巨潮资讯本容器不可用（HTTP 500）**
   - 此前未测试，本次发现 cninfo.com.cn 在本容器返回 500
   - 推测原因：海外 IP 对 cninfo.com.cn 有限制；国内网络应该正常

5. **深交所/上交所 API 本容器均不可用（HTTP 500/null）**
   - 深交所 CATALOGID=1835/1803/1805 均 500
   - 上交所 commonQuery.do 返回 200 但 data=null（sqlId 可能过期）

---

## 数据库层改动

**文件**: `~/workspace/stocks-ai-view/scripts/db_layer.py`

### 新增表（5 张）
| 表名 | 用途 | 分区键 |
|---|---|---|
| announcements | 公告 | ann_date |
| news_items | 新闻快讯 | ts |
| fund_nav | 基金/ETF 净值 | fund_code, date |
| fund_rebalance | 基金重仓股 | fund_code, report_date |
| financial_summary | 财务摘要 (同花顺 v2 长表) | code, report_date |

### 新增覆盖索引（8 条）
- `idx_quotes_chg_cover ON quotes(trade_date, chg_pct, code, name, price)` — 补齐缺失的 ORDER BY 扫描
- `idx_quotes_pe_pb_cover ON quotes(trade_date, pe, pb, code, name)` — 低估值筛选覆盖
- `idx_events_deal_cover ON events(trade_date, deal_amt, code, name, type)` — 按成交额排序覆盖
- 各新表各自索引

### 分区声明修复
- 文档字符串中的"分区: trade_date"改为"隐式分区: trade_date (DuckDB zone maps, 非显式 PARTITION BY)"
- DuckDB 不创建 `PARTITION BY` 子句，使用列式存储 + zone maps 实现隐式分区效果

---

## 数据接口调用示例

### 龙虎榜（已跑通 ✓）
```bash
# 抓取并入库
python3 ~/workspace/stocks/tools-repo/tools/e2e_lhb_pipeline.py

# 查询最新龙虎榜前 10
python3 ~/workspace/stocks-ai-view/scripts/query_api.py events --type lhb --limit 10

# 查指定日期
python3 ~/workspace/stocks-ai-view/scripts/query_api.py events --type lhb --date 2026-10-13 --limit 20

# 导出 CSV
python3 ~/workspace/stocks-ai-view/scripts/query_api.py events --type lhb --limit 50 --csv --out /tmp/lhb.csv
```

### 两融
```bash
python3 ~/workspace/stocks-ai-view/scripts/query_api.py margin --limit 30
```

### 行情（需已有数据）
```bash
python3 ~/workspace/stocks-ai-view/scripts/query_api.py quotes --top 20 --by chg_pct
python3 ~/workspace/stocks-ai-view/scripts/query_api.py quotes --low-value
python3 ~/workspace/stocks-ai-view/scripts/query_api.py quotes --code 600519
```

### K线
```bash
python3 ~/workspace/stocks-ai-view/scripts/query_api.py kline --code 600519 --days 20
```

### 全库统计
```bash
python3 ~/workspace/stocks-ai-view/scripts/query_api.py stats
```

---

## 已跑通 vs 未验证 清单

### 已跑通 ✓
- 龙虎榜/大宗交易抓 → 存 DuckDB → query_api 读出（`e2e_lhb_pipeline.py`）
- query_api.py 全部 10 个子命令（events/margin/quotes/kline/stats 等）
- db_layer.py 新建 5 张表 + 8 条索引（`--init` 验证 11 张表 20 条索引）
- 东财 datacenter 龙虎榜 50 行、大宗交易 50 行（零凭据直接 HTTP 200）
- 同花顺概念板块 375 个、行业板块 90 个（akshare 正常返回）
- 东财 ETF 净值 784 行（akshare fund_etf_fund_info_em）
- 腾讯/新浪 K线全史（akshare 验证）

### 未验证 / 本容器不可用
- 巨潮资讯（cninfo.com.cn）：本容器 HTTP 500，国内网络应可用（未验证）
- 深交所/上交所官方 API：本容器均 HTTP 500/null，sqlId 可能过期（未验证）
- 东财公告 API (np-ann)：加 XHR 头是否返回 JSON 未验证
- 基金净流入 (fund_nav 表填充管线)：表已建，数据填充脚本未写
- 财务摘要入库 (financial_summary 表填充管线)：表已建，数据填充脚本未写
- akshare stock_zh_a_spot_em：东财 push2 WAF 拦截（已知，与生产降级链一致）

### 被 WAF 拦截的替代方案
| 被拦截源 | 替代 | 现状 |
|---|---|---|
| 东财 push2 实时行情 | TradingView (15分钟延迟) + 腾讯实时 | 生产在用 |
| 东财 push2 clist 资金流 | 涨停池主题聚类占比 | 生产在用 |
| 巨潮资讯公告 | 东财 np-ann（待 XHR 验证）| 降级方案 |
| 同花顺行业接口 | industry_map_tv.json（TV 全量缓存）| 生产在用 |

---

## 后续建议扩展顺序

1. **同花顺财务摘要入库**（高价值，已有可用 akshare 接口，financial_summary 表已建）
2. **东财基金净值 (fund_nav) 数据填充**（已有 akshare fund_etf_fund_info_em 验证）
3. **巨潮资讯本地测试**（需大陆出口 IP 环境验证）
4. **东财 np-ann 公告 API XHR 头验证**（可能解锁公告域）
5. **新闻快讯自动入库**（news_items 表已建，填充管线需实现）
6. **akshare 批量采集脚本**（统一采集入口，覆盖全领域数据）

---

*本报告基于 2026-10-13 实测数据，探测环境为 Alpine aarch64 容器（海外 IP），国内网络表现可能有差异。*
