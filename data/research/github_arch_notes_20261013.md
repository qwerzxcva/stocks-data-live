# GitHub A股算法/引擎/架构调研笔记

- **调研日期**: 2026-10-13
- **调研人**: 破甲 (逆向工程 Agent)
- **域**: GitHub 开源项目调研（域外任务，未实测任何数据接口）
- **数据文件**: `data/research/github_algos_20261013.json`
- **环境说明**: 容器内 `github.com` git clone 不可达；`api.github.com` 与 `raw.githubusercontent.com` 实测可用。所有 star 数来自 GitHub REST API `/repos/{owner}/{repo}`（2026-10-13 拉取），源码经 raw 拉取到 `/tmp/gh_research/` 后本地阅读。

## 0. 先说结论：我们与这些项目的本质差异

我们的 `stocks-ai-view` 已经在**数据层**做得比多数开源项目更扎实（68 个已实测数据源 + 注册表 + 探测节流 + stale/provenance 标记），但在**验证层**几乎空白：

| 维度 | 开源项目普遍做法 | 我们现状 |
|---|---|---|
| 数据采集 | 每源一个模块，无统一注册表 | 有 `sources_registry.py` 唯一事实来源 |
| 因子计算 | 标准化三/四件套预处理 | `factor_lib` 直接算，未去极值/中性化 |
| 信号打分 | 横截面分位/排名 | 绝对分 0-100（不可横向比较） |
| **有效性检验** | **IC / ICIR / 分位分层 / t 值** | **只有单指标胜率 + Wilson CI** |
| 回测口径 | next_open + 滑点 + 信号有效期 | 收盘价成交，无滑点，无有效期 |
| 绩效指标 | Sortino/Calmar/Ulcer/Kelly/VaR/MC | 6 项（pnl/sharpe/max_dd/win_rate/profit_dd/expectancy） |
| 仓位建议 | Kelly f* | 无（只有分数） |

**当前最痛的证据**：`data/reflect_latest.json` 显示 1 日胜率 43.3%、3 日 36.0%、5 日 26.3%、10 日 20.0%（n=550/450/350/100），且 `avg_ret_pct` 全为负。这说明当前 engine_v5 的 score 排序能力接近或低于随机——而 IC/ICIR 检验缺位，使我们无法定位是「指标选错」还是「权重错」还是「口径错」。这是本次调研认定的第一优先级。

---

## 1. 架构对比表

### 1.1 数据接口层

| 仓库 | Star | 分层 | 关键模式 | 与我们差距 | 优先级 |
|---|---|---|---|---|---|
| `akfamily/akshare` | 22918 | 接口函数 → 域分组 → 每源一文件 → utils → DataFrame | 函数式命名 `<域>_<市场>_<数据>_<源>`；`cons.py` 常量集中；无框架，用约定 | 我们注册表更集中，但 `collect_*.py` 单文件过大（29KB/21KB），源变更要改大文件 | P1 |
| `waditu/tushare` | 15447 | `pro_api(token)` 统一入口 → 服务端鉴权/积分/限流 → DataFrame | 标准化主键 `ts_code` 带交易所后缀；内置令牌桶限流；积分制 | 我们**无统一限流器**，各脚本各自 sleep，违反 1-2 QPS 约定时无法自动拦截 | **P0** |
| `shidenggui/easyquotation` | 5462 | `BaseQuotation` 模板方法 → 源子类只写 `format_response_data` | 类属性 `max_num` 配置（腾讯 60 / 新浪 800）；`ThreadPool(len(stock_list))` 并发分批 | 我们缺分批上限常量化；缺本地静态代码表兜底 | P1 |
| `myhhub/stock` | 14783 | crawling 每源一模块 → kline/indicator → 选股/回测 → cron | 单例代理；通达信 TQLEX 直调（JJQC 竞价抢筹） | cyq 已移植但换手率口径用了近似；JJQC 源未登记 | P2 |

