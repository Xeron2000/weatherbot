---
phase: 1
slug: 市场语义与扫描基线
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-17
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/test_phase1_market_semantics.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase1_market_semantics.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | MKT-02 | T-1-01 | Snapshot schema preserves station / unit / rule metadata without silent fallback | unit | `pytest tests/test_phase1_market_semantics.py -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 2 | MKT-01 | T-1-02 | Scan loop emits market snapshots for configured cities/dates without aborting on one bad market | integration | `pytest tests/test_phase1_scan_loop.py -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | MKT-03 | T-1-03 | Invalid mapping / stale weather / unit mismatch are rejected with explicit reason codes | unit | `pytest tests/test_phase1_guardrails.py -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 3 | MKT-01, MKT-02, MKT-03 | T-1-04 | CLI/report surfaces accepted vs skipped reasons from persisted snapshots | smoke | `pytest tests/test_phase1_reporting.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase1_market_semantics.py` — schema + mapping validation stubs for MKT-02
- [ ] `tests/test_phase1_scan_loop.py` — scan survivability fixture for MKT-01
- [ ] `tests/test_phase1_guardrails.py` — explicit rejection reason fixtures for MKT-03
- [ ] `tests/test_phase1_reporting.py` — snapshot visibility smoke checks
- [ ] `pytest` install + minimal test entrypoint — current repo has no test framework

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Review a generated `data/markets/*.json` snapshot after one scan run | MKT-01, MKT-02 | Confirms persisted file shape against real upstream payloads, not just fixtures | Run phase smoke command, open one generated market JSON, confirm station / unit / resolution metadata / contract IDs / skip reasons are present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
