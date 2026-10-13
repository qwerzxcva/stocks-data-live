# 技能数据源与算法吸收笔记（2026-10-13）

**调查人**：subagent 破甲
**环境**：Alpine aarch64 Docker 容器，零凭据，无代理，容器 NAT 出口 IP
**配套 JSON**：`skill_sources_20261013.json`（结构化，含可复现 curl/python）

---

## 0. 前置结论：17 个技能在本地均未以该名字存在

对两个技能目录做了全量列举：

| 目录 | 数量 | 与清单 17 个的匹配 |
|---|---|---|
| `~/.aharou/skills/` | 37 | **0 个** |
| `~/workspace/.aharou/skills/` | 45 | **0 个** |

本地真正存在的是另一批股票技能：`a-stock-data`、`a-share-data`、`deep-analysis`、`lhb-analyzer`、`buffett-value-investing`、`theme-detector`、`hot-theme-scanner`、`concept-stock-mapper`、`simons-factor-quant`、`Geek-skills-a-share-analyst` 等。

因此调查分三条腿走：

1. **本地同源技能全文读**：`a-stock-data/SKILL.md`（V3.2.2，2095 行，27 个端点）逐段读完，这是「东方财富财经取数」的等价实现。
2. **websearch 取公开文档**：FTShare MCP、中证 932365 编制方案、Barra CNE6、UID 因子研报、Gangtise MCP、KlineShare、Playwright skill。
3. **容器内端点实测**：温和限频，每源 1-2 QPS。

> `found: false` 的准确含义是「按该技能名未在本地目录找到」，**不代表能力不存在**。

---

## 1. 本地技能目录全清单（备查）

```
~/.aharou/skills/ (37):
LQF_Machine_Learning_Expert_Guide, adr-create, adr-index, adr-reindex, aeon, aif-ci,
android-project-generator, api-gateway, autopilot-predict, brainstorming, capability-evolver,
caveman, clean-architecture, code-complete, code-maestro, content-ops,
designing-data-intensive-applications, golang-testing, kotlin, llm-sampling-tuner,
matt__code-review, matt__diagnosing-bugs, matt__domain-modeling, matt__implement,
matt__improve-codebase-architecture, matt__prototype, matt__research, matt__retro,
matt__tdd, matt__teach, matt__to-spec, matt__triage, nested-subagents, rust,
subagent-orchestration, supermemory, task-observer

~/workspace/.aharou/skills/ (45):
Geek-skills-a-share-analyst, Geralt-L__Stock-Analysis-3D, a-share-data, a-share-paper-trading,
a-stock-data, aesop-three-questions, bogle-index-investing, buffett-value-investing,
business-picker, compounding-thinking, concept-stock-mapper, cruisekkk__trading-ledger,
dalio-all-weather, deep-analysis, downtrend-duration-analyzer, earnings-tracker,
fadewalk__serenity-stock-choke, fear-and-greed, framework-backtest, futuapi,
gh-stock-deep-analysis, graham-defensive-investing, hold-forever, hot-theme-scanner,
howard-marks-cycle, investor-panel, lhb-analyzer, livermore-trend-trading,
macd-second-golden-cross, macd-trend-resonance-stock-picker, macro-regime-detector,
market-top-detector, master-ensemble, mr-market, oneil-canslim, real-conservatism,
research-report-review, simons-factor-quant, technical-pattern-recognition, theme-detector,
three-asset-categories, trap-detector, tuige-shortline-trading
```

---

## 2. 东财财经取数：三市场报表名矩阵 + SECUCODE + 长宽表判别

对应技能：**东方财富财经取数**（本地等价 `a-stock-data` V3.2.2）。

### 2.1 SECUCODE 与 secid 构造

```python
def secucode(code):
    """6 位代码 → 带市场后缀的证券代码"""
    if code.startswith(('6', '9', '5')): return f'{code}.SH'   # 沪市主板/科创/ETF
    if code.startswith(('8', '4')):     return f'{code}.BJ'   # 北交所
    return f'{code}.SZ'                                       # 深市主板/创业板

def secid(code):
    """东财 secid：1=沪 0=深 90=板块 116=港股"""
    return ('1.' if code.startswith(('6', '9', '5')) else '0.') + code
```

港股 5 位 → `.HK`；美股 → `.US`。

### 2.2 三市场报表名矩阵

同一域名 `https://datacenter-web.eastmoney.com/api/data/v1/get`，只切换 `reportName`：

