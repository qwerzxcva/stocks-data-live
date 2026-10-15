# 同花顺 (THS) 接口逆向报告 — 2026-10-15

> 调研方式：**纯只读 + 本容器实测**。未安装任何爬虫框架，未破解验证码，
> 未使用代理轮换。全部请求带正确 UA + 对应页面 Referer，间隔 0.5-1.2s（1-2 QPS）。
> 遵循 AGENTS.md §4「Crawling and reverse-engineering boundary」。
> 采集器：`scripts/ths_collect.py` ｜ 注册表：`scripts/sources_registry.py`（新增 20 条）

## 0. 结论速览

| 域 | 状态 | 价值 |
|---|---|---|
| `d.10jqka.com.cn/v6` | ✅ 全通 | 日K/月K/分时，**独立于东财腾讯的第三 K 线源** |
| `basic.10jqka.com.cn/api/stock/finance/` | ✅ 全通 | **三大报表全科目 JSON**（此前项目只有摘要），45/81/75 指标 × 103-111 报告期 |
| `basic.10jqka.com.cn/new/{code}/*.html` | ✅ 全通 | F10 九大页面静态数据：业绩预测/十大股东/分红/主营/大事/资本/行业排名/股本/个股新闻 |
| `q.10jqka.com.cn/{thshy,gn}/detail/` | ✅ 全通 | 板块成分股 14 实时字段，翻页规律已定位 |
| `news.10jqka.com.cn/tapp/news/push/stock` | ✅ 全通 | 7x24 快讯，零签名 |
| `zx.10jqka.com.cn/event/api/getharden` | ✅ 已注册 | 强势股 + 题材归因 |
| `data.10jqka.com.cn` | ❌ 401 | 2026-10-15 起全域加鉴权（龙虎榜/新股/资金流/放量排名共 9 榜单） |

**净增 20 条源，其中 18 条 ok、2 条 blocked 留档。** 项目数据源从 89 → 109。

## 1. 行情与 K 线：`d.10jqka.com.cn/v6`

### 1.1 端点矩阵（实测）

```
GET https://d.10jqka.com.cn/v6/line/{sym}/01/last.js     200  10860B  日线最近 140 根
GET https://d.10jqka.com.cn/v6/line/{sym}/01/all.js      200 190037B  日线全史 (6848 根)
GET https://d.10jqka.com.cn/v6/line/{sym}/21/last.js     200  22115B  月线全史 (347 根)
GET https://d.10jqka.com.cn/v6/time/{sym}/last.js        200   8297B  分时 (242 根/天)
```

Header：`Referer: http://d.10jqka.com.cn`，`Host: d.10jqka.com.cn`。
响应是 **JSONP**：`quotebridge_v6_line_hs_000063_01_last({...})`，需正则剥壳。

### 1.2 周期码真相（02-20/30 全部 404）

只支持两个周期码，实测 16 个候选：

| 周期码 | 结果 | 说明 |
|---|---|---|
| `01` | ✅ 日线 | `last` 给 140 根，`all` 给全史 |
| `21` | ✅ 月线 | `last` 即全史（`num == total`） |
| `02`-`20` / `30` | ❌ 404 | **周线和分钟线此域不提供** |

这是与东财 `klt=102(周)` 的差距，周线需自行从日线聚合。

### 1.3 数据字段

日线 `data` 串，`;` 分隔行、`,` 分隔列，共 11 列：

```
20260318,35.42,36.07,34.96,35.84,66984593,2399879500.00,1.663,,,0
 date    open  close high  low   volume    amount            amp  chg% chg turnover
```

坑位：
- **第 9/10 列（涨跌幅/涨跌）历史股为空串**，需用 `close/prev_close-1` 自算；
- volume 单位是**股**（东财是手），amount 单位元；
- 月线早期行含**负价格**（未复权原始口径，1997 年数据），不能直接当价格用。

顶层元数据：`start`（上市日）、`total`（历史总根数）、`num`（本次返回）、
`rt`（交易时段）、`marketType`（`HS_stock_sz`）、`today`。

### 1.4 code 前缀

| 前缀 | 实测 |
|---|---|
| `hs_{code}` | ✅ A 股通用 |
| `sh_{code}` | ✅ 沪市 |
| `sz_{code}` | 未测（推测同） |
| `hk_00700` / `us_AAPL.N` | ❌ 404，此域只服务 A 股 |

### 1.5 line 与 time 的结构差异（踩坑）

- `line` 系列：JSONP 顶层**直接是数据本体**（`rt/year/start/.../data`），无 symbol 包裹；
- `time` 系列：顶层是 `{sym: {...}}`。

统一写 `v = d.get(sym) if sym in d else d` 才能兼容，否则 `KeyError`。

## 2. 财务三大报表：`basic.10jqka.com.cn/api/stock/finance/`

### 2.1 端点与体量（000063 中兴通讯实测）

