# Phase 1 Research — 市场语义与扫描基线

**Phase:** 1
**Researched:** 2026-04-17
**Confidence:** MEDIUM-HIGH

## Objective

回答这个问题：**为了把 Phase 1 计划好，必须先知道什么？**

Phase 1 不是做收益优化，也不是做订单生命周期；它要先把“我们到底在扫什么市场、这些市场按什么规则结算、哪些市场应该被拒绝”这层基础做对。当前 `bot_v2.py` 已经能扫描城市、发现事件、保存 market JSON，但市场对象仍然过于粗糙：

- 每个 market record 只按 `city + date` 建模，尚未显式表示 event / condition / token 语义。
- `all_outcomes` 只保存 `market_id` 和温区，缺少 YES/NO token、结算规则文本、数据源约束、映射校验结果。
- 扫描会在 `get_polymarket_event()` 成功后继续推进，但对规则缺失、单位不一致、数据陈旧的停单防线不够显式。

因此，Phase 1 的正确方向是：**先把扫描输出升级为可信的市场语义快照和拒绝原因模型，再谈后续候选定价与挂单。**

## What the existing code already gives us

### Reusable baseline

- `bot_v2.py:54-91` 已有城市、站点、单位、时区映射。
- `bot_v2.py:268-341`（现有 market helper 区）已能解析温区文本、计算结算时间窗口。
- `bot_v2.py:348-389` 已有 per-market JSON 持久化壳子。
- `bot_v2.py:414-541` 已有连续扫描、forecast snapshot、market snapshot 的主循环骨架。

### Current gaps blocking Phase 1 success criteria

1. **市场粒度不对**
   - 现在一个 `data/markets/{city}_{date}.json` 聚合整天市场，内部只存 `all_outcomes` 列表。
   - Phase 1 需要让“候选市场快照”能稳定标识每个 bucket/outcome 的语义与归属，而不是只在运行时临时算。

2. **规则语义未被持久化为真相**
   - 当前 `new_market()` 只保存 `station`、`unit`、`event_end_date` 等少数字段。
   - 研究要求把 resolution text、结算站点、单位、整度精度、condition/token 标识作为后续一切判断的 source of truth。

3. **缺少显式 rejection / skip 分类**
   - 当前扫描的 skip 多数是 `continue`。
   - Phase 1 成功标准明确要求：规则映射缺失、单位不一致、天气数据过期时要**明确跳过并说明原因**。

## Phase-specific implementation guidance

### 1. Keep the runtime shape, but add a tighter domain schema

本阶段不需要完整模块化重构，也不该上 SQLite。遵循项目约束，继续使用：

- Python CLI
- 本地 JSON 持久化
- `bot_v2.py` 为主入口

但要把扫描阶段的输出 schema 明确化，建议至少引入以下概念（可以先以 dict schema 落地，而不是 dataclass/package 重构）：

- `event_identity`: `city`, `date`, `event_slug`, `event_end_date`
- `resolution_metadata`: `station`, `unit`, `resolution_source`, `rounding_rule`, `resolution_text`
- `market_contracts[]`: 每个温区 outcome 的 `market_id`, `condition_id`, `token_id_yes`, `token_id_no`, `range_low`, `range_high`, `question`
- `scan_guardrails`: `mapping_ok`, `unit_ok`, `weather_fresh`, `market_complete`, `skip_reasons[]`

这层 schema 必须落到 `data/markets/*.json` 中，不能只存在内存里。

### 2. Add a “market admissibility” gate before any later strategy logic

Phase 1 最重要的不是多扫几个城市，而是**只把可以被正确理解的市场纳入 universe**。

建议在现有 `scan_and_update()` 中，创建 market record 后、追加 forecast / price snapshots 前，插入单独的 admissibility 评估步骤：

- 检查 event 是否包含完整温区 outcomes
- 检查每个 outcome 是否可解析出温区
- 检查 market question / rules / title 是否与本地 `station` / `unit` 一致
- 检查天气源是否在 freshness 阈值内
- 检查 forecast 单位是否与市场结算单位一致

输出必须是结构化结果，而不是单纯 `continue`。

### 3. Use explicit skip reasons, not implicit control flow

后续 Phase 2 的候选解释依赖 Phase 1 的跳过原因，所以本阶段应建立统一 reason code。

建议 reason code 至少包括：

