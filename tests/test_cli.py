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


def test_requested_simulated_jog_is_successful(monkeypatch, capsys):
    monkeypatch.setattr("tpb9000_testbench.cli.signal.signal", lambda *_args: None)
    assert main(["--config", CONFIG, "--simulate", "jog-close", "--seconds", "0.05"]) == 0
    output = capsys.readouterr().out
    assert "requested duration complete" in output


def test_simulated_stall_produces_failed_summary(tmp_path, monkeypatch):
    source = Path(CONFIG).read_text()
    config_path = tmp_path / "config" / "testbench.yaml"
    config_path.parent.mkdir()
    config_path.write_text(source.replace("directory: logs", f"directory: {tmp_path / 'logs'}"))
    monkeypatch.setattr("tpb9000_testbench.cli.signal.signal", lambda *_args: None)
    code = main([
        "--config", str(config_path), "--simulate", "--simulate-fault", "stall-close",
        "test", "--cycles", "1",
    ])
    assert code == 2
    summary = next((tmp_path / "logs").glob("*-summary.json")).read_text()
    assert '"result": "FAIL"' in summary
    assert "CLOSE limit not reached" in summary


def test_fault_injection_requires_simulation(capsys):
    assert main(["--config", CONFIG, "--simulate-fault", "stall-close", "status"]) == 2
    assert "requires --simulate" in capsys.readouterr().err