| 市场 | 报表名系列 | filter 字段名 |
|---|---|---|
| A 股 | `RPT_DAILYBILLBOARD_DETAILSNEW`（龙虎榜）、`RPT_DATA_BLOCKTRADE`（大宗）、`RPTA_WEB_RZRQ_GGMX`（两融明细）、`RPTA_RZRQ_LSHJ`（两融汇总）、`RPT_MUTUAL_DEAL_HISTORY`（陆股通）、`RPT_LICO_FN_CPD`（业绩快报）、`RPT_HOLDERNUMLATEST`（股东户数）、`RPT_SHAREBONUS_DET`（分红）、`RPT_LIFT_STAGE`（解禁） | `SECURITY_CODE` |
| 港股 | `RPT_HKF10_*` | `HKSECODE` |
| 美股 | `RPT_USF10_*` | `SECCODE` |

### 2.3 长表-宽表判别与命中校验红线

```python
def dc_query(report, flt='', page=50, sort='TRADE_DATE', order='-1'):
    """东财数据中心统一查询。
    返回 result.data 为 list → 宽表（一行一标的，字段全集）。
    若字段稀疏且成对出现 METRIC_NAME/VALUE → 长表，需按 (SECUCODE, METRIC_NAME) pivot。"""
    r = requests.get(
        'https://datacenter-web.eastmoney.com/api/data/v1/get',
        params={'reportName': report, 'columns': 'ALL', 'filter': flt,
                'pageNumber': 1, 'pageSize': page,
                'sortColumns': sort, 'sortTypes': order,
                'source': 'WEB', 'client': 'WEB'},
        timeout=15).json()
    # 红线：code != 0 或 result == null 一律判未命中；空列表 != 有数据
    if r.get('code') != 0 or not r.get('result'):
        return []
    return r['result']['data']
```

三条红线：

1. `code != 0` 或 `result == null` → 未命中，**不得把空列表当数据**。
2. 日期 filter 必须用 `TRADE_DATE='YYYY-MM-DD'` **短横格式**。
3. 排序键各报表不同：`TRADE_DATE` / `DATE` / `dim_date`，需逐个确认。

### 2.4 容器内实测记录（9 个端点 200）

| 端点 | HTTP | 实测样本 |
|---|---|---|
| `datacenter-web/api/data/v1/get` (RPT_HOLDERNUMLATEST) | 200 | `HOLDER_NUM=296404, RATIO=21.897, END_DATE=2026-06-30` |
| `datacenter-web` (RPT_SHAREBONUS_DET) | 200 | 14 页；`PRETAX_BONUS_RMB=280.2423, EX_DIVIDEND_DATE=2026-06-26` |
| `datacenter-web` (RPTA_WEB_RZRQ_GGMX) | 200 | 1998 页；`RZYE=17000155431, RQYE=264230624` |
| `reportapi.eastmoney.com/report/list` | 200 | `hits=69`；`infoCode=AP202610061830166304` |
| `quotes.sina.cn/.../getFinanceReport2022` | 200 | `report_count=99`，3 期 report_list |
| `search-api-web.eastmoney.com/search/jsonp` | 200 | `hitsTotal=415` |
| `np-weblist.eastmoney.com/.../getFastNewsList` | 200 | `total=5000` |
| `basic.10jqka.com.cn/new/688017/worth.html` | 200 | 32 table，命中一致预期 EPS 表 |
| `qt.gtimg.cn/q=sh600519` | 200 | GBK，`vals[44]=15937.17`（总市值亿） |

降级/未验证：

- `cninfo.com.cn/new/hisAnnunt/query` → 200 但 `totalAnnouncement=0`（容器出口被降权）。
- `mootdx` TCP 7709 → socket 可连（3 个服务器 OPEN），但裸协议首包被 reset，且 mootdx/pytdx **均未安装**，标 unverified。

---

## 3. Tushare 自由现金流策略（中证全指自由现金流指数 932365）

### 3.1 权威口径

中证指数官方编制方案（`932365_Index_Methodology_cn.pdf`，V1.0 2024-12）：

- 样本空间：同中证全指
- 可投资性筛选：过去一年日均成交金额排名位于样本空间**前 80%**
- 选样四条件 + 排序取前 100

### 3.2 公式

