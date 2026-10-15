# 多站点股票接口逆向报告（第二批）— 2026-10-16

> 调研方式：**子代理探测 + 主代理逐条 curl/urllib 复核**。两个 Explore 子代理
> （新浪/腾讯/和讯、东财深度）无 Bash 工具，其结论全部由主代理在本容器复测后才入库。
> 纯只读，1-2 QPS，不装软件，不绕 WAF。遵循 AGENTS.md §4。
> 采集器：`scripts/em_f10_collect.py`、`scripts/xueqiu_screener_collect.py`
> 注册表：`scripts/sources_registry.py`（本轮 +32，累计 **145 个源**）

## 0. 结论速览

| 站点 | 新增 ok | 新增 degraded | 新增 blocked | 核心收获 |
|---|---|---|---|---|
| 同花顺 | 18 | 0 | 2 | 三大报表全科目 + F10 九页 + 第三 K 线源 |
| 东财 | 14 | 1 | 1 | **`emweb.securities.eastmoney.com/PC_HSF10/*/PageAjax` 富接口** |
| 腾讯 | 4 | 1 | 0 | 全市场排行 28 字段 + 任意日期区间 K 线 |
| 新浪 | 9 | 2 | 0 | ESG 5 源（10 家机构）+ 修正 akshare bug |
| 雪球 | 1 | 0 | 1 | screener 40 字段 × 5000 只 |
| 和讯 | 0 | 0 | 1 | 全死，留档 |

**数据源总数：89 → 145。**

## 1. 东财（本轮最大收获）

### 1.1 富接口：`emweb.securities.eastmoney.com/PC_HSF10/{page}/PageAjax?code=SH600519`

一次请求拿一整类 F10 数据，实测全部 200：

| 页面 | 体积 | 内容 |
|---|---|---|
| `ShareholderResearch` | 36 KB | 户数 + 十大股东 + 十大流通 + 机构持仓 + **基金持仓（含基金净值占比）** + 实控人 |
| `CompanySurvey` | 2.8 KB | 公司概况 / 高管 / 曾用名 / 发行价 / 员工数 |
| `CapitalStockStructure` | 14 KB | 最新股本 + **历年变动全史（2001-2026，含回购/送股/股改原因）** + 限售解禁 |
| `BonusFinancing` | 4.1 KB | 分红送配 + 历年分红融资（可算股息率） |
| `BusinessAnalysis` | 68 KB | 主营构成（**中文 key**：`zyfw`/`zygcfx`/`jyzl`） |
| `OperationsRequired` | 99 KB | 经营评述长文本（degraded，需 NLP） |

`ShareholderResearch` 一个接口顶 5 个单独调用，是**本轮价值最高的发现**。

### 1.2 `datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_*`

8 个可用报表（`columns=ALL&source=WEB&client=WEB`，HSF10 源要 `client=PC`）：

| 报表 | 内容 |
|---|---|
| `RPT_ORG_SURVEYNEW` | 机构调研（29 万条，含接待高管姓名） |
| `RPT_SHARE_HOLDER_INCREASE` | 股东增减持，**MARKET 区分大宗交易/二级市场** |
| `RPT_HOLDERNUMLATEST` | 最新股东户数（filter 用 `SECURITY_CODE`） |
| `RPT_MAIN_ORGHOLD` | 机构持仓全市场（32 万页，可扫机构加仓） |
| `RPT_F10_EH_FREEHOLDERS` | 十大流通股东，**IS_LANDSTOCK=1 陆股通** |
| `RPT_F10_MAIN_ORGHOLD` | 机构持仓历史（LABEL_NAME='机构重仓'） |
| `RPT_F10_CORETHEME_BOARDTYPE` | 核心题材所属板块，**含入选理由长文本** |
| `RPT_F10_FN_MAINOP` | 主营构成（英文 key 版） |

**坑**：HSF10 源的 SECUCODE 格式是 `600519.SH`（带点、代码在前），
不是 emweb PageAjax 的 `SH600519`。写错会静默返回空数组。

### 1.3 研报 `reportapi.eastmoney.com/report/list`

`qType=0` 个股研报，含 `predictThisYearEps/Pe`（券商一致预期）、
`emRatingName`/`sRatingName` 双评级、PDF 直链 `https://pdf.dfcfw.com/pdf/H3_{infoCode}_1.pdf`。
**registry 此前无任何研报源。**

### 1.4 blocked 留档

