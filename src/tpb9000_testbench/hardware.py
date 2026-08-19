from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time
from collections.abc import Callable
from typing import Protocol

from .config import LimitConfig, MotorConfig


class Direction(Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"


@dataclass(frozen=True)
class LimitState:
    open_active: bool
    closed_active: bool

    @property
    def mechanism_state(self) -> str:
        if self.open_active and self.closed_active:
            return "FAULT: BOTH LIMITS ACTIVE"
        if self.open_active:
            return "OPEN"
        if self.closed_active:
            return "CLOSED"
        return "BETWEEN LIMITS"


class Hardware(Protocol):
    def limits(self) -> LimitState: ...
    def drive(self, direction: Direction) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...


class GpioHardware:
    """gpiozero adapter. Constructor leaves every motor output off."""

    def __init__(self, motor: MotorConfig, limits: LimitConfig):
        try:
            from gpiozero import Button, DigitalOutputDevice, PWMOutputDevice
        except ImportError as exc:
            raise RuntimeError("gpiozero is required on Raspberry Pi; install the 'pi' extra") from exc

        self._cfg = motor
        self._devices: list[object] = []
        try:
            self._rpwm = PWMOutputDevice(motor.rpwm_gpio, frequency=motor.pwm_frequency_hz, initial_value=0)
            self._devices.append(self._rpwm)
            self._lpwm = PWMOutputDevice(motor.lpwm_gpio, frequency=motor.pwm_frequency_hz, initial_value=0)
            self._devices.append(self._lpwm)
            self._ren = DigitalOutputDevice(motor.right_enable_gpio, initial_value=False)
            self._devices.append(self._ren)
            self._len = DigitalOutputDevice(motor.left_enable_gpio, initial_value=False)
            self._devices.append(self._len)
            # NC switch opens at the limit. A pull-up makes an open contact read high;
            # therefore active_low=true means 'pressed' is represented by !is_pressed.
            self._open = Button(limits.open_gpio, pull_up=True, bounce_time=limits.bounce_time_seconds)
            self._devices.append(self._open)
            self._closed = Button(limits.closed_gpio, pull_up=True, bounce_time=limits.bounce_time_seconds)
            self._devices.append(self._closed)
            self._active_low = limits.active_low
            self.stop()
        except Exception:
            for device in reversed(self._devices):
                device.close()
            raise

    def _active(self, button: object) -> bool:
        contact_closed = bool(getattr(button, "is_pressed"))
        return not contact_closed if self._active_low else contact_closed

    def limits(self) -> LimitState:
        return LimitState(self._active(self._open), self._active(self._closed))

    def drive(self, direction: Direction) -> None:
        self.stop()
        use_rpwm = (direction is Direction.OPEN) == self._cfg.open_uses_rpwm
        self._ren.on()
        self._len.on()
        (self._rpwm if use_rpwm else self._lpwm).value = self._cfg.duty_cycle

    def stop(self) -> None:
        self._rpwm.off()
        self._lpwm.off()
        self._ren.off()
        self._len.off()

    def close(self) -> None:
        self.stop()
        for device in reversed(self._devices):
            device.close()


class SimulatedHardware:
    """In-memory mechanism model. It never imports or accesses GPIO."""

    START_POSITIONS = {"open": 0.0, "between": 0.5, "closed": 1.0}

    def __init__(self, open_travel_seconds: float, close_travel_seconds: float,
                 start: str = "open", clock: Callable[[], float] = time.monotonic):
        if start not in self.START_POSITIONS:
            raise ValueError(f"Unknown simulated start position: {start}")
        if open_travel_seconds <= 0 or close_travel_seconds <= 0:
            raise ValueError("Simulated travel times must be greater than zero")
        self._open_travel = open_travel_seconds
        self._close_travel = close_travel_seconds
        self._position = self.START_POSITIONS[start]
        self._clock = clock
        self._direction: Direction | None = None
        self._last_update = clock()
        self.closed = False

    def _update(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last_update)
        if self._direction is Direction.OPEN:
            self._position -= elapsed / self._open_travel
        elif self._direction is Direction.CLOSE:
            self._position += elapsed / self._close_travel
        self._position = min(1.0, max(0.0, self._position))
        self._last_update = now

    def limits(self) -> LimitState:
        self._update()
        return LimitState(self._position <= 0.0, self._position >= 1.0)

    def drive(self, direction: Direction) -> None:
        self._update()
        self._direction = direction

    def stop(self) -> None:
        self._update()
        self._direction = None

    def close(self) -> None:
        self.stop()
        self.closed = True