```
FCF  = 过去一年经营活动产生的现金流量净额 − 过去一年购建固定资产、无形资产和其他长期资产支付的现金
EV   = 公司总市值 + 总负债 − 货币资金
FCF率 = FCF / EV

盈利质量 = (过去一年经营活动现金流量净额 − 过去一年营业利润) / 总资产
```

四门槛：

1. 按中证一级行业分类，**不属于金融或地产**；
2. **FCF > 0 且 EV > 0**；
3. **连续 5 年经营活动产生的现金流量净额为正**；
4. 盈利质量由高到低排名位于样本空间**前 80%**。

（技能描述中的「非 ST」来自国证/富时同族指数的样本空间规则，中证方案里体现在样本空间本身。）

### 3.3 可落地实现

```python
def fcf_ev_screen(rows):
    out = []
    for r in rows:
        if r['is_st'] or r['industry_l1'] in ('金融', '房地产'):
            continue
        fcf = r['n_cashflow_act'] - r['c_pay_acq_const_fiolta']
        ev  = r['total_mv'] + r['total_liab'] - r['money_cap']
        if fcf <= 0 or ev <= 0:
            continue
        if not all(x > 0 for x in r['n_cashflow_act_5y']):   # 连续 5 年为正
            continue
        q = (r['n_cashflow_act'] - r['oper_profit']) / r['total_assets']
        out.append(dict(r, fcf=fcf, ev=ev, fcf_ev=fcf / ev, quality=q))

    k = max(1, int(0.8 * len(out)))
    liq  = sorted(out, key=lambda x: -x['avg_amt_1y'])[:k]   # 流动性前 80%
    qual = {id(x) for x in sorted(out, key=lambda x: -x['quality'])[:k]}
    kept = [x for x in liq if id(x) in qual]                 # 盈利质量前 80%
    return sorted(kept, key=lambda x: -x['fcf_ev'])[:100]    # FCF率降序取 100
```

### 3.4 免 token 替代数据链（已实测跑通）

不需要 Tushare token 也能算同一组指标：

```python
import akshare as ak, requests

# 经营现金流净额 / 购建长期资产支付现金 → 新浪现金流量表
llb = requests.get(
    'https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022',
    params={'paperCode': 'sh600519', 'source': 'llb', 'type': '0', 'page': '1', 'num': '8'},
    timeout=15).json()['result']['data']['report_list']

# 总市值 → 腾讯行情字段 44（单位：亿）
t = requests.get('https://qt.gtimg.cn/q=sh600519',
                 headers={'User-Agent': 'Mozilla/5.0'}, timeout=10).content.decode('gbk')
total_mv_yi = float(t.split('"')[1].split('~')[44])

# 辅助验证 → akshare 个股资金流（实测 121 行）
flow = ak.stock_individual_fund_flow(stock='600519', market='sh')
```

---

## 4. 波动均匀度因子（波动率的波动率 / 信息分布均匀度 UID）

### 4.1 来源研报

- 《信息分布均匀度，基于高频波动率的选股因子》（方正证券）
- 《波动率的波动率与投资者模糊性厌恶》（方正证券 2022-08，引用 Kostopoulos 2021）

### 4.2 分钟级公式

```
剔除开盘与收盘分钟
r_t    = close_t / close_{t-1} − 1                      # 分钟收益率
vol_t  = std(r_{t-4}, r_{t-3}, r_{t-2}, r_{t-1}, r_t)   # 第 t 分钟波动率
amb_t  = std(vol_{t-4} ... vol_t)                       # 第 t 分钟模糊性
日因子  = mean(amb_t)   或   UID = mean(amb) / std(r)
```

前 9 分钟为空（5 分钟算 vol + 5 分钟算 amb）。

### 4.3 实现

```python
import numpy as np, pandas as pd

def ambiguity_series(close_min):
    r   = np.diff(close_min) / close_min[:-1]
    vol = pd.Series(r).rolling(5).std().values
    amb = pd.Series(vol).rolling(5).std().values
    return amb[9:]                       # 前 9 分钟为空

def uid_factor(close_min):
    amb = ambiguity_series(close_min)
    vol = np.nanstd(np.diff(close_min) / close_min[:-1])
    return np.nanmean(amb) / vol if vol else np.nan
```

### 4.4 日频代理版（零额外成本，可立即进因子库）

```python
def vol_evenness_daily(close):
    """VE = std(rolling_std(r,20)) / std(r)；VE 小 = 波动率本身稳定 = 信息分布均匀"""
    r    = close.pct_change().dropna()
    roll = r.rolling(20).std()
    return roll.std() / r.std()
```

