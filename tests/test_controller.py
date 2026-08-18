from tpb9000_testbench.controller import Controller
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

