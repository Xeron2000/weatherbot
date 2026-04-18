import json

from pathlib import Path

import bot_v2

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
