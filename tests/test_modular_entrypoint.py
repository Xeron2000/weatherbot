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