11 个 RPT_* 报表名返回 9501「报表配置不存在」；`push2` 的 `kamt.rtmin`/`ulist.np` TLS reset；
`emappdata` 需 POST；`fund rankhandler.aspx ft=all` 无权限；`api.fund` 两个路径已失效；
`search-api-web` 的 type 名已变更。全部记入 `em_datacenter_dead_reportnames`。

## 2. 腾讯

### 2.1 `proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList`

**A 股全市场 5576 只，28 字段，单次 200 只/95 KB/0.17s。**

`sort_type` 白名单极窄，实测仅 5 个有效（其余 14 个候选全返回
`code=1619377101 参数错误`）：`price` / `turnover` / `volume` / `pn` / `speed`。

`board_code` 只有 `aStock` 有数据，`hkStock`/`usStock`/`etf` 全 total=0。

字段含 `zljlr`（主力净流入）、`zllr_d5`（5 日主力流入）、
`zdf_d5/d10/d20/d60/w52/y`（多周期涨幅）、`lb`（量比）、`state`（S=停牌）。

**未核实**：`pn` 字段含义（茅台 6.53）；`volume`/`turnover`/`zsz` 单位。

### 2.2 K 线三端点

| 端点 | 结论 |
|---|---|
| `newfqkline` | ✅ **唯一支持任意起止日期区间**（`param=code,day,start,end,640,qfq`） |
| `hkfqkline` | ✅ 港股后复权，**日期参数生效**，附带除权/派息/回购事件文本 + 80 字段实时快照 |
| `usfqkline` | ⚠️ **日期参数完全失效** — 两个相隔 15 年的区间返回完全相同的 1541 字节，只按 count 退化 |

`index_weektrends` 单请求拿 20 年周线收盘价（30 KB），但只有 close，无开高低量。

## 3. 新浪

### 3.1 修正 akshare 的 bug

akshare `futures/cons.py:121-129` 写死 `node=001`，导致
`Market_Center.getHQFuturesData` **恒返回 `[]`**。正确格式是 `{大写品种}_qh`。

**但 node 白名单实测极窄**：`sngz_qh`（10 年国债）与 `IM_qh`（中证 1000）通，
`TA_qh` / `IF_qh` / `T_qh` 实测返回 `[]`。
子代理称 `TA_qh` 可用，本次复核为空 —— 已按实测标 degraded，白名单未穷举。

### 3.2 ESG 5 源（registry 全新维度）

| 源 | 条数 | 特点 |
|---|---|---|
| `getEsgStocks` | 53418 | 聚合 10 家机构，symbol 格式 `SZ000001` |
| `getMsciEsgStocks` | 8959 | E/S/G 分项 + quarter_date，结构最规范，分页用 `p` |
| `getZdEsgStocks` | 8200 | 中证，score 带评级后缀 `87.53(AAA)` 需拆 |
| `getRftEsgStocks` | 4518 | 15 细分维度，**唯一覆盖 US/CN/HK** |
| `getHzEsgStocks` | 6355 | **唯一带公司中文名**，百分制无后缀 |

### 3.3 其他

`MoneyFlow.ssl_qsfx_zjlrqs`（主力资金趋势，独有行业对比 `cate_ra/cate_na`）
与 `ssl_qsfx_lscjfb`（资金四档，生产已在用但未注册）——
注意 `netamount` 单位是**元**不是万元。
`GoodsIndexService.get_goods_index` 必须显式传 symbol，否则返回脏数据。
`StockOptionService.getStockName` ETF 期权月份日历（数据有重复项和错别字需清洗）。

## 4. 雪球：出口敏感（重要坑）

`service/v5/stock/screener/quote/list` 本机容器 IP **全 200**（5000 只、40 字段），
但 **GitHub Actions（Azure 出口）返回 HTTP 418 I'm a Teapot**。

试过 5 种变体（cookie 预热 / `xq_a_token` / 移动 UA / Referer / HTTP2）在本机都通，
说明是按 **IP 段**风控，改 header 无解。

→ 已把 `ths-collect.yml` 的雪球步改为 `if: inputs.run_xq=='true'`，默认跳过。
该源只能在**本机或 GitCode Space（大陆 IP）**跑。

独家字段：`limitup_days`（连板天数）、`percent5m`、`north_net_inflow`、`followers`、
`dividend_yield`、`roe_ttm`、`net_profit_cagr`、`income_cagr`。
**筛选参数不生效**（count 恒为全量），必须拉全量本地过滤。

## 5. 和讯：全死

akshare 全库 grep `hexun` 仅 4 处命中，对应 2 个 URL 都死：

