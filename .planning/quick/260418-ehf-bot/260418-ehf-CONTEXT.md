# Quick Task 260418-ehf: 把无用的代码文件和旧代码死代码清理掉，然后把bot文件拆分成模块化 - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Task Boundary

把无用的代码文件和旧代码死代码清理掉，然后把bot文件拆分成模块化。

</domain>

<decisions>
## Implementation Decisions

### 清理范围
- 激进清理旧版本：可以删除确认已废弃的旧版本 bot、旧 dashboard、历史脚本等遗留内容，而不是只做保守清理。

### 模块化深度
- 轻量模块化：保留一个主 CLI 入口，把配置、持久化、天气/市场数据、策略/扫描、报告等逻辑拆到独立模块。

### 兼容性要求
- 保持现有兼容：尽量保留当前 CLI 命令、`config.json`、`data/` 持久化格式和主要运行方式。

### the agent's Discretion
- 哪些文件/逻辑可以安全删除，由代码证据和运行链路判断。
- 具体模块边界和文件命名由实现时按现有仓库风格决定。

</decisions>

<specifics>
## Specific Ideas

- 目标不是重写，而是在现有 `weatherbot` brownfield 代码上做清理和轻量模块化。
- 清理应该优先删除已经被新结构替代、不会影响当前主运行链路的旧文件和死代码。

</specifics>

<canonical_refs>
## Canonical References

No external specs — requirements fully captured in decisions above

</canonical_refs>
