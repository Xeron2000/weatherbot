import json
import sys
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ROOT_DIR = FIXTURES_DIR.parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _load_fixture(name):
    path = FIXTURES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def phase1_gamma_event():
    return _load_fixture("phase1_gamma_event.json")


@pytest.fixture
def phase1_weather_snapshot():
    return _load_fixture("phase1_weather_snapshot.json")


@pytest.fixture
def phase2_gamma_event():
    return _load_fixture("phase2_gamma_event.json")


@pytest.fixture
def phase2_weather_snapshot():
    return _load_fixture("phase2_weather_snapshot.json")


@pytest.fixture
def phase2_clob_book_yes():
    return _load_fixture("phase2_clob_book_yes.json")


@pytest.fixture
def phase2_clob_book_no():
    return _load_fixture("phase2_clob_book_no.json")