实测茅台 `VE ≈ 0.2067`。

### 4.5 因子有效性诊断

```
RankIC_t = spearman(factor_t, ret_{t+1})
ICIR     = mean(IC) / std(IC)
分组      = 按因子分 10 组统计各组下期收益，检查单调性
判据      = |IC 均值| > 0.05 有效，> 0.1 显著
```

```python
from scipy.stats import spearmanr

def rank_ic(f, nxt):
    return spearmanr(f, nxt).statistic

def icir(ics):
    a = np.array(ics)
    return a.mean() / a.std(ddof=1)
```

---

## 5. 相似 K 线匹配

### 5.1 相关系数法（同花顺 SuperMind 口径）

```
相似度 K = (corr(开) + corr(收) + corr(低) + corr(高)) / 4
窗口      = 60 根日 K
K ∈ [−1, 1]，越接近 1 越相似
```

对历史所有等长片段算 K，取 Top-N，统计其后 1/5/10 日实际涨跌分布。

### 5.2 归一化余弦法（本地已实测）

```python
import numpy as np

def cos(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))

def similar_kline(close, win=20, topk=5, fwd=5):
    q    = close[-win:] / close[-win]              # 查询段归一化
    best = []
    for i in range(len(close) - win - fwd):
        seg = close[i:i + win] / close[i]
        best.append((cos(q, seg), i + win))
    best.sort(reverse=True)
    fwd_rets = [close[j + fwd] / close[j] - 1 for _, j in best[:topk]]
    return {'mean': float(np.mean(fwd_rets)),
            'win_rate': float(np.mean([r > 0 for r in fwd_rets]))}
```

茅台实测：后续 5 日均 **+0.06%**，胜率 **60%**。

### 5.3 DTW 变体（吸收时间轴错位）

```python
def dtw(x, y):
    n, m = len(x), len(y)
    D = np.full((n + 1, m + 1), np.inf); D[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = abs(x[i-1] - y[j-1]) + min(D[i-1, j], D[i, j-1], D[i-1, j-1])
    return D[n, m]
```

> 注意：历史匹配天然过拟合，「后续涨跌」只能作方向旁证，不能单独作买入依据。

---

## 6. Barra 多因子归因

### 6.1 模型形式

```
r_j = Σ_k x_jk · f_k + u_j                    # 个股收益分解
Σ   = X · F · Xᵀ + Δ                          # 结构化协方差
σ_P = sqrt(wᵀ (X F Xᵀ + Δ) w)                 # 组合风险
```

- `X`：(N×K) 因子暴露（行业 one-hot + 风格因子）
- `F`：(K×K) 因子协方差，EWMA + PSD 修正
- `Δ`：(N×N) 对角特异风险
- 因子收益用**逐日截面 WLS**（权重 ∝ √市值）估计

### 6.2 实现

```python
import numpy as np

def barra_risk(returns, X):
    T, N = returns.shape
    K = X.shape[1]
    F = np.zeros((K, K))
    resid = np.zeros_like(returns)
    for t in range(T):
        s = returns[t].std()
        W = np.diag(1 / s**2 if s else 1)
        XtWX = X.T @ W @ X
        f = np.linalg.solve(XtWX, X.T @ W @ returns[t])
        F += XtWX
        resid[t] = returns[t] - X @ f
    Fc = F / T
    Delta = np.diag(resid.var(0))
    return X @ Fc @ X.T + Delta, Fc, Delta
```

### 6.3 Euler / CCTR 风险贡献

```python
def factor_risk_share(w, X, F, Delta):
    Sigma = X @ F @ X.T + Delta
    var = w @ Sigma @ w
    fw = F @ (X.T @ w)
    contrib = (X.T @ w) * fw          # 每因子方差贡献
    return contrib / var, var
```

各因子 `%var` 之和 = 因子风险占比，剩余为特异风险占比。

### 6.4 CNE-6 关键风格因子定义

| 因子 | 计算方法 |
|---|---|
| LNCAP | 流通市值的自然对数 |
| HBETA | 收益率对沪深 300 时序回归，窗口 252 交易日，半衰期 63 |
| HSIGMA | 上述回归的残差波动率 |
| DASTD | 日收益率过去 252 日波动，半衰期 42 |
| CMRA | 累积对数收益（每月 21 交易日） |
| MIDCAP | Size 暴露立方后对 Size 正交，去极值标准化 |

