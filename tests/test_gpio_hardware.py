import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin

from tpb9000_testbench.hardware import Direction, GpioHardware


@pytest.fixture
def mock_pin_factory():
    previous = Device.pin_factory
    factory = MockFactory(pin_class=MockPWMPin)
    Device.pin_factory = factory
    try:
        yield factory
    finally:
        factory.close()
        Device.pin_factory = previous


@pytest.fixture
def gpio_hardware(config, mock_pin_factory):
    hardware = GpioHardware(config.motor, config.limits)
    try:
        yield hardware
    finally:
        hardware.close()


def test_startup_leaves_all_motor_outputs_safe(config, gpio_hardware, mock_pin_factory):
    assert gpio_hardware.motor_is_stopped()
    assert mock_pin_factory.pin(config.motor.rpwm_gpio).state == 0
    assert mock_pin_factory.pin(config.motor.lpwm_gpio).state == 0
    assert mock_pin_factory.pin(config.motor.right_enable_gpio).state == 0
    assert mock_pin_factory.pin(config.motor.left_enable_gpio).state == 0


def test_nc_limit_sense_is_fail_aware(config, gpio_hardware):
    # Pull-up/high represents an open NC contact or broken wire: limit active.
    assert gpio_hardware.limits().open_active
    assert gpio_hardware.limits().closed_active

    gpio_hardware._open.pin.drive_low()
    gpio_hardware._closed.pin.drive_low()
    assert not gpio_hardware.limits().open_active
    assert not gpio_hardware.limits().closed_active

    gpio_hardware._open.pin.drive_high()
    assert gpio_hardware.limits().open_active
    assert not gpio_hardware.limits().closed_active


def test_open_direction_uses_configured_pwm_channel(config, gpio_hardware, mock_pin_factory):
    gpio_hardware.drive(Direction.OPEN)
    expected_rpwm = config.motor.duty_cycle if config.motor.open_uses_rpwm else 0
    expected_lpwm = 0 if config.motor.open_uses_rpwm else config.motor.duty_cycle
    assert mock_pin_factory.pin(config.motor.rpwm_gpio).state == expected_rpwm
    assert mock_pin_factory.pin(config.motor.lpwm_gpio).state == expected_lpwm
    assert mock_pin_factory.pin(config.motor.right_enable_gpio).state == 1
    assert mock_pin_factory.pin(config.motor.left_enable_gpio).state == 1


def test_close_direction_uses_opposite_pwm_channel(config, gpio_hardware, mock_pin_factory):
    gpio_hardware.drive(Direction.CLOSE)
    expected_rpwm = 0 if config.motor.open_uses_rpwm else config.motor.duty_cycle
    expected_lpwm = config.motor.duty_cycle if config.motor.open_uses_rpwm else 0
    assert mock_pin_factory.pin(config.motor.rpwm_gpio).state == expected_rpwm
    assert mock_pin_factory.pin(config.motor.lpwm_gpio).state == expected_lpwm


def test_stop_disables_pwm_and_both_enables(config, gpio_hardware, mock_pin_factory):
    gpio_hardware.drive(Direction.OPEN)
    gpio_hardware.stop()
    assert mock_pin_factory.pin(config.motor.rpwm_gpio).state == 0
    assert mock_pin_factory.pin(config.motor.lpwm_gpio).state == 0
    assert mock_pin_factory.pin(config.motor.right_enable_gpio).state == 0
    assert mock_pin_factory.pin(config.motor.left_enable_gpio).state == 0
    assert gpio_hardware.motor_is_stopped()


def test_switching_direction_stops_old_pwm_first(config, gpio_hardware, mock_pin_factory):
    gpio_hardware.drive(Direction.OPEN)
    gpio_hardware.drive(Direction.CLOSE)
    active_pwm = config.motor.rpwm_gpio if not config.motor.open_uses_rpwm else config.motor.lpwm_gpio
    inactive_pwm = config.motor.lpwm_gpio if not config.motor.open_uses_rpwm else config.motor.rpwm_gpio
    assert mock_pin_factory.pin(active_pwm).state == config.motor.duty_cycle
    assert mock_pin_factory.pin(inactive_pwm).state == 0


def test_close_leaves_motor_pins_safe(config, mock_pin_factory):
    hardware = GpioHardware(config.motor, config.limits)
    pins = [
        mock_pin_factory.pin(config.motor.rpwm_gpio),
        mock_pin_factory.pin(config.motor.lpwm_gpio),
        mock_pin_factory.pin(config.motor.right_enable_gpio),
        mock_pin_factory.pin(config.motor.left_enable_gpio),
    ]
    hardware.drive(Direction.OPEN)
    hardware.close()
    assert [pin.state for pin in pins] == [0, 0, 0, 0]
