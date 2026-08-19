from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class MotorConfig:
    rpwm_gpio: int
    lpwm_gpio: int
    right_enable_gpio: int
    left_enable_gpio: int
    pwm_frequency_hz: int
    duty_cycle: float
    open_uses_rpwm: bool


@dataclass(frozen=True)
class LimitConfig:
    open_gpio: int
    closed_gpio: int
    active_low: bool
    bounce_time_seconds: float


@dataclass(frozen=True)
class TestBenchConfig:
    max_cycles: int
    pause_after_close_seconds: float
    pause_after_open_seconds: float
    max_close_travel_seconds: float
    max_open_travel_seconds: float
    jog_timeout_seconds: float
    poll_interval_seconds: float
    motor: MotorConfig
    limits: LimitConfig
    log_directory: Path


def _positive(data: dict[str, Any], key: str) -> float:
    value = float(data[key])
    if value <= 0:
        raise ConfigurationError(f"{key} must be greater than zero")
    return value


def _nonnegative(data: dict[str, Any], key: str) -> float:
    value = float(data[key])
    if value < 0:
        raise ConfigurationError(f"{key} must not be negative")
    return value


def load_config(path: str | Path) -> TestBenchConfig:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
        motor = raw["motor"]
        limits = raw["limits"]
        logging = raw["logging"]
    except (OSError, TypeError, KeyError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot load {path}: {exc}") from exc

    duty = float(motor["duty_cycle"])
    if not 0 < duty <= 1:
        raise ConfigurationError("motor.duty_cycle must be in (0, 1]")
    pins = [int(motor[k]) for k in ("rpwm_gpio", "lpwm_gpio", "right_enable_gpio", "left_enable_gpio")]
    pins += [int(limits[k]) for k in ("open_gpio", "closed_gpio")]
    if len(pins) != len(set(pins)):
        raise ConfigurationError("Every configured GPIO must be unique")

    cycles = int(raw["max_cycles"])
    if cycles <= 0:
        raise ConfigurationError("max_cycles must be greater than zero")
    log_dir = Path(logging["directory"])
    if not log_dir.is_absolute():
        log_dir = (path.parent.parent / log_dir).resolve()

    return TestBenchConfig(
        max_cycles=cycles,
        pause_after_close_seconds=_nonnegative(raw, "pause_after_close_seconds"),
        pause_after_open_seconds=_nonnegative(raw, "pause_after_open_seconds"),
        max_close_travel_seconds=_positive(raw, "max_close_travel_seconds"),
        max_open_travel_seconds=_positive(raw, "max_open_travel_seconds"),
        jog_timeout_seconds=_positive(raw, "jog_timeout_seconds"),
        poll_interval_seconds=_positive(raw, "poll_interval_seconds"),
        motor=MotorConfig(**{**motor, "duty_cycle": duty}),
        limits=LimitConfig(**limits),
        log_directory=log_dir,
    )