### 6.5 Barra-lite 五风格（本地简化版，零依赖）

```python
def barra_lite(df):
    z = lambda s: (s - s.mean()) / (s.std() + 1e-12)
    return pd.DataFrame({
        'size':       z(-np.log(df['mcap'])),
        'value':      z(-df['pe']),
        'momentum':   z(df['ret_240d']),
        'volatility': z(-df['vol_240d']),
        'growth':     z(df['rev_yoy']),
    }).fillna(0)
```

回看 240 天（≈1 年交易日），与本地周期池口径一致。

### 6.6 中性化

```python
def neutralize(factor, ind_dummies, styles):
    """因子值对行业哑变量 + 风格因子做截面回归，取残差"""
    Z = np.column_stack([ind_dummies, styles])
    beta, *_ = np.linalg.lstsq(Z, factor, rcond=None)
    return factor - Z @ beta
```

---

## 7. 涨停联动捕手：连板梯队 + 情绪周期

### 7.1 数据源（均零鉴权，实测可用）

```bash
# 涨停/跌停池（akshare 底层即 push2ex）
python3 -c "import akshare as ak; print(len(ak.stock_zt_pool_em(date='20261013')))"        # 67
python3 -c "import akshare as ak; print(len(ak.stock_zt_pool_previous_em(date='20261012')))" # 69

# 同花顺当日强势股 + 题材归因 reason tags
curl -sS 'http://zx.10jqka.com.cn/event/api/getharden/date/2026-10-13/orderby/date/orderway/desc/charset/GBK/' -H 'User-Agent: Mozilla/5.0'
```

`reason` 字段是人工运营的题材标签（如「预重整+氨回收+环保设备」），是板块归因的稀缺信号。

### 7.2 连板梯队与晋级率

```python
from collections import Counter

def ladder(zt_df):
    return dict(sorted(Counter(zt_df['连板数']).items()))

def promo_rate(zt_today, zt_yesterday):
    """晋级率 = 今日连板数>1 的股票数 / 昨日涨停股票数"""
    y = set(zt_yesterday['代码'])
    cont = len(zt_today[zt_today['连板数'] > 1])
    return cont / max(1, len(y))
```

### 7.3 短线情绪周期定位

| 指标 | 强 | 弱 |
|---|---|---|
| 涨停家数 | > 60 | < 30 |
| 连板高度 | ≥ 5 板 | ≤ 2 板 |
| 炸板率 | < 30% | > 50% |
| 昨日涨停溢价 | 高开高走 | 高开低走 |

```python
def emotion_stage(n_zt, max_lb, zhaban_rate, premium):
    if n_zt < 30 and max_lb <= 2:
        return '冰点'
    if zhaban_rate < 0.3 and max_lb >= 5:
        return '主升/高潮'
    if zhaban_rate > 0.5:
        return '退潮'
    return '发酵/分歧'
```

阶段序列：**冰点 → 发酵 → 高潮 → 分歧 → 退潮**。

### 7.4 龙头辨识度排序

```python
def leadership(lhb_df):
    g = (lhb_df.groupby(['SECURITY_CODE', 'SECURITY_NAME_ABBR'])
         .agg(times=('TRADE_DATE', 'count'), cum=('CHANGE_RATE', 'sum'))
         .reset_index())
    return g.sort_values(['times', 'cum'], ascending=False)
```

---

## 8. FTShare 金融数据（覆盖面最广的单一源）

### 8.1 端点与鉴权

```
https://market.ft.tech/gateway/mcp        # MCP Streamable HTTP
鉴权：FTSHARE_API_KEY header
```

### 8.2 调用范式（三步握手）

```python
import requests, json

S = 'https://market.ft.tech/gateway/mcp'

# 1) initialize → 拿 Mcp-Session-Id
r = requests.post(S, json={
    'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
    'params': {'protocolVersion': '2025-11-25', 'capabilities': {},
               'clientInfo': {'name': 'probe', 'version': '1'}}},
    headers={'Accept': 'application/json, text/event-stream'}, timeout=60)
sid = r.headers['Mcp-Session-Id']

# 2) tools/list（实测返回 248 个 ft_* 工具）
t = requests.post(S, json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                  headers={'Mcp-Session-Id': sid,
                           'MCP-Protocol-Version': '2025-11-25',
                           'Accept': 'application/json, text/event-stream'}, timeout=60).text
tools = json.loads(t.split('data: ', 2)[2].strip())['result']['tools']

# 3) tools/call
def mcp_call(name, args):
    return requests.post(S, json={'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                                  'params': {'name': name, 'arguments': args}},
                         headers={'Mcp-Session-Id': sid,
                                  'MCP-Protocol-Version': '2025-11-25',
                                  'Accept': 'application/json, text/event-stream'},
                         timeout=60).text
```

