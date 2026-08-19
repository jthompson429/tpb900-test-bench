from pathlib import Path

from tpb9000_testbench.cli import main


CONFIG = str(Path(__file__).parents[1] / "config/testbench.yaml")


def test_simulated_status_does_not_construct_gpio(monkeypatch, capsys):
    def gpio_must_not_be_used(*_args, **_kwargs):
        raise AssertionError("real GPIO backend was constructed")

    monkeypatch.setattr("tpb9000_testbench.cli.GpioHardware", gpio_must_not_be_used)
    assert main(["--config", CONFIG, "--simulate", "--simulate-start", "between", "status"]) == 0
    output = capsys.readouterr().out
    assert "SIMULATION MODE" in output
    assert "BETWEEN LIMITS" in output


def test_simulated_endurance_cli(tmp_path, monkeypatch):
    source = Path(CONFIG).read_text()
    config_path = tmp_path / "config" / "testbench.yaml"
    config_path.parent.mkdir()
    config_path.write_text(source.replace("directory: logs", f"directory: {tmp_path / 'logs'}"))
    monkeypatch.setattr("tpb9000_testbench.cli.signal.signal", lambda *_args: None)
    assert main(["--config", str(config_path), "--simulate", "test", "--cycles", "1"]) == 0
    assert len(list((tmp_path / "logs").glob("*.log"))) == 1
    assert len(list((tmp_path / "logs").glob("*-summary.json"))) == 1