- `webusstock.hermes.hexun.com` — **DNS 无法解析主机名**
- `stockdata.stock.hexun.com` — https 证书错乱（CN=`*.unionpayintl.com` 银联国际证书劫持），
  http 可连但 301 到 `stock.hexun.com` 首页，无 JSON 端点

已放弃猜 URL 路线，记入 `hexun_dead_all`。

## 6. 同花顺（第一批，详见 `ths_reverse_20261015.md`）

18 个 ok 源。最关键的是
`basic.10jqka.com.cn/api/stock/finance/{code}_{benefit,debt,cash}.json`
——三大报表全科目 201 个指标 × 最多 111 个报告期，**项目此前只有 8 指标摘要**。

## 7. 采集与落地状态

`ths-collect.yml`（cron 工作日 CST 09:40 / 15:40，mod5=4 与 shard-collect 错峰）
已两轮验证成功，`data/ths/` 下 101 个文件：

```
data/ths/finance/<code>_{benefit,debt,cash}.json   东财式三大报表 (THS 源)
data/ths/f10/<code>_{worth,holder,...}.json        THS F10 九页
data/ths/kline/<code>/kline_{01,21}.json           THS 日/月K
data/ths/board.json                                板块成分股 + 板块K线
data/ths/news.json                                 THS 7x24
data/ths/f10_em/<code>_*.json                      东财 F10 / 机构 / 研报
data/ths/manifest.json                             汇总
```

**待办**：雪球 screener 需在大陆出口环境跑一次全量（5000 只）。

## 8. 证据分级

| 结论 | 来源 |
|---|---|
| 所有入库源的 http_code/bytes/secs | 主代理本容器 2026-10-16 实测 |
| 字段含义与结构 | 响应体实测 + akshare 源码注释交叉验证 |
| 东财 15 端点可用性 | 子代理 webfetch 探测 + 主代理复测（15/15 通过） |
| 腾讯 sort_type 白名单仅 5 个 | 实测 19 个候选 |
| 雪球 418 是 IP 段风控 | 本机 5 种变体全 200 vs Actions 418 |
| 和讯 DNS 死 | 本机 `getaddrinfo` 失败 |
| 新浪期货 node 白名单窄 | 实测 5 个品种，仅 2 个通 |
| `pn` 字段含义、`volume/turnover/zsz` 单位 | **未核实**，已标注 |

---

# 第三批补充 — 财联社签名突破 + 深交所（2026-10-16 深夜）

## 9. 财联社：签名算法补上 `category` 后打通

**根因**：项目里 2026-10-14 写的 `scripts/cls_sign.py` 签名时**漏了 `category` 参数**
（即使它为空字符串），导致 `cls_cn` 源一直标 blocked、返回 `errno=10012 签名错误`。

正确算法（与旧版同样的双层 hash，只是参数集不同）：

```
所有参数（含空 category）按 key 字母排序
  → 拼接为 key=value&key=value
  → sha1().hexdigest()
  → md5().hexdigest()          # sign
```

默认参数：`app=CailianpressWeb, category='', os=web, rn=50, sv=7.7.5`

### 9.1 实测结论

| 项 | 结论 |
|---|---|
 `v1/roll/get_roll_list` | ✅ 200, 51909B, 53 字段, `errno=0` |
| `rn` 上限 | **50**（60/70/80/99/100/150/200 全部返回 0 条） |
| 分页参数 | **全无效**：`last_time`/`last_id`/`ctime`/`min_time`/`refresh_type`/`page`/`pageNo`/`p` 实测 5 页翻下来都是同样 50 条 —— 只返回最新窗口，无历史回溯 |
| `category` 白名单 | 6 个且**服务端真过滤**：`red`(40 条全 B 级) / `announcement` / `watch` / `hk_us` / `fund`(38 条 C 级) / `remind` |
| `title` 字段 | 恒为空串（电报正文在 `brief`/`content`） |
| `subjects` | **100% 覆盖且带 `plate_id`** —— 可直接映射东财板块，是 `hot_impact` 的优质输入 |
| `stock_list` | 覆盖率低（实测 2/50），不要依赖它做个股关联 |
| `sv` 版本号 | 不敏感（7.7.5 / 8.0.0 / 8.7.9 均可） |

### 9.2 旧端点 `/api/cache?name=telegraphList` 仍可用

2026-10-14 发现的端点复核仍活着，且**免签也返回 200**（`errno=0`, 20 条, 31 字段）。
与 v1 的差异：

