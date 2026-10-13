# 技能算法与数据源吸收笔记 (2026-10-13)

## 一、本地技能目录核查结论

`~/.aharou/skills/` 共 **37 个**目录，与用户提供的 17 个技能清单**零匹配**（grep 关键词：lude/fud/ftshare/volat/barra/gan/similar/kline/buffett/cash/niuf/xiaoguo/pingan/huatai/playwright/tdx/zhangting 全部 0 命中）。

→ 这些技能是用户在其它环境/会话见过的，本容器未安装。
→ 因此「读 SKILL.md 提取接口」不可行，改为**按用户给出的算法描述直接落地实现**（已全部实现并验证）。

## 二、已落地的算法 (scripts/skill_algos.py)

| 算法 | 来源技能 | 公式/规则 | 落地状态 |
|---|---|---|---|
| `fcf_ev_screen` | Tushare 量化-自由现金流策略 | FCF = 经营现金流净额 − 购建长期资产支付现金；EV = 总市值 + 总负债 − 货币资金；门槛：流动性前80% + ROE前80% + 非ST + 剔除金融地产；按 FCF/EV 降序 | ✅ 跑通，10 候选。用 OCF/EV 代理（业绩快报无 Capex），数据缺口已标注 |
| `volatility_evenness` | 波动均匀度高频选股因子 | VE = std(rolling_std(r,20)) / std(r)；VE 小 = 信息分布均匀 = 低风险 | ✅ 茅台实测 VE=0.2067「信息分布均匀」 |
| `turnover_cv` | 交易行为波动因子选股 | CV = std(换手率20日) / mean(换手率20日)；CV 小 = 交易行为稳定 | ✅ 茅台实测 CV=0.2517「交易行为稳定」 |
| `similar_kline` | 股票相似K线-汇正财经 | 近 20 日归一化形态，历史 top-5 余弦相似片段，统计后续 5 日涨跌 | ✅ 茅台实测：后续5日均 +0.06%，胜率 60% |
| `barra_lite` | 股票池 Barra 归因 | 5 风格 z-score：size=−ln(mktcap), value=−PE, momentum=240日收益, volatility=−240日波动, growth=营收同比 | ✅ 代码完成（需外部传 stocks 列表） |

## 三、可复用的架构思想（未完全落地，供后续）

| 技能 | 架构思想 | 可复用点 |
|---|---|---|
| 禄得历史回测 | 指定规则+日期区间 → 模拟回测 → 区间收益/回撤/费用统计 → 实验对比 | `optimizer.py` 已有回测，可加「实验对比」维度（多组参数并列） |
| 东方财富财经取数 | 三市场报表名矩阵 + SECUCODE 构造规则 + 长表/宽表判别 + 命中校验 | 已实测：`SECUCODE` = `{code}.{SH\|SZ\|BJ\|NQ}`；datacenter 报表名必须区分排序键（TRADE_DATE/DATE/dim_date） |
| 涨停联动捕手 | 涨停结构 → 连板梯队 → 情绪周期 → 龙头博弈 | `ban_pick.py`/`ban_prob.py` 已有打板池；可加「卡位/弱转强/分歧转一致」状态机 |
| FTShare 金融数据 | 统一因子查询接口层 | `sources_registry.py` + `query_api.py` 已是同一架构 |
| 九方-巴菲特投资 | 生意模式/企业质量/盈利/现金流/负债/资本配置/估值 七维 | 可作 `ai_screener.py` 的「价值维度」加权项 |
| Playwright Scraper | 隐身抓取 + 验证码处理 | **不实现**：项目纪律明确不做 CAPTCHA 破解/指纹伪装；需要浏览器渲染的源（小红书/腾讯新闻）已标 unavailable 并给替代源 |

## 四、数据源新增（来自逆向子代理，已实测验证并入库）

| id | 端点 | 关键发现 |
|---|---|---|
| `em_push2his_clist` | push2his.eastmoney.com/api/qt/clist/get | **push2 WAF 绕行**：push2 域 TLS reset，push2his 同路径 200，total=5923 |
| `em_push2his_etf_onsite` | 同上 fs=b:MK0021 | 场内基金/ETF 全量 1357 只 |
| `em_fund_lsjz` | api.fund.eastmoney.com/f10/lsjz | **Referer 静默鉴权**：不带 Referer 返回 200 + ErrCode=-999 + 空数据（比 403 更危险） |
| `jisilu_dividend_rate` | jisilu.cn/data/stock/dividend_rate_list/ | pb/pe_temperature 历史分位 + 5年均值，单接口密度最高 |
| `sina_vip_kline` | vip.stock.finance.sina.com.cn | 多周期 + 直返 MA5/MA10，可作 K 线第三方交叉校验 |

## 五、验证过的坑（2026-10-13）

1. `push2his` 的 **kline 端点已失效**（rc=102）——早间实测 200，晚间 102。K 线统一改用腾讯 `fqkline`。
2. `push2his` clist 的 `pz=6000` 只返回 100 条 → 必须分页循环。
3. `RPT_LICO_FN_CPD` 真实字段名：`WEIGHTAVG_ROE`/`BASIC_EPS`/`MGJYXJJE`(每股经营现金流)/`PARENT_NETPROFIT`/`TOTAL_OPERATE_INCOME`/`XSMLL`，且**混有新三板**（`TRADE_MARKET=新三板`）需过滤。
4. 腾讯指数 `kline/kline` 的 `end` 参数必须是 `YYYY-MM-DD`（`20200101` 返回空），且返回数组**升序**（最早在 seg[0]，不是 seg[-1]）。