### 8.3 工具路由（248 个）

| 前缀 | 定位 | 代表工具 |
|---|---|---|
| `ft_v1_*` | 基础版 | `stock_candlesticks` / `stock_fund_flow` / `limit_list` / `ths_hot_list` / `northbound` / `eastmoney_*` |
| `ft_v2_*` | 批量/分钟版 | `stock_minutes` / `stock_candlesticks_batch` / `etf_minutes` |
| `ft_v3_*` | **特色因子** | `ashare_news_sentiment_factors` / `kline_pattern_annotations` / `limit_up_reports_briefs` / `supply_chain_*` |
| `ft_v4_*` | 实时日K/分钟K | `stock_realtime_day_kline` / `futures_minutes_realtime` |

### 8.4 匿名额度限制（实测）

```
initialize    → 200
tools/list    → 200，248 个工具
tools/call    → 429 UPSTREAM_UNAVAILABLE
               「最近 1 天最多访问 500 次；请等待 11 小时 4 分钟后再试」
```

→ 需 `FTSHARE_API_KEY` 才能实际取数。248 个工具的完整索引（name/title/params）已存 `/tmp/skill_probe/ft_tools_index.json`。

**这是本次调查中覆盖面最广的单一源**，独有：港股、美股、期货、供应链、千股千评、新闻情绪因子。

---

## 9. 其余技能的算法落地

### 9.1 换手率变异系数 CV（交易行为波动因子）

```
CV = std(换手率_20日) / mean(换手率_20日)
CV 小 = 交易行为稳定 = 筹码结构健康
CV 大 = 情绪化交易
```

```python
import numpy as np

def turnover_cv(t20):
    a = np.asarray(t20, dtype=float)
    return a.std(ddof=1) / a.mean() if a.mean() else np.nan
```

实测茅台 `CV ≈ 0.2517`。配合研报二次过滤：

```python
def screen(df, cv_col='turnover_cv', pct=0.3, min_reports=3):
    k = int(len(df) * pct)
    s = df.sort_values(cv_col).head(k)
    return s[s['report_count'] >= min_reports]
```

### 9.2 巴菲特七维检查清单（九方-巴菲特）

本地等价技能：`~/workspace/.aharou/skills/buffett-value-investing/SKILL.md`（38KB）。

| 维度 | 量化判据 |
|---|---|
| 生意模式 | 毛利率稳定 + ROE 持续 |
| 企业质量 | ROE 5 年均值 > 15% |
| 盈利 | 净利润 5 年 CAGR > 0 |
| 现金流 | 经营现金流/净利润 > 1 持续 |
| 负债 | 有息负债/EBITDA < 3 |
| 资本配置 | ROIC > WACC |
| 估值 | 股东盈余折现，安全边际 > 30% |

```python
def buffett_checklist(f):
    return {'roe_5y_ok':    np.mean(f['roe_5y']) > 15,
            'cash_conv_ok': np.mean(f['ocf_to_np']) > 1.0,
            'leverage_ok':  f['net_debt_ebitda'] < 3,
            'roic_ok':      f['roic'] > f['wacc']}

def owner_earnings(ni, dep, maint_capex):
    return ni + dep - maint_capex

def margin_of_safety(iv, price):
    return (iv - price) / iv
```

### 9.3 自选股批量体检（Gangtise stockpool 通道）

```python
def health_score(pe_pct, roe, rev_g, net_g, main_net):
    """估值分位 30% + 财务质量 25% + 成长 25% + 资金面 20%"""
    return (0.30 * (100 - pe_pct)
          + 0.25 * min(100, roe * 4)
          + 0.25 * min(100, (rev_g + net_g) / 2 * 5)
          + 0.20 * (50 + np.sign(main_net) * min(50, abs(main_net) / 1e6)))

def pct_rank(series, current):
    return float((series < current).sum()) / len(series) * 100
```

Gangtise 通道需 OpenAPI 账号（`gangtise-mcp`，50+ 工具）。