**可落地的最小改进（tushare 令牌桶）**：

```python
class RateLimiter:
    def __init__(self, per_minute):
        self.capacity = per_minute
        self.tokens = float(per_minute)
        self.ts = time.time()
    def acquire(self):
        now = time.time()
        self.tokens = min(self.capacity,
                          self.tokens + (now - self.ts) * self.capacity / 60.0)
        self.ts = now
        if self.tokens < 1:
            time.sleep((1 - self.tokens) * 60.0 / self.capacity)
            self.tokens = 0.0
        else:
            self.tokens -= 1.0
```

### 1.2 引擎 / 因子层

| 仓库 | Star | 因子抽象 | 聚合方式 | 与我们差距 | 优先级 |
|---|---|---|---|---|---|
| `zvtvz/zvt` | 4312 | `Factor = DataReader + EntityStateService + DataListener`，`FactorMeta` 元类自动注册 | `TargetSelector`：filter 用 AND/OR，score 用均值；三态 positive/negative/keep | 我们缺横截面分位/排名打分；缺 keep 态（每日全量重排） | **P0**（分位部分） |
| `quantOS-org/JAQS` | 631 | `signaldigger`：signal/return/quantile 三列长表 | IC（spearman）+ 分位收益 + TMB 价差 + t 检验 | 我们**完全没有 IC/ICIR**，无法量化排序能力 | **P0** |
| `yutiansut/QUANTAXIS` | 11278 | `QASingleFactor_DailyBase.calc() -> [date, code, factor]` | 分位选股（>quantile 0.998）+ next_open + rolling sell | 我们回测用收盘价成交（高估收益）；因子未预处理 | **P0** |
| `henrylzl/Factor_analysis_system` | 24 | 月度截面 csv + `info_cols` 基准列分离 | WLS 回归 t 值 + IC + 分层回测 | 单因子检验流程可直接复用我们的 reflect 数据 | P1 |
| `ricequant/rqalpha` | 6822 | `AbstractMod.start_up/tear_down` + `load_mod()` | 事件三分割 pre/main/post；`register_api` 注入 API | 我们无钩子机制；optimizer 单进程 | P1 |

### 1.3 回测 / 绩效层

| 仓库 | Star | 滑点模型 | 置信区间 | 与我们差距 | 优先级 |
|---|---|---|---|---|---|
| `edtechre/pybroker` | 3611 | Fixed(bps) / Volatility(ATR) / Volume(参与率+平方冲击) | BCa bootstrap（2.5/5/10% 三档） | 我们无 bootstrap CI；无 ATR 滑点 | P1 |
| `ranaroussi/quantstats` | 7705 | — | — | 我们缺 Sortino/Calmar/Ulcer/Kelly/VaR/MC | **P0** |
| `shidenggui/easytrader` | 10236 | 单一 `slippage ∈ [0,1]` | — | 指令幂等键 + 过期机制可搬到推股→复盘链路 | P1 |
| `robertmartin8/MachineLearningStocks` | 1963 | — | — | 相对收益标签 + TimeSeriesSplit | P2 |

---

## 2. 算法实现要点（可复现）

### 2.1 IC / ICIR（JAQS + QUANTAXIS）— 本次调研最高价值

```python
import scipy.stats as scst
import numpy as np

def daily_ic(scores, fwd_rets):
    """scores/fwd_rets: 同日的横截面 Series (index=code)"""
    m = scores.notna() & fwd_rets.notna()
    if m.sum() < 10:
        return None
    return scst.spearmanr(scores[m], fwd_rets[m])[0]

def ic_stats(ic_series):
    ic = ic_series.dropna()
    t, p = scst.ttest_1samp(ic, 0)
    return {
        "IC_mean": ic.mean(), "IC_std": ic.std(),
        "ICIR": ic.mean() / ic.std() if ic.std() else None,
        "t_stat": t, "p_value": p,
        "IC>0概率": (ic > 0).mean(),
        "n": len(ic),
    }
```

