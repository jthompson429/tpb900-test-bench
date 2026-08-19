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