- `missing_rule_mapping`
- `missing_contract_identifiers`
- `unparseable_temperature_range`
- `unit_mismatch`
- `weather_data_stale`
- `weather_data_missing`
- `event_outside_time_window`

这样后续 `status/report/dashboard` 可以直接消费，不必重做解释逻辑。

### 4. Do not silently trust current location config as canonical truth

`LOCATIONS` 当前是本地硬编码映射，但研究与 requirements 都要求“每个被纳入扫描结果的市场都能显示正确的机场站点、温区、结算规则和 condition/token 标识”。

因此本阶段要把本地映射当作**candidate mapping**，并和市场实际 rule text 做交叉验证：

- 本地 `station` 与 market rule text 提到的 station 不一致 → skip
- 本地 `unit` 与 market bucket 文本单位不一致 → skip
- 无法从 event/market payload 提取 condition/token 标识 → skip

## Recommended task split implications

Phase 1 适合拆成 2-3 个 plans，不宜压成单 plan：

1. **扫描语义 schema / contract plan**
   - 定义 market record 新字段与 admissibility schema
   - 不改变后续策略规则

2. **扫描管线接线 plan**
   - 在 `scan_and_update()` 中填充 resolution metadata / contract identifiers / skip reasons
   - 让 `data/markets/*.json` 输出稳定

3. **验证与可见性 plan**
   - 提供 status/report 或 debug 输出，证明市场被纳入或跳过的原因
   - 补测试脚手架，验证规则缺失/单位不一致/天气过期会被拒绝

## Project-specific cautions

### Brownfield caution

不要在 Phase 1 直接把整个项目重写成 `src/weatherbot/` 包。研究虽然把它列为中期推荐方向，但本 phase 的 roadmap 目标更小：先把市场语义与扫描基线做对。

### Persistence caution

虽然项目研究总体推荐未来把 authoritative execution ledger 升级到 SQLite，但 **Phase 1 仍应遵守当前 roadmap/runtime 约束，继续使用本地 JSON 持久化**。SQLite 属于后续订单生命周期阶段的架构转折点，不应提前塞入本阶段。

### Testing caution

当前仓库没有测试体系，但计划里必须补最小自动验证，否则后续 phase 无法对“skip 而非交易”做回归验证。最小可行方式：

- 引入 `tests/` 目录
- 为纯函数和 market admissibility guard 写 pytest
- 对扫描输出做 fixture 驱动的 JSON-level 验证

## Validation Architecture

Phase 1 的验证不该只看“脚本能跑”。它必须覆盖三层：

1. **Schema truth**
   - `data/markets/*.json` 中存在 resolution metadata、contract identifiers、guardrail fields
2. **Guardrail behavior**
   - 缺规则、单位不一致、天气数据过期时，market 被标记 rejected/skipped
3. **Loop survivability**
   - 扫描循环遇到坏 market 时继续处理其他市场，不会中断整轮 scan

建议 planner 为本 phase 设计以下自动验证面：

- 纯函数测试：temperature range parse、unit normalization、freshness check、mapping validation
- fixture 测试：给定 event/weather payload → 产生 expected `skip_reasons` / `market_contracts`
- smoke 命令：运行一次 scan 子命令或可复用 helper，确认会生成带新字段的 market snapshot

## Acceptance truths for planning

如果 Phase 1 规划是对的，那么执行完成后应能证明：

- 机器人可以持续扫描配置城市与日期范围，并产生 market snapshot 文件
- 每个纳入 universe 的 market snapshot 都带有 station / unit / resolution rule / condition/token / bucket range
- 坏 market 会被结构化拒绝，并记录原因
- 这些拒绝不会阻塞其他城市/日期的扫描

## Sources used

- `/home/xeron/Coding/weatherbot/.planning/ROADMAP.md`
- `/home/xeron/Coding/weatherbot/.planning/REQUIREMENTS.md`
- `/home/xeron/Coding/weatherbot/.planning/PROJECT.md`
- `/home/xeron/Coding/weatherbot/.planning/research/SUMMARY.md`
- `/home/xeron/Coding/weatherbot/.planning/research/ARCHITECTURE.md`
- `/home/xeron/Coding/weatherbot/.planning/research/PITFALLS.md`
- `/home/xeron/Coding/weatherbot/.planning/codebase/ARCHITECTURE.md`
- `/home/xeron/Coding/weatherbot/.planning/codebase/CONVENTIONS.md`
- `/home/xeron/Coding/weatherbot/bot_v2.py`

---

## RESEARCH COMPLETE