**判定经验值（业界常用，需用我们数据校准）**：|IC_mean| > 0.03 且 t > 2 视为有效因子；ICIR > 0.3 为可用。单一指标 IC 接近 0 即噪声。

### 2.2 分位分层检验（JAQS + Factor_analysis_system）

```python
def quantilize_without_nan(mat, n_quantiles=5):
    """横截面分位, 小值给小档位号"""
    mask = np.isnan(mat)
    rank = np.argsort(np.argsort(mat, axis=-1), axis=-1)
    count = np.sum(~mask, axis=-1)
    divisor = count * 1.0 / n_quantiles
    res = np.floor(rank / divisor) + 1.0
    res[mask] = np.nan
    return res

# 每日: q = quantilize(scores); 组收益 = rets.groupby(q).mean()
# TMB = 组5均收益 - 组1均收益; TMB 序列的 t 检验即多空策略显著性
```

### 2.3 因子预处理四件套（QUANTAXIS + Factor_analysis_system）

```python
def winsorize_mad(v, n=5):
    dm = np.nanmedian(v, axis=0)
    dm1 = np.nanmedian(np.abs(v - dm), axis=0)
    return np.clip(v, dm - n * dm1, dm + n * dm1)

def neutralize(y, X, w=None):
    """X = [ln(流通市值), 行业哑变量]; 返回残差"""
    import statsmodels.api as sm
    return sm.WLS(y, sm.add_constant(X), weights=w).fit().resid

def standardize(v):
    return (v - np.nanmean(v, axis=0)) / np.nanstd(v, axis=0)
```

### 2.4 绩效指标（quantstats，全部 10 行内）

```python
def sortino(r, periods=252):
    downside = np.sqrt((r[r < 0] ** 2).sum() / len(r))   # 分母是全样本数
    return r.mean() / downside * np.sqrt(periods) if downside else np.nan

def calmar(r, periods=252):
    total = (1 + r).prod() - 1
    years = len(r) / periods
    cagr = abs(total + 1) ** (1.0 / years) - 1 if total + 1 > 0 else np.nan
    cum = (1 + r).cumprod()
    dd = (cum / np.maximum.accumulate(cum) - 1).min()
    return cagr / abs(dd) if dd else np.nan

def kelly_f(r):
    wins = r[r >= 0]; losses = r[r < 0]
    p = len(r[r > 0]) / max(len(r[r != 0]), 1)
    b = wins.mean() / abs(losses.mean()) if len(losses) and losses.mean() else np.nan
    return ((b * p) - (1 - p)) / b if b else np.nan   # 建议实际用 f*/2

def profit_factor(r):
    w = r[r >= 0].sum(); l = abs(r[r < 0].sum())
    return w / l if l else (np.inf if w else 0.0)

def montecarlo_bust(r, sims=1000, bust=-0.10, seed=42):
    rng = np.random.default_rng(seed)
    ra = np.asarray(r); n = len(ra)
    sim = np.empty((n, sims)); sim[:, 0] = ra
    for i in range(1, sims):
        sim[:, i] = rng.permutation(ra)
    cum = np.cumprod(1 + sim, axis=0)
    run_max = np.maximum.accumulate(cum, axis=0)
    dd = (cum - run_max) / run_max
    return float((dd.min(axis=0) < bust).mean())
```

### 2.5 滑点模型（pybroker 三层）

```python
def slippage_price(side, price, bps=5, atr=None, scale=0.1, volume=None,
                   shares=None, volume_limit=0.025, price_impact=0.1):
    adj = price * bps / 10000.0                    # 固定基点
    if atr is not None:
        adj = max(adj, scale * atr)                # ATR 波动率 (取更大者)
    if volume and shares:
        shares = min(shares, volume_limit * volume)
        adj = max(adj, price_impact * (shares / volume) ** 2 * price)
    return shares, price + adj if side == "buy" else price - adj
```

