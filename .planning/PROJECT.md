# Polymarket Weather Asymmetry Bot

## What This Is

这是一个基于现有 `weatherbot` 代码库继续演进的 Polymarket 天气市场自动交易项目，目标是在天气温度区间市场里执行一套高不对称回报策略：低价 YES 窄温区猎杀 + 高价 NO 稳赚小利。v1 先做模拟交易，但要把自动扫描、候选筛选、被动挂单、订单生命周期和持仓管理链路完整跑通，为后续实盘接入留好执行边界。

## Core Value

在天气市场里稳定抓住“概率对、价格错”的盘口，并用可验证的自动化执行把高赔率机会变成可重复策略。

## Requirements

### Validated

- ✓ 扫描多个城市的 Polymarket 天气温度市场并抓取多源天气预测 — existing
- ✓ 基于 EV、Kelly、价格、流动性和滑点过滤候选交易 — existing
- ✓ 将市场、仓位、校准和账户状态持久化到本地 JSON — existing
- ✓ 提供 CLI 状态/报告输出与本地 dashboard 查看结果 — existing
- ✓ 在不发送真实订单的前提下跑完整 paper trading，并可回放 execution events 校验保守 fill 假设 — validated in Phase 05

### Active

- [ ] 将当前方向性入场逻辑升级为“低价 YES 窄温区猎杀 + 高价 NO 稳赚小利”双策略框架
- [ ] 支持面向挂单的执行模型：报价、排队、成交、撤单、超时失效与剩余订单管理
- [ ] 在 20+ 城市天气市场中持续扫描候选标的，并按策略类型分别做定价与仓位控制
- [ ] 在模拟模式下验证资金分配、风险暴露、订单簿假设和持仓退出规则
- [ ] 为后续实盘接入预留清晰的下单/撤单执行接口，但 v1 不接真实资金

### Out of Scope

- 实盘自动下单与真实资金执行 — v1 先验证策略、订单管理和风控闭环
- 非天气类 Polymarket 市场 — 首个里程碑只聚焦天气温度市场
- 多用户 Web 产品化界面 — 当前只服务单个操作者
- 高并发分布式部署、数据库和云原生基础设施 — 当前阶段保持本地 Python 单进程方案

## Context

- 现有仓库已经有 `bot_v1.py` 和 `bot_v2.py` 两套脚本式实现，覆盖天气抓取、市场匹配、模拟仓位、状态持久化、CLI 报告和 dashboard。
- 当前系统更偏“看到错价后直接按阈值入场”的方向性策略，尚未围绕被动挂单、订单生命周期和双策略资金路由建模。
- 用户给定的新策略核心是两段式：
  - 低价 YES：窄温区（如 52–53°F、38–39°F）在 0.1–2¢ 区间重仓挂 YES，吃高赔率命中。
  - 高价 NO：极端温区在 80–99¢ 区间做高胜率 NO，赚小而稳的价差/结算收益。
- 项目当前没有测试体系、包管理锁文件或模块化边界，后续路线需要在“快速演进现有代码”和“避免脚本继续失控膨胀”之间平衡。
- 这个项目首先服务策略操作者本人，不是做通用 SaaS；成功标准是自动扫描 + 自动挂单链路可持续运行，并能在模拟环境里看清策略表现。

## Current State

- Phase 05 complete — bot 已具备保守 paper execution、append-only execution event ledger 和 replay CLI。
- Next focus: Phase 06 将在这些逐笔执行事实之上补聚合复盘与 readiness 报告。

## Constraints

- **Codebase**: 在现有 `weatherbot` 代码上演进 — 用户明确选择 brownfield 演进而不是重写
- **Trading Mode**: v1 先做模拟交易 — 先验证策略与执行链路，避免真实资金风险
- **Market Scope**: 仅覆盖 Polymarket 天气温度市场 — 与当前仓库能力和给定策略完全对齐
- **Execution Goal**: 完成标准优先“自动扫描 + 挂单” — 先保证候选发现与订单管理闭环
- **Runtime**: 延续 Python CLI + 本地 JSON 持久化 — 现有项目已具备这套运行方式，改造成本最低

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| v1 先做模拟，不直接上实盘 | 交易策略和挂单执行模型都要先验证，真实资金风险过高 | — Pending |
| 首个里程碑仅做天气市场 | 现有代码和给定策略都围绕天气市场，先聚焦能缩短验证路径 | — Pending |
| 在现有 `weatherbot` 代码上演进 | 代码库已有天气抓取、市场匹配和状态存储能力，可复用 | — Pending |
| 以自动扫描 + 被动挂单作为阶段性完成标准 | 这是从“能看机会”走向“能执行机会”的关键跃迁 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-18 after Phase 05 completion*
