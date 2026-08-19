import pytest

from tpb9000_testbench.controller import Controller
from tpb9000_testbench.hardware import Direction, SimulatedHardware

from fakes import FakeClock


def test_simulator_starts_without_accessing_gpio():
    clock = FakeClock()
    hardware = SimulatedHardware(1.0, 2.0, start="open", clock=clock)
    assert hardware.limits().open_active
    assert not hardware.limits().closed_active


def test_simulator_models_partial_and_complete_travel():
    clock = FakeClock()
    hardware = SimulatedHardware(1.0, 2.0, start="open", clock=clock)
    hardware.drive(Direction.CLOSE)
    clock.sleep(1.0)
    assert hardware.limits().mechanism_state == "BETWEEN LIMITS"
    clock.sleep(1.0)
    assert hardware.limits().closed_active
    hardware.drive(Direction.OPEN)
    clock.sleep(1.0)
    assert hardware.limits().open_active


def test_controller_completes_cycle_with_simulator(config):
    clock = FakeClock()
    hardware = SimulatedHardware(0.03, 0.03, start="open", clock=clock)
    result = Controller(hardware, config, clock=clock, sleeper=clock.sleep).run_test(2)
    assert result.result == "PASS"
    assert result.completed_cycles == 2
    assert len(result.close_times) == 2
    assert len(result.open_times) == 2


def test_simulator_close_stops_motion():
    clock = FakeClock()
    hardware = SimulatedHardware(1.0, 1.0, start="between", clock=clock)
    hardware.drive(Direction.CLOSE)
    hardware.close()
    clock.sleep(2.0)
    assert hardware.limits().mechanism_state == "BETWEEN LIMITS"
    assert hardware.closed


def test_stall_fault_prevents_motion():
    clock = FakeClock()
    hardware = SimulatedHardware(1.0, 1.0, start="between", fault="stall-close", clock=clock)
    hardware.drive(Direction.CLOSE)
    clock.sleep(2.0)
    assert hardware.limits().mechanism_state == "BETWEEN LIMITS"


def test_missing_limit_fault_hides_endpoint():
    clock = FakeClock()
    hardware = SimulatedHardware(1.0, 1.0, start="closed", fault="closed-limit-missing", clock=clock)
    assert not hardware.limits().closed_active


def test_both_limits_fault_reports_impossible_state():
    clock = FakeClock()
    hardware = SimulatedHardware(1.0, 1.0, fault="both-limits-active", clock=clock)
    state = hardware.limits()
    assert state.open_active and state.closed_active


def test_stalled_endurance_run_fails_and_stops(config):
    clock = FakeClock()
    hardware = SimulatedHardware(0.01, 0.01, start="open", fault="stall-close", clock=clock)
    result = Controller(hardware, config, clock=clock, sleeper=clock.sleep).run_test(1)
    assert result.result == "FAIL"
    assert "CLOSE limit not reached" in result.fault_reason
    assert hardware._direction is None


@pytest.mark.parametrize(
    ("fault", "start", "reason"),
    [
        ("stall-open", "closed", "OPEN limit not reached"),
        ("stall-close", "open", "CLOSE limit not reached"),
        ("open-limit-missing", "closed", "OPEN limit not reached"),
        ("closed-limit-missing", "open", "CLOSE limit not reached"),
        ("both-limits-active", "between", "Both limit switches are active"),
    ],
)
def test_each_fault_causes_expected_endurance_failure(config, fault, start, reason):
    clock = FakeClock()
    hardware = SimulatedHardware(0.01, 0.01, start=start, fault=fault, clock=clock)
    result = Controller(hardware, config, clock=clock, sleeper=clock.sleep).run_test(1)
    assert result.result == "FAIL"
    assert reason in result.fault_reason