| 端点 | 体积 | 指标数 | 报告期数 |
|---|---|---|---|
| `{code}_benefit.json` | 473 KB | 45 | 111 |
| `{code}_debt.json` | 813 KB | 81 | 110 |
| `{code}_cash.json` | 670 KB | 75 | 103 |

Header：`Referer: https://basic.10jqka.com.cn/`。

### 2.2 双层 JSON 结构

```json
{
  "flashData": "<字符串化的 JSON>",
  "fieldflashData": "<另一份字符串化 JSON>"
}
```

`flashData` 解析后含 8 个表：

| 键 | 含义 |
|---|---|
| `title` | 指标名列表（45/81/75 项），含分组标记如 `报表核心指标` |
| `report` | 报告期累计（表头是 `2026-06-30` 等） |
| `simple` | 单季度 |
| `year` | 年度（表头是 `2025` 等 int） |
| `report_yoy` / `simple_yoy` / `year_yoy` | 各自同比 |
| `simple_mom` | 单季环比 |

### 2.3 三个坑

1. **`report[1]` 是分隔空行**（全空串），真实数据从 `report[2]` 开始；
2. **值是带单位字符串**：`"27.85亿"`、`"780.25亿"`、`"--"`，入库前必须 parse；
3. `year` 表头是**年份 int**，不是日期，与 report 表不能混用同一套列名。

### 2.4 利润表指标全集（45 项）

核心指标 6 项（净利润/营业总收入/营业总成本/归母净利润/扣非净利润），
报表全部指标 39 项：营业总收入及其中营业收入、营业总成本及其中营业成本、
营业税金及附加、销售/管理/研发/财务费用、利息费用与收入、资产/信用减值损失、
公允价值变动收益、投资收益及其中联营合营、资产处置收益、其他收益、
营业利润、营业外收支、非流动资产处置损失、利润总额、所得税费用、净利润、
持续经营净利润、归母净利润、少数股东损益、扣非净利润、
每股收益（基本/稀释）、其他综合收益及其归属、综合收益总额及其归属。

**这是项目此前完全缺失的数据**——registry 里只有 `stock_financial_abstract_ths` 摘要
（8 个指标），现在有全科目 45+81+75 = 201 个指标 × 最多 111 个报告期。

### 2.5 与 akshare 的路线差异

akshare 的 `stock_financial_abstract_ths` 走 `basic.10jqka.com.cn/new/{code}/finance.html`
HTML 里的 `<p id="main">`，需 BeautifulSoup 解析。直接打
`/api/stock/finance/{code}_benefit.json` 跳过 HTML，且**同时拿到三大报表**，
实测单次 1.5s vs akshare 全流程数秒。

## 3. F10 九大页面：`basic.10jqka.com.cn/new/{code}/{page}.html`

**编码是 GBK**（`Content-Type: text/html; charset=gbk`），
用 utf-8 解码会全乱码——这是最容易踩的坑。

| 页面 | 体积 | 内联 JSON | HTML 表 | 关键内容 |
|---|---|---|---|---|
| `worth` | 115 KB | `yjycData` | 31 | 机构业绩预测（2026/2027 一致预期）+ 机构预测明细 + 研究员评级 |
| `holder` | 160 KB | `gdrsFlashData` | 19 | 股东人数**旬频** + 十大股东/十大流通股东 5 期（含 orgid） |
| `bonus` | 96 KB | `bonusData` | 16 | 分红方案 59 期 + 增发 + 配股 + 获配机构 |
| `operate` | 132 KB | — | 9 | 主营构成（地区/产品双维度）+ 前 5 大客户/供应商集中度 |
| `event` | 459 KB | — | 21 | 高管增减持 175 行 + 股东增减持 64 行 + 机构调研 338 家 + 担保 + 处罚 + 披露日历 |
| `field` | 195 KB | — | 4 | 每股收益/每股净资产同行排名（42-94 只对照） |
| `capital` | 132 KB | — | 94 | 募集资金 + 项目承诺/已投入/建设期 + 并购 24 笔 |
| `equity` | 79 KB | `astockconstrData1/2` | 5 | 股本结构比例 + 解禁时间表 139 行 |
| `news` | 301 KB | `linkagedata` | 0 | 个股新闻全史（seq/ctime/title/source/author/type） |
| `position` | 40 KB | — | 0 | 空（JS 渲染） |
| `main` | 0 B | — | — | 不存在 |

### 3.1 股东人数是旬频（重要）

`gdrsFlashData` 实测：

```
[["2026-09-30","643175","30.58","股东人数"],
 ["2026-09-18","650287","32.44","股东人数"],
 ["2026-09-10","649787","32.45","股东人数"],
 ...]
```

每 10 天一个点，比东财的月频密度高 3 倍，对判断筹码集中/分散更灵敏。

### 3.2 十大股东表带 orgid

```html
<a class="clientJump" orgid="00000379" ...>中兴新通讯有限公司</a>
<td>9.61亿</td><td>不变</td><td class="tc">20.09%</td><td>流通A股,流通H股</td>
```

