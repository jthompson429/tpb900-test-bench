import pytest

from tpb9000_testbench.controller import Controller, JogStopReason, TestBenchFault as BenchFault
from tpb9000_testbench.hardware import Direction, LimitState

from fakes import FakeClock, FakeHardware


def test_move_stops_at_target_limit(config):
    hardware = FakeHardware([LimitState(False, False), LimitState(False, False), LimitState(True, False)])
    clock = FakeClock()
    elapsed = Controller(hardware, config, clock=clock, sleeper=clock.sleep).move_until_limit(Direction.OPEN, 1)
    assert elapsed == 0.01
    assert hardware.drives == [Direction.OPEN]
    assert hardware.stop_count >= 1


def test_timeout_stops_motor(config):
    hardware = FakeHardware([LimitState(False, False)])
    clock = FakeClock()
    controller = Controller(hardware, config, clock=clock, sleeper=clock.sleep)
    try:
        controller.move_until_limit(Direction.CLOSE, 0.03)
    except Exception as exc:
        assert "not reached" in str(exc)
    assert hardware.stop_count >= 1


def test_both_limits_fail_endurance_test(config):
    hardware = FakeHardware([LimitState(True, True)])
    clock = FakeClock()
    result = Controller(hardware, config, clock=clock, sleeper=clock.sleep).run_test(1)
    assert result.result == "FAIL"
    assert "Both limit" in result.fault_reason


def test_one_complete_cycle(config):
    states = [
        LimitState(True, False),                 # initial validation
        LimitState(True, False),                 # close precheck
        LimitState(False, False), LimitState(False, True),
        LimitState(False, True),                 # open precheck
        LimitState(False, False), LimitState(True, False),
    ]
    hardware = FakeHardware(states)
    clock = FakeClock()
    result = Controller(hardware, config, clock=clock, sleeper=clock.sleep).run_test(1)
    assert result.result == "PASS"
    assert result.completed_cycles == 1
    assert hardware.drives == [Direction.CLOSE, Direction.OPEN]


def test_requested_jog_duration_is_normal_stop(config):
    hardware = FakeHardware([LimitState(False, False)])
    clock = FakeClock()
    result = Controller(hardware, config, clock=clock, sleeper=clock.sleep).jog(Direction.CLOSE, 0.03)
    assert result.reason is JogStopReason.REQUESTED_DURATION_COMPLETE
    assert result.elapsed_seconds == pytest.approx(0.03)
    assert hardware.stop_count >= 1


def test_jog_limit_is_normal_stop(config):
    hardware = FakeHardware([LimitState(False, False), LimitState(False, True)])
    clock = FakeClock()
    result = Controller(hardware, config, clock=clock, sleeper=clock.sleep).jog(Direction.CLOSE, 0.03)
    assert result.reason is JogStopReason.LIMIT_REACHED
    assert result.elapsed_seconds == 0


def test_jog_without_duration_faults_at_safety_timeout(config):
    hardware = FakeHardware([LimitState(False, False)])
    clock = FakeClock()
    controller = Controller(hardware, config, clock=clock, sleeper=clock.sleep)
    with pytest.raises(BenchFault, match="safety timeout"):
        controller.jog(Direction.OPEN)
    assert hardware.stop_count >= 1


@pytest.mark.parametrize("duration", [0, -1, 5])
def test_invalid_jog_duration_rejected(config, duration):
    hardware = FakeHardware([LimitState(False, False)])
    with pytest.raises(ValueError, match="Jog duration"):
        Controller(hardware, config).jog(Direction.OPEN, duration)