| | `/api/cache` | `/v1/roll/get_roll_list` |
|---|---|---|
| 字段数 | 31 | 53 |
| `title` 非空率 | **7/20** | 0/20 |
| 分类筛选 | 无 | 6 类 |
| `lastTime` 分页 | 部分生效（19/20 条，边界重叠 1 条） | 无效 |

→ **两端点互补**：cache 版拿 title，v1 版拿分类 + 富字段。已写入 registry notes。

另：网上多个开源项目用的 `nodeapi/telegraphList` 免签路径现在**全 404**，
`v2/roll/get_roll_list` 返回 `errno=50101`。财联社已把免签入口全关。

### 9.3 采集与落地

`scripts/cls_collect.py`（含修正后的签名），已接进 `ths-collect.yml`。
Actions 第三轮验证：**250 条唯一电报**（7 个分类各 40-50 条），
`subjects` 100% 覆盖、`plate_ids` 68%、level 分布 B5/C45。
落地 `data/ths/cls_telegraph.json`。

## 10. 深交所：`szse api/report` 三个可用报表

registry 里的 `szse_api` 一直标 blocked，实际是入口找错了。
正确路径是 `https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=<id>&TABKEY=tab1&random=<float>`：

| CATALOGID | 名称 | 记录数 |
|---|---|---|
| 1110 | A股列表 | 2906 |
| 1105 | 基金列表 | 1069 |
| 1945 | ETF列表 | 756 |

字段（A股）：`agdm`(代码) / `agjc`(简称) / `bk`(板块) / `agssrq`(上市日期) /
`agzgb`(总股本) / `agltgb`(流通股本) / `sshymc`(证监会行业，如 `J 金融业`)。
ETF 列表**独带 `zxjjjz` 最新净值**。

**两个坑**：
1. **`pageno` 翻页参数不生效** —— 实测 `pageno=1/2/3/100` 全部返回同样的前 20 条
   （平安银行 000001 开头）。只能拿首页 20 只，要全量得另找入口。
2. **简称字段全带 HTML 锚标签**（`agjc`/`jjjcurl`/`kzjcurl`），且 ETF 的字段含多个链接，需正则剥离。

## 11. 第三批 blocked 留档（`dead_third_batch`）

| 站点 | 现象 |
|---|---|
| 富途 | `futunn.com` 5 个 `quote-api`/`news-site-api` 路径全返回 404 SPA 页（10769B） |
| 淘股吧 | `tgb.cn/moreHot` 返回页脚营业执照框架（94KB，无热帖数据）；`api`/`topic` 路径 404 |
| 开盘啦 | `kaipanla.com/api/v1/*` 返回 Nuxt SPA HTML（8.6KB），需登录态 |
| 问财 | `iwencai.com/unifiedwap/v2` 返回 200 但 **0 字节**；`urp/v7` 403 |
| 东财股吧 | `guba.eastmoney.com/interface/GetData.aspx` 200 但 0 字节 |
| 上交所 | `query.sse.com.cn getStockListData` 返回 `success:false`（需 jsonCallBack 精确匹配） |
| 新浪 | `MoneyFlow.ssl_bestsort` 与 `Market_Center.getHQNodeData` 返回 `Service not found` |
| 腾讯 | `rank/hs/getMoneyRankList` 与 `getLimitUpList` 404；`fflow/daykline` 返回 `No dispatch info found` |
| 巨潮 | `web.cninfo.com.cn` **DNS 无法解析**（与和讯同样死） |

新增 ok 源 `sina_hq_node_count`：A 股总数 5575（裸字符串，非 JSON），
可与雪球 screener 的 5000 交叉校验（差 575，口径差异**未核实**）。

## 12. 数据源总数与落地状态

**89 → 152 个源**（ok 108 / degraded 15 / blocked 19 / unauth 8 / untested 2）。

`data/ths/` 共 101 个文件，四类数据：

```
finance/<code>_{benefit,debt,cash}.json   THS 三大报表全科目
f10/<code>_{9页}.json                     THS F10 九页
kline/<code>/kline_{01,21}.json           THS 日/月K + 分时
board.json / news.json                    板块成分股 + 7x24 快讯
f10_em/<code>_*.json                      东财 F10 / 机构 / 研报（43 个文件）
cls_telegraph.json                        财联社 250 条唯一电报（7 分类）
manifest.json                             汇总（files=101, em=43, cls=250）
```

另 `data/xq_screener.json.gz`（674KB）：雪球 5000 只 A 股 × 31 字段选股池。

**仍未跑**：雪球全量需大陆 IP（Actions 出口 418）；全市场 THS 采集未实测耗时。
