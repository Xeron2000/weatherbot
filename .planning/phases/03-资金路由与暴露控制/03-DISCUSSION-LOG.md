# Phase 3: 资金路由与暴露控制 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 03-资金路由与暴露控制
**Areas discussed:** 资金池结构, 暴露上限维度, 冲突净额规则, 路由优先级, 预留与释放时机

---

## 资金池结构

| Option | Description | Selected |
|--------|-------------|----------|
| 独立资金池 | 总 bankroll 下切出 YES 池和 NO 池，各自独立占用和回收 | ✓ |
| 共享池+腿上限 | 单一 balance + 分腿上限 | |
| 动态再平衡池 | 允许按候选质量在两腿间搬预算 | |

**User's choice:** 独立资金池
**Notes:** 预算单位选百分比；每轮扫描刷新；两腿不能互借；初始配比 YES 30 / NO 70。

---

## 暴露上限维度

| Option | Description | Selected |
|--------|-------------|----------|
| 最坏损失 | 所有 cap 统一按 worst-case loss 统计 | ✓ |
| 入场成本 | 按现金占用统计 | |
| 名义敞口 | 按 payout/notional 统计 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 都可配置且任一生效 | city / date / city+date / leg / global 任一命中即拦截 | ✓ |
| 只保留 city+date | 只把事件当 cap 主键 | |
| city/date 只观察 | 只报表不拦截 | |

**User's choice:** 最坏损失；都可配置且任一生效；双保险；总资金 cap 直接拒单；默认保守模板。
**Notes:** 单腿 cap 不能只靠资金池代替，风控要保守优先。

---

## 冲突净额规则

| Option | Description | Selected |
|--------|-------------|----------|
| 最坏路径聚合 | 同 event 多 bucket 默认不净额 | ✓ |
| 相邻温区部分净额 | 对相邻 bucket 做有限净额 | |
| 仅同 bucket 聚合 | 只处理完全重叠 bucket | |

| Option | Description | Selected |
|--------|-------------|----------|
| 默认不允许 | 同 bucket 的 YES / NO 不得共存 | ✓ |
| 允许但按净额算 | 同 bucket 可对冲 | |
| 只允许人工例外 | 默认拒绝，仅保留人工 override seam | |

**User's choice:** 最坏路径聚合；同 bucket YES/NO 默认不允许；同 event 全相关；冲突时拒绝新候选。
**Notes:** 先保留已有暴露一致性，不做自动 portfolio optimizer。

---

## 路由优先级

| Option | Description | Selected |
|--------|-------------|----------|
| 先分腿后排序 | 先在 YES / NO 各自池内排序，再受全局 cap 拦截 | ✓ |
| 全候选统一排序 | 所有候选一起竞争总资金 | |
| NO 固定优先 | NO 先吃完，再轮到 YES | |

| Option | Description | Selected |
|--------|-------------|----------|
| 按 edge 排序 | 候选主排序键 | ✓ |
| 按 edge / 风险比 | 引入归一化公式 | |
| 按临近结算 | 时间优先 | |

**User's choice:** 先分腿后排序；腿内按 edge 排序；tie-breaker 先看流动性；cap 拒绝需保留 reason；全局 cap 不足时不做跨腿重排。
**Notes:** 30/70 分腿设计不能因为全局 cap 再被冲淡。

---

## 预留与释放时机

| Option | Description | Selected |
|--------|-------------|----------|
| 进入路由通过后 | 候选被 router 录取、准备进入后续下单意图时开始预留 | ✓ |
| candidate 阶段就预留 | 过早占用 | |
| 成交后才预留 | 过晚占用 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 失效即释放 | 淘汰/取消/过期/平仓即释放 | ✓ |
| 下一轮统一释放 | 本轮冻结，下一轮再回收 | |
| 只在结算后释放 | 一路锁到最后 | |

**User's choice:** 路由通过后开始预留；失效即释放；预留金额按最坏损失全额；重新扫描降级/消失时立即释放并记原因。
**Notes:** reserve 口径必须和暴露 cap 口径保持一致。

---

## the agent's Discretion

- 保守模板下各 cap 的具体默认百分比
- state / market JSON 的精确字段命名
- 后续是否保留“自动缩量再试”作为 seam，但不在本阶段首版启用

## Deferred Ideas

None.