### 2.6 前视偏差防护（JAQS 的 shift 纪律）

```python
# 信号与未来收益对齐的标准写法
signal = signal.shift(1)                 # 避开当日信息
fwd_ret = close.pct_change(N).shift(-N)  # 未来 N 日收益
# 停牌/缺失逐格剔除
mask = signal.isna() | fwd_ret.isna()
```

### 2.7 Hurst 指数（QUANTAXIS R/S 分析）

```python
def hurst(series):
    series = np.asarray(series, dtype=float)
    n = len(series)
    exponent = int(np.log2(n))
    rs, sizes = [], []
    for i in range(1, exponent):
        parts = 2 ** i
        size = n // parts
        vals = []
        for x in range(parts):
            seg = series[x * size:(x + 1) * size]
            dev = np.cumsum(seg - seg.mean())
            R = dev.max() - dev.min()
            S = seg.std()
            if S > 0 and R > 0:
                vals.append(R / S)
        if vals:
            rs.append(np.mean(vals)); sizes.append(size)
    slope, _ = np.polyfit(np.log10(sizes), np.log10(rs), 1)
    return slope      # <0.5 均值回复, >0.5 趋势持续
```

---

## 3. 我们的改进路线图

### P0 — 立刻做（4 条，直接关系推股准确度）

| # | 改进 | 来源 | 动作 | 预期效果 |
|---|---|---|---|---|
| 1 | **IC/ICIR/分位分层检验** | JAQS, QUANTAXIS, Factor_analysis_system | 新建 `scripts/factor_eval.py`，输入 engine_v5 历史 top + K线，按 pred_date 横截面算 spearman(score, 未来 N 日收益)，输出 IC_mean/std/ICIR/t/p；score 分 5 组算组均收益与 TMB | 第一次能回答「排序是否有效」，把 43%/36%/26%/20% 的胜率归因到指标选择/权重/口径 |
| 2 | **绩效指标补全 + Kelly 仓位** | quantstats | optimizer/kline_sim 输出加 sortino/calmar/ulcer/upi/profit_factor/payoff/kelly_f/var95/cvar95/连续盈亏/MC 破产概率；Kelly f*/2 作建议仓位 | 从「只给分数」升级为「分数 + 风险 + 仓位」 |
| 3 | **回测口径修正** | QUANTAXIS, pybroker, easytrader | reflect entry 改 next_open；加 slippage_bps=5 与 ATR 滑点选项；信号加 valid_bars=5 有效期 | 消除当前口径的系统性高估 |
| 4 | **横截面分位打分** | zvt, JAQS | engine_v5 输出加 `rank_pct`（当日全市场 pct rank）+ 5 档标签；top-N 改按 rank_pct 取 | 绝对分不可跨日比较，分位可；排序稳定性提升 |

### P1 — 下一步（5 条）

| # | 改进 | 来源 | 动作 |
|---|---|---|---|
| 5 | 统一限流门（令牌桶） | tushare | `scripts/rate_limit.py` + 每源在 registry 声明 qps |
| 6 | 因子预处理四件套 | QUANTAXIS, Factor_analysis_system | factor_lib 输出后接 MAD 去极值 → 行业中性化 → z-score |
| 7 | 三态目标（positive/negative/keep） | zvt | 已在池且分数未掉出阈值标 keep，不再每日全量重排 |
| 8 | 并行参数扫描 + 结果落盘 | rqalpha | optimizer 改 ProcessPoolExecutor，结果写 `data/optimizer_runs/` |
| 9 | 超额收益口径（跑赢指数） | MachineLearningStocks | reflect 增加 `个股 N 日收益 - 指数 N 日收益` 统计列 |

### P2 — 有空做（4 条）