`orgid` 可关联 `kuaicha365.com/company_/{orgid}`，持股数字是**中文单位**
（`9.61亿` / `6079.54万`），需 parse。

### 3.3 业绩预测（`yjycData`）

```json
[["2019","1.22","51.48","SJ"],["2025","1.17","56.18","SJ"],
 ["2026","1.28","61.38","YC"],["2027","1.47","70.44","YC"]]
```

`SJ`=实际、`YC`=预测。含 2026/2027 一致预期 EPS 与净利润，
**是估值模型最缺的前瞻输入**。

## 4. 板块：`q.10jqka.com.cn`

### 4.1 成分股翻页规律（实测定位）

akshare 用的 `/thshy/index/field/199112/order/desc/page/{n}/ajax/1/` 现在**全 404**。
真实可用路径是：

```
http://q.10jqka.com.cn/thshy/detail/code/{bk}/page/{n}/     ← 有效
http://q.10jqka.com.cn/gn/detail/code/{bk}/page/{n}/        ← 概念同
```

实测 `page/2` 返回序号 21 起（每页 20 只），`?page=2` **无效**（返回第 1 页）。

字段 14 个：序号/代码/名称/现价/涨跌幅%/涨跌/涨速%/换手%/量比/振幅%/成交额/流通股/流通市值/市盈率。

### 4.2 板块列表与板块 K 线

- 列表 `/thshy/index/.../ajax/1/` 与 `/gn/index/.../ajax/1/`：**401**（2026-10-15 起），
  需改用 akshare 封装（已注册 `ths_industry_list` / `ths_concept_list`，走 `d.10jqka` 域不受影响）；
- 板块日K `https://d.10jqka.com.cn/v4/line/bk_{bk}/01/{year}.js`：✅ 200，14KB/年；
  **坑**：`bk_881272`（软件开发）通，`bk_301558` 404——概念板块的内部码与列表码不一致，
  必须先从概念列表页取 `detail/code/{码}` 才能拼对。

## 5. 快讯：`news.10jqka.com.cn/tapp/news/push/stock`

零签名 JSON，`page`/`tag`/`track=website` 三参数，实测 20 条/页。
字段 `title/digest/rtime(unix)/url/seq/id`。覆盖全球财经（不只 A 股），
与东财 7x24、新浪 zhibo 构成三源互备。

## 6. 已失效域：`data.10jqka.com.cn`（401）

2026-10-15 实测以下全部 HTTP 401（换 Referer/Host 无效，是登录态要求）：

| 子路径 | 榜单 |
|---|---|
| `/rank/cxfl/` | 持续放量 |
| `/rank/cxsl/` | 持续下跌 |
| `/rank/lxsz/` `/lxxd/` | 连续上涨/下跌天数 |
| `/rank/ljqd/` `/ljqs/` | 量价齐涨/齐跌 |
| `/rank/cxg/` `/cxd/` | 创新高/新低 |
| `/rank/xstp/` `/xxtp/` | 向上/向下突破 |
| `/funds/hyzjl/` `/gnzjl/` `/ggzjl/` | 行业/概念/个股资金流 |
| `/funds/ddzz/` | 大单异动 |
| `/ipo/xgsr/` `/syg/` | 新股上市/申购 |
| `/ifmarket/lhbyyb/` | 龙虎榜营业部 ✅ **这条仍 200** |

**已注册 2 条 blocked 源留档**（`ths_rank_cxfl` / `ths_funds_flow_rank`），
避免下次重复探测。若后续拿到匿名 cookie，该域 9 个独家榜单值得补采——
其中「创新高/连续上涨」类榜单与项目打板池逻辑直接相关。

## 7. 采集器 `scripts/ths_collect.py`

```bash
python3 scripts/ths_collect.py --group kline   --codes 000063,600519
python3 scripts/ths_collect.py --group finance --codes 000063 --statements benefit,debt,cash
python3 scripts/ths_collect.py --group f10     --codes 000063
python3 scripts/ths_collect.py --group board   --board-kind thshy --board-code 881272 --board-pages 5
python3 scripts/ths_collect.py --group news
python3 scripts/ths_collect.py --group all     --codes 000063,600519,000001,300750
```

内置：3 次重试 + 指数退避、0.5-1.0s 节流、GB18030 解码、JSONP 剥壳、
空行分隔跳过、单位字符串保留原值（parse 交给下游）。

## 8. 证据分级

| 结论 | 来源 |
|---|---|
| 全部端点 200/404/401 状态 | 本容器 2026-10-15 23:30-23:50 实测 |
| 字段含义与列序 | 响应体实测 + akshare 源码注释交叉验证 |
| 周期码只支持 01/21 | 实测 16 个候选码 |
| 翻页规律 `page/{n}/` | 实测 7 种 URL 模式 |
| data 域 401 是登录态要求 | 换 Referer/Host/UA 均 401，非 UA 问题 |
| 概念板块 bk 码不一致 | `bk_301558` 404 vs `bk_881272` 200 |
