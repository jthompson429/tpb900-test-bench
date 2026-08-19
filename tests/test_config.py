from pathlib import Path

import pytest

from tpb9000_testbench.config import ConfigurationError, load_config


def test_default_config_loads():
    config = load_config(Path(__file__).parents[1] / "config/testbench.yaml")
    assert config.max_cycles == 25
    assert config.motor.rpwm_gpio == 18
    assert config.log_directory.is_absolute()


def test_duplicate_gpio_rejected(tmp_path):
    source = (Path(__file__).parents[1] / "config/testbench.yaml").read_text()
    path = tmp_path / "bad.yaml"
    path.write_text(source.replace("closed_gpio: 6", "closed_gpio: 5"))
    with pytest.raises(ConfigurationError, match="unique"):
        load_config(path)

