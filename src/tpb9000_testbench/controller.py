from __future__ import annotations

import logging
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .config import TestBenchConfig
from .hardware import Direction, Hardware, LimitState
from .reporting import RunProvenance, TestResult


class TestBenchFault(RuntimeError):
    pass


class OperatorAbort(KeyboardInterrupt):
    pass


class JogStopReason(Enum):
    LIMIT_REACHED = "limit reached"
    REQUESTED_DURATION_COMPLETE = "requested duration complete"


@dataclass(frozen=True)
class JogResult:
    elapsed_seconds: float
    reason: JogStopReason


@dataclass(frozen=True)
class DiagnosticReport:
    limits: LimitState
    initial_outputs_safe: bool
    outputs_safe_after_stop: bool

    @property
    def issues(self) -> tuple[str, ...]:
        issues = []
        if not self.initial_outputs_safe:
            issues.append("Motor outputs were active after initialization")
        if not self.outputs_safe_after_stop:
            issues.append("Motor outputs did not enter the stopped state")
        if self.limits.open_active and self.limits.closed_active:
            issues.append("Both limit switches are active")
        return tuple(issues)

    @property
    def passed(self) -> bool:
        return not self.issues


class Controller:
    def __init__(self, hardware: Hardware, config: TestBenchConfig, logger: logging.Logger | None = None,
                 clock: Callable[[], float] = time.monotonic, sleeper: Callable[[float], None] = time.sleep):
        self.hardware = hardware
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.clock = clock
        self.sleep = sleeper
        self.stop_event = threading.Event()

    def status(self) -> LimitState:
        return self.hardware.limits()

    def doctor(self) -> DiagnosticReport:
        initial_outputs_safe = self.hardware.motor_is_stopped()
        try:
            self.hardware.stop()
            limits = self.hardware.limits()
            outputs_safe_after_stop = self.hardware.motor_is_stopped()
            return DiagnosticReport(limits, initial_outputs_safe, outputs_safe_after_stop)
        finally:
            self.hardware.stop()

    def request_stop(self) -> None:
        self.stop_event.set()
        self.hardware.stop()

    def _validate(self, state: LimitState) -> None:
        if state.open_active and state.closed_active:
            raise TestBenchFault("Both limit switches are active")

    def move_until_limit(self, direction: Direction, timeout: float) -> float:
        started = self.clock()
        try:
            state = self.hardware.limits()
            self._validate(state)
            target_active = state.open_active if direction is Direction.OPEN else state.closed_active
            if target_active:
                return 0.0
            self.hardware.drive(direction)
            while True:
                if self.stop_event.is_set():
                    raise OperatorAbort("STOP requested")
                state = self.hardware.limits()
                self._validate(state)
                if (state.open_active if direction is Direction.OPEN else state.closed_active):
                    return self.clock() - started
                if self.clock() - started >= timeout:
                    raise TestBenchFault(f"{direction.value} limit not reached within {timeout:g} seconds")
                self.sleep(self.config.poll_interval_seconds)
        finally:
            self.hardware.stop()

    def jog(self, direction: Direction, duration: float | None = None) -> JogResult:
        safety_timeout = self.config.jog_timeout_seconds
        if duration is not None:
            if duration <= 0:
                raise ValueError("Jog duration must be greater than zero")
            if duration >= safety_timeout:
                raise ValueError(f"Jog duration must be shorter than the {safety_timeout:g}-second safety timeout")

        started = self.clock()
        try:
            state = self.hardware.limits()
            self._validate(state)
            target_active = state.open_active if direction is Direction.OPEN else state.closed_active
            if target_active:
                return JogResult(0.0, JogStopReason.LIMIT_REACHED)
            self.hardware.drive(direction)
            while True:
                if self.stop_event.is_set():
                    raise OperatorAbort("STOP requested")
                state = self.hardware.limits()
                self._validate(state)
                elapsed = self.clock() - started
                if (state.open_active if direction is Direction.OPEN else state.closed_active):
                    return JogResult(elapsed, JogStopReason.LIMIT_REACHED)
                if duration is not None and elapsed >= duration:
                    return JogResult(elapsed, JogStopReason.REQUESTED_DURATION_COMPLETE)
                if elapsed >= safety_timeout:
                    raise TestBenchFault(
                        f"{direction.value} jog reached the {safety_timeout:g}-second safety timeout"
                    )
                self.sleep(self.config.poll_interval_seconds)
        finally:
            self.hardware.stop()

    def run_test(self, cycles: int, provenance: RunProvenance | None = None) -> TestResult:
        if cycles <= 0:
            raise ValueError("cycles must be greater than zero")
        self.stop_event.clear()
        result = TestResult(cycles, provenance=provenance)
        self.logger.info("Test Started; Target Cycles: %d", cycles)
        if provenance:
            self.logger.info("Backend: %s", provenance.backend)
            self.logger.info("Hostname: %s", provenance.hostname)
            self.logger.info("Application Version: %s", provenance.application_version)
            self.logger.info("Configuration File: %s", provenance.configuration_file)
            if provenance.backend == "SIMULATION":
                self.logger.info("Simulation Start: %s; Fault: %s",
                                 provenance.simulation_start, provenance.simulation_fault)
            self.logger.info("Effective Configuration: %s",
                             json.dumps(provenance.effective_configuration, sort_keys=True))
        try:
            self._validate(self.hardware.limits())
            for cycle in range(1, cycles + 1):
                self.logger.info("Cycle %03d - Closing", cycle)
                close_time = self.move_until_limit(Direction.CLOSE, self.config.max_close_travel_seconds)
                result.close_times.append(close_time)
                self.logger.info("CLOSED Limit Reached - %.2f sec", close_time)
                self._pause(self.config.pause_after_close_seconds)
                self.logger.info("Cycle %03d - Opening", cycle)
                open_time = self.move_until_limit(Direction.OPEN, self.config.max_open_travel_seconds)
                result.open_times.append(open_time)
                self.logger.info("OPEN Limit Reached - %.2f sec", open_time)
                self._pause(self.config.pause_after_open_seconds)
                result.completed_cycles = cycle
                self.logger.info("Cycle %03d - PASS", cycle)
            result.result = "PASS"
        except OperatorAbort as exc:
            result.result, result.fault_reason = "ABORTED", str(exc)
            self.logger.warning("Test Aborted - %s", exc)
        except Exception as exc:
            result.result, result.fault_reason = "FAIL", str(exc)
            self.logger.exception("Test Failed - %s", exc)
        finally:
            self.hardware.stop()
            result.ended_at = datetime.now()
            self.logger.info("Test Complete; Passed Cycles: %d / %d; Result: %s",
                             result.completed_cycles, cycles, result.result)
        return result

    def _pause(self, seconds: float) -> None:
        deadline = self.clock() + seconds
        while self.clock() < deadline:
            if self.stop_event.is_set():
                raise OperatorAbort("STOP requested")
            self.sleep(min(self.config.poll_interval_seconds, max(0, deadline - self.clock())))