### 9.4 通用回测口径（禄得历史回测）

```python
def backtest(signals, prices, fee=0.0003, init=1e6):
    pos = 0; cash = init
    for d, s in enumerate(signals):
        if s > 0 and pos == 0:
            pos = cash / prices[d] * (1 - fee); cash = 0
        elif s <= 0 and pos > 0:
            cash = pos * prices[d] * (1 - fee); pos = 0
    return (cash or pos * prices[-1]) / init - 1

def max_dd(nav):
    nav = np.asarray(nav); peak = np.maximum.accumulate(nav)
    return float(((peak - nav) / peak).max())

def sharpe(r, rf=0.0):
    a = np.asarray(r)
    return float((a.mean() - rf) / (a.std(ddof=1) + 1e-12) * np.sqrt(252))
```

### 9.5 人气分（牛股王/平安股友圈的共性抽象）

```python
def popularity_score(clicks, recency_decay=0.9):
    """clicks: [(ts, n)]"""
    import time
    now = time.time()
    return sum(n * recency_decay ** ((now - ts) / 86400) for ts, n in clicks)

def hot_holdings(posts):
    from collections import Counter
    c = Counter(s for p in posts for s in p.get('stocks', []))
    return c.most_common(20)
```

---

## 10. Playwright Scraper：能力矩阵（仅作工具选型记录）

| 目标反爬强度 | 方法 | Discuss.com.hk 实测成功率 |
|---|---|---|
| Low（普通站） | `web_fetch` | 0% |
| Medium（动态 JS） | `playwright-simple.js` | 20% |
| High（Cloudflare） | `playwright-stealth.js` | **100%** |

```bash
npm install && npx playwright install chromium
node scripts/playwright-simple.js <url>       # 动态站
node scripts/playwright-stealth.js <url>      # Cloudflare 站
```

**按任务约束，不做 CAPTCHA 破解、指纹伪装、代理池轮换**；本地已有等价方案，仅作兜底。

---

## 11. 复用价值排序（对 stocks-ai-view 引擎）

| 排名 | 技能/算法 | 落地目标 | 理由 |
|---|---|---|---|
| 1 | **涨停联动捕手**（连板梯队+情绪周期） | 周期池 | 两个数据源零鉴权实测可用；周期池的核心量化口径直接补齐 |
| 2 | **FTShare ft_v3 特色因子** | 推股 + 周期池 | 唯一能补足港股/美股/期货/供应链/新闻情绪的通道；需申请 API Key |
| 3 | **Tushare FCF/EV 五门槛** | 推股 + 周期池 | 现成价值因子；已定位免 token 替代数据链 |
| 4 | **东财财经取数**（datacenter 9 报表） | 推股 | 与本地 a-stock-data 重合，9 端点实测 200，可直接并入 sources_registry |
| 5 | **Barra 归因**（240 日） | 板块分析 | 开源实现可直接跑；回看窗口与周期池一致 |
| 6 | **波动均匀度 UID / 日频 VE** | 推股 | 日频 VE 零成本立即可进因子库；分钟级版仅对候选池跑 |
| 7 | **换手率 CV** | 推股 | 零依赖，茅台实测 0.2517 |
| 8 | **相似 K 线** | 推股 | 算法可落地；注意历史匹配过拟合 |
| 9 | **巴菲特七维** | 推股 | 本地已有技能；可作 ai_screener 价值维度加权项 |
| 10 | Playwright Scraper / 牛股王 / 平安股友圈 / 小果 / 禄得 / 华泰 | — | 无公开接口或需登录态/付费，仅记录 |

---

## 12. 限制声明（未验证项）

1. **mootdx / pytdx 未安装**，TCP 7709 仅完成 socket 连通测试，未完成协议级握手，`unverified`。
2. **Tushare Pro 无 token**，`unverified`；已用免 token 链替代。
3. **FTShare tools/call 触达匿名日额度 429**，248 个工具仅枚举未逐一调用，`degraded`。
4. **Gangtise / KlineShare / 猫爪数据 均需账号或 key**，`unverified`。
5. **巨潮 cninfo** 容器内 200 但返回空（IP 降权），`degraded`。
6. **东财 push2 全系**在本容器 TLS reset（与已知一致），涨跌停池走 `push2ex` / akshare 路径。
7. 本地 17 个技能名**零匹配**，本报告的能力还原依赖「本地同源技能 + 公开文档」推断，非原技能原文。
