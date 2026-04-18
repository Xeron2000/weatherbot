from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT_DIR / "config.json"
DATA_DIR = ROOT_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"
MARKETS_DIR = DATA_DIR / "markets"
CALIBRATION_FILE = DATA_DIR / "calibration.json"


def ensure_data_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    MARKETS_DIR.mkdir(exist_ok=True)
