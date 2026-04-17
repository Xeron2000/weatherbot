---
phase: 03
slug: 资金路由与暴露控制
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-17
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — direct `uv run pytest` |
| **Quick run command** | `uv run pytest tests/test_phase3_router.py -q` |
| **Full suite command** | `uv run pytest tests/test_phase2_probability.py tests/test_phase2_quotes.py tests/test_phase2_strategies.py tests/test_phase2_reporting.py tests/test_phase3_router.py tests/test_phase3_scan_loop.py tests/test_phase3_reporting.py -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_phase3_router.py -q` or the task-specific phase-3 test file.
- **After every plan wave:** Run `uv run pytest tests/test_phase2_probability.py tests/test_phase2_quotes.py tests/test_phase2_strategies.py tests/test_phase2_reporting.py tests/test_phase3_router.py tests/test_phase3_scan_loop.py tests/test_phase3_reporting.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | STRAT-04 | T-03-01 | 独立 YES/NO 预算、multi-cap worst-loss 拦截、同 bucket YES/NO 互斥 | unit | `uv run pytest tests/test_phase3_router.py -q` | ✅ | ⬜ pending |
| 03-02-01 | 02 | 2 | RISK-01 | T-03-02 | scan loop 将 route decision 与 reserved exposure 写入 state/market JSON | integration | `uv run pytest tests/test_phase3_scan_loop.py -q` | ✅ | ⬜ pending |
| 03-03-01 | 03 | 3 | RISK-02 | T-03-03 | 候选降级/冲突/消失时立即 release，并保留 release reason | integration | `uv run pytest tests/test_phase3_scan_loop.py -q -k "release or conflict"` | ✅ | ⬜ pending |
| 03-04-01 | 04 | 4 | STRAT-04, RISK-01, RISK-02 | T-03-04 | CLI 直接读取 risk facts 展示 per-leg budget、exposure、reject/release reasons | reporting | `uv run pytest tests/test_phase3_reporting.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| status/report 中预算与暴露摘要可读性 | STRAT-04, RISK-01 | CLI 文案布局需要人工确认 | 运行 `python bot_v2.py status` 与 `python bot_v2.py report`，确认 YES/NO budget usage、event/city/date exposure、reject/release reasons 可直接读懂 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
