import importlib
import json
import sys

from pathlib import Path

import bot_v2
import pytest

from weatherbot import config, paths


def test_bot_v2_public_surface_still_exists():
    for name in [
        "scan_and_update",
        "monitor_positions",
        "print_status",
        "print_report",
        "run_loop",
        "load_state",
        "save_state",
        "new_market",
    ]:
        assert hasattr(bot_v2, name)


def test_modular_paths_still_point_to_repo_root_defaults():
    root = Path(__file__).resolve().parent.parent

    assert paths.ROOT_DIR == root
    assert paths.CONFIG_FILE == root / "config.json"
    assert paths.DATA_DIR == root / "data"
    assert paths.STATE_FILE == root / "data" / "state.json"
    assert paths.CALIBRATION_FILE == root / "data" / "calibration.json"
    assert paths.MARKETS_DIR == root / "data" / "markets"


def test_modular_config_loader_reads_default_repo_config():
    loaded = config.load_config()

    assert loaded == bot_v2._cfg


def test_load_config_prefers_visual_crossing_env(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "balance": 10000.0,
                "vc_key": "json-key",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VISUAL_CROSSING_KEY", "env-key")

    loaded = config.load_config(config_path)

    assert loaded["vc_key"] == "env-key"
    assert loaded["balance"] == 10000.0


def test_load_config_falls_back_to_json_vc_key(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "balance": 10000.0,
                "vc_key": "json-key",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("VISUAL_CROSSING_KEY", raising=False)

    loaded = config.load_config(config_path)

    assert loaded["vc_key"] == "json-key"
    assert loaded["balance"] == 10000.0


def write_profile_config(config_path, strategy_profile="1000"):
    config_path.write_text(
        json.dumps(
            {
                "balance": 1000.0,
                "vc_key": "json-key",
                "yes_strategy": {
                    "max_price": 0.04,
                    "min_probability": 0.02,
                    "min_edge": 0.05,
                    "min_size": 1.0,
                    "max_size": 40.0,
                },
                "no_strategy": {
                    "min_price": 0.75,
                    "max_ask": 0.95,
                    "min_probability": 0.90,
                    "min_edge": 0.03,
                    "min_size": 1.0,
                    "max_size": 20.0,
                },
                "risk_router": {
                    "yes_budget_pct": 0.25,
                    "no_budget_pct": 0.75,
                    "global_usage_cap_pct": 0.80,
                },
                "order_policy": {
                    "yes_time_in_force": "GTC",
                    "no_time_in_force": "GTD",
                    "gtd_buffer_hours": 6.0,
                    "price_improve_ticks": 1,
                    "replace_edge_buffer": 0.02,
                    "max_order_hours_open": 72.0,
                },
                "paper_execution": {
                    "submission_latency_ms": 5000,
                    "queue_ahead_shares": 80.0,
                    "queue_ahead_ratio": 0.25,
                    "touch_not_fill_min_touches": 1,
                    "partial_fill_slice_ratio": 0.5,
                    "cancel_latency_ms": 4000,
                    "adverse_fill_buffer_ticks": 1,
                },
                "strategy_profile": strategy_profile,
                "strategy_profiles": {
                    "100": {
                        "balance": 100.0,
                        "yes_strategy": {
                            "max_price": 0.08,
                            "max_size": 25.0,
                        },
                        "no_strategy": {
                            "min_probability": 0.84,
                            "max_size": 18.0,
                        },
                        "risk_router": {
                            "global_usage_cap_pct": 0.92,
                        },
                    },
                    "1000": {
                        "balance": 1000.0,
                        "yes_strategy": {
                            "max_price": 0.05,
                        },
                    },
                    "10000": {
                        "balance": 10000.0,
                        "yes_strategy": {
                            "max_price": 0.02,
                            "max_size": 12.0,
                        },
                        "no_strategy": {
                            "min_probability": 0.95,
                            "max_size": 10.0,
                        },
                        "risk_router": {
                            "global_usage_cap_pct": 0.72,
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def reload_runtime_modules(monkeypatch, config_path):
    monkeypatch.setattr(paths, "CONFIG_FILE", config_path)
    monkeypatch.setattr(config, "CONFIG_FILE", config_path)
    sys.modules.pop("bot_v2", None)
    weatherbot_module = importlib.reload(importlib.import_module("weatherbot"))
    bot_v2_module = importlib.import_module("bot_v2")
    return weatherbot_module, bot_v2_module


@pytest.mark.parametrize(
    ("profile_name", "expected_balance", "expected_yes_max_price", "expected_global_usage_cap"),
    [
        ("100", 100.0, 0.08, 0.92),
        ("1000", 1000.0, 0.05, 0.80),
        ("10000", 10000.0, 0.02, 0.72),
    ],
)
def test_load_config_merges_selected_strategy_profile(
    monkeypatch,
    tmp_path,
    profile_name,
    expected_balance,
    expected_yes_max_price,
    expected_global_usage_cap,
):
    config_path = tmp_path / "config.json"
    write_profile_config(config_path, strategy_profile=profile_name)
    monkeypatch.delenv("VISUAL_CROSSING_KEY", raising=False)

    loaded = config.load_config(config_path)

    assert loaded["balance"] == expected_balance
    assert loaded["yes_strategy"]["max_price"] == expected_yes_max_price
    assert loaded["yes_strategy"]["min_edge"] == 0.05
    assert "no_strategy" not in loaded
    assert "no_kelly_fraction" not in loaded
    assert loaded["risk_router"]["yes_budget_pct"] == 0.25
    assert loaded["risk_router"]["global_usage_cap_pct"] == expected_global_usage_cap
    assert loaded["paper_execution"]["submission_latency_ms"] == 5000
    assert loaded["order_policy"]["max_order_hours_open"] == 72.0
    assert "no_budget_pct" not in loaded["risk_router"]
    assert "no_leg_cap_pct" not in loaded["risk_router"]
    assert "no_time_in_force" not in loaded["order_policy"]


def test_load_config_env_visual_crossing_key_wins_after_profile_merge(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    write_profile_config(config_path, strategy_profile="100")
    monkeypatch.setenv("VISUAL_CROSSING_KEY", "env-key")

    loaded = config.load_config(config_path)

    assert loaded["balance"] == 100.0
    assert loaded["vc_key"] == "env-key"
    assert "no_strategy" not in loaded


def test_runtime_entrypoints_consume_merged_profile_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    write_profile_config(config_path, strategy_profile="100")
    monkeypatch.delenv("VISUAL_CROSSING_KEY", raising=False)

    weatherbot_module, bot_v2_module = reload_runtime_modules(monkeypatch, config_path)

    assert weatherbot_module.BALANCE == 100.0
    assert weatherbot_module.YES_STRATEGY["max_price"] == 0.08
    assert weatherbot_module.YES_STRATEGY["min_edge"] == 0.05
    assert weatherbot_module.NO_STRATEGY["min_probability"] == 0.84
    assert weatherbot_module.RISK_ROUTER["global_usage_cap_pct"] == 0.92
    assert weatherbot_module.PAPER_EXECUTION["submission_latency_ms"] == 5000
    assert bot_v2_module.BALANCE == weatherbot_module.BALANCE
    assert bot_v2_module.YES_STRATEGY == weatherbot_module.YES_STRATEGY
    assert bot_v2_module.NO_STRATEGY == weatherbot_module.NO_STRATEGY
    assert bot_v2_module.RISK_ROUTER == weatherbot_module.RISK_ROUTER


def test_load_config_without_profile_fields_keeps_legacy_behavior(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "balance": 321.0,
                "vc_key": "json-key",
                "yes_strategy": {"max_price": 0.03},
                "paper_execution": {
                    "submission_latency_ms": 5000,
                    "queue_ahead_shares": 80.0,
                    "queue_ahead_ratio": 0.25,
                    "touch_not_fill_min_touches": 1,
                    "partial_fill_slice_ratio": 0.5,
                    "cancel_latency_ms": 4000,
                    "adverse_fill_buffer_ticks": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("VISUAL_CROSSING_KEY", raising=False)

    loaded = config.load_config(config_path)

    assert loaded["balance"] == 321.0
    assert loaded["yes_strategy"]["max_price"] == 0.03
    assert "strategy_profile" not in loaded
    assert "no_strategy" not in loaded
    assert "no_kelly_fraction" not in loaded


def test_load_config_unknown_explicit_profile_raises(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    write_profile_config(config_path, strategy_profile="missing")
    monkeypatch.delenv("VISUAL_CROSSING_KEY", raising=False)

    with pytest.raises(ValueError, match="unknown_strategy_profile"):
        config.load_config(config_path)