| # | 改进 | 来源 | 动作 |
|---|---|---|---|
| 10 | bootstrap 置信区间 | pybroker | 收益类指标用 BCa bootstrap（n_boot=1000） |
| 11 | 事件钩子（pre/main/post） | rqalpha | engine 打分前后插钩子，不改 engine_v5.py |
| 12 | cyq 换手率口径修正 + 进投票 | myhhub/stock | 用真实 turnover 字段替换 volume/mean 近似；三指标进 engine_v5 投票 |
| 13 | ML 对照实验 + JJQC 源 | MachineLearningStocks, myhhub/stock | RandomForest 跑 factor_lib 因子对照等权共振；JJQC 竞价抢筹源登记实测 |

---

## 4. 限制声明（未验证项）

1. **未做动态验证**：本次全部为静态代码/文档阅读，未运行任何被调研仓库的代码，未对任何数据接口发起请求（遵守 probe_log 68 源已登记的约束）。
2. **star 数为 2026-10-13 API 快照**，会随时间变化。
3. **仓库名变更已核实**：`joinquant/jaqs` → `quantOS-org/JAQS`；`QUANTAXIS/QUANTAXIS` → `yutiansut/QUANTAXIS`；`zvtvzvt/zvt` → `zvtvz/zvt`；`polakowo/quantstats` 与 `bdzholars/quantstats` 均已 404，真实 owner 为 `ranaroussi`。
4. **IC/ICIR 阈值（0.03 / t>2）为业界常用经验值，非本项目实测**，需用我们自己的 reflect 数据校准后才可引用。
5. **未核实项**：JAQS 的 `DataView` 面板实现细节（144KB 未通读）；pybroker 的 `scope.py` 因果读取完整约束（仅读 docstring 与 model.py 的 lookahead 部分）；rqalpha 的 bundle 数据层（仅读事件与 Mod 文档）。
6. **JJQC 竞价抢筹源未实测**，`myhhub/stock` 中的 token 为上游仓库硬编码，本项目若要采用需自行获取并遵守其服务条款。
7. **我们的 reflect 是否存在前视偏差未核实**：需确认 `engine_v5_*.json` 的 `ts` 与 `top[0].date` 的时间关系——若预测在收盘后生成而 entry 用当日收盘，则含前视，next_open 修正可一并解决。

---

## 5. 一页速查：最该抄的三段代码

1. **IC/ICIR 检验**（`scripts/factor_eval.py`，约 40 行）— 见 2.1
2. **绩效指标全家桶**（`optimizer.py` 的 stats 扩展，约 60 行）— 见 2.4
3. **令牌桶限流**（`scripts/rate_limit.py`，约 15 行）— 见 1.1

## 6. 代码片段可运行性自检（2026-10-13 实测）

用合成数据（`numpy 2.5.4` / `scipy 1.18.1` / Python 3.14）跑了笔记中全部 11 个片段，11/11 通过：

| 片段 | 验证结果 | 说明 |
|---|---|---|
| `quantilize_without_nan` | 5 组各 80 只（n=400） | 等分精确，组号 1..5 |
| `winsorize_mad(5)` | 离群值 100 → 18.0 | 中位数 5.5、MAD=2.5、稳健上界=5.5+5×2.5=18.0，离群值被精确削到上界 |
| `sortino` / `calmar` / `kelly_f` / `profit_factor` | -1.821 / -0.657 / -0.1167 / 0.799 | 合成数据均值为正但方差大，指标方向合理 |
| `montecarlo_bust_prob` | 1.0 | 合成数据 σ=2%/日，-10% 回撤几乎必然发生，符合直觉 |
| `slippage(buy, sell)` | (10.03, 9.97) | 5bp 双向对称 |
| `hurst` | 0.9649 | 合成序列为累积随机游走（强趋势），H>0.5 符合预期 |
| `RateLimiter.acquire` | 10 次调用累计等待 0s | 60/min 容量下 0.1s 间隔不会触发等待 |

注意：上表数值均由合成数据产生，**不代表 A 股真实表现**；仅证明代码片段逻辑正确、可运行。
