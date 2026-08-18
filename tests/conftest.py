from pathlib import Path

import pytest

from tpb9000_testbench.config import load_config


@pytest.fixture
def config():
    cfg = load_config(Path(__file__).parents[1] / "config/testbench.yaml")
    return cfg.__class__(**{**cfg.__dict__, "pause_after_close_seconds": 0.02,
                            "pause_after_open_seconds": 0.02, "poll_interval_seconds": 0.01,
                            "max_close_travel_seconds": 0.05, "max_open_travel_seconds": 0.05})

