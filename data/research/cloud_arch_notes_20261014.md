# 云架构调研 + 分钟级方案（2026-10-14）

## 一、三个项目的可借鉴点（子代理调研 + 我的核实）

| 项目 | stars | 结论 | 落地动作 |
|---|---|---|---|
| **UFund-Me/Qbot** | 18633 | 事件驱动四引擎（Clock/Quotation/Event/Main），纯标准库轻量（1-2核/2-4G） | **P0 做**：ClockEngine 双轨时钟替代各脚本散落的 sleep；EventEngine 订阅解耦替代线性调用 |
| **Rockyzsu/stock**（sto/stock） | 8849 | BaseService 统一 retry + trading_time 判定；告警冷却 `has_sent`；jsonp2json 工具 | **P0 做**：68 个源的采集器统一基类；告警冷却防同一标的重推。**反面教材：每日一表不要学** |
| **apache/doris** | 16078 | 单机最小 8C/24G/60G SSD，太重 | **P2 不引入**。但抄两个设计：Unique Key UPSERT 去重 + Stream Load label 幂等——用 DuckDB 同样实现 |

### 必须纠正的一条错误结论
子代理称「分钟级代码已写好：`scripts/longrun_collect.py:190` 的 `run_realtime(interval=60)`」。
**已核实：该文件在本项目不存在**（`find` 无结果，workflows 无引用）——子代理把别的仓库代码当成了我们的。
真实的分钟级采集器是本次新写的 `scripts/realtime_minute.py`，且数据源是 **push2delay 全市场快照**（1 请求/100 只 × 60 页），不是它推演的腾讯 `qt.gtimg.cn`（60 只/批 × 89 批），**配额模型完全不同**（见下）。

## 二、GitCode Notebook 能不能替代本地站——不能（官方文档证实）

三条硬限制叠加：
1. 「目前一次启动 Notebook 后的使用时长为**两小时**」
2. 「创建的资源**不会进行持久化保存**」（50G 持久化仅作预告，未确认上线）
3. 「如果是在运行中，也**切勿重启**，防止文件丢失」

**结论：Notebook 适合一次性批量补数据（2 小时够）、算法实验/回测、临时数据处理；不能做常驻服务。**

### 那云服务器还要不要？
要，但换形式。三个选项：

| 选项 | 常驻 | 成本 | 备案/合规 | 建议 |
|---|---|---|---|---|
| GitCode Notebook | ❌ 2h 上限 + 不持久化 | 免费（限时，按核时计） | 无 | **只用于批量回补**（复权补录 2 小时 + 算法实验） |
| GitHub Codespace | ✅（项目已有先例，突破 Actions 6h 限制） | 免费额度 60h/月，超额付费 | 无 | **分钟级采集 + 算法引擎首选** |
| 轻量云服务器（阿里云/腾讯云） | ✅ | 付费 | 域名+备案+HTTPS 成本高 | 仅当要对外提供 API 时 |

## 三、分钟级方案（已实现 + 待验证）

### 已实现
`scripts/realtime_minute.py`：常驻采集，每 60 秒一轮全市场 **5923 只**（push2delay 绕 WAF），实测一轮 15 秒。

### 数据流
```
数据源(push2delay/东财) → [云服务器 1min tick] → 原子写 JSON → git push
   → GitHub raw → GitHub Pages (data_origin_patch.js 已改为 GitHub 优先)
```

### 真正的瓶颈（子代理指出，我认同）
**不在采集，在 `git push → CDN` 链路**：GitHub Pages 有 CDN 缓存，raw 文件 push 后全球生效通常 1-5 分钟。
要做到「用户刷新就看到 60 秒前数据」，两个选择：
- A. 接受 1-5 分钟 CDN 延迟（仍是 5 分钟 → 1 分钟的改善）
- B. 云服务器对外提供 HTTP API + 前端直连（需域名备案，国内合规成本高）

### 未解决的前置风险（**必须先量化，否则分钟级可能不成立**）

1. **限流配额未实测**：子代理基于腾讯旧结论推演「19 分钟触发限流」，但我们的采集器用 push2delay（全市场 60 页/轮）。
   → 需实测：push2delay 在 60 秒频率下连续采集多少轮会 429/reset。**这是方案成立的前置条件。**
2. **DuckDB 多进程读写锁竞争**（采集层写 + 算法层读同一文件）未实测。
3. **双路采集重复写入**（Actions 兜底 + 云服务器主路）必须有幂等兜底。
4. **成本待用户决策**：Codespace 超额付费 or 轻量云服务器月费。

## 四、落地路线（建议顺序）

1. **先实测限流**（30 分钟，本地就能做）：`realtime_minute.py --interval 60` 连续跑 2 小时，记录失败率
2. **幂等 + 去重**（抄 Doris 设计，1 小时）：DuckDB 表加唯一键 `(code, ts)`，INSERT 前 DELETE 或 ON CONFLICT
3. **BaseService 基类**（抄 sto/stock，2 小时）：68 个源采集器统一 retry/trading_time/jsonp2json
4. **ClockEngine + EventEngine**（抄 Qbot，半天）：分钟 tick 替代散落 sleep，采集/算法/推送解耦
5. **部署到 Codespace**（已写好 `deploy_cloud.sh`，1 小时）
6. **Notebook 只做批量回补**：复权补录（本地跑了 300+ 只/89MB，可迁 Notebook 跑全量）

## 五、诚实边界

- 未实测：Notebook 具体规格（CPU/内存/出口 IP）、DuckDB 多进程并发、push2delay 分钟级限流
- 未运行：Doris/Qbot/sto 的代码（静态阅读）
- 未决策：是否投入 Codespace/云服务器成本
