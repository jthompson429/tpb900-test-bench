from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime

from .config import TestBenchConfig
from .hardware import Direction, Hardware, LimitState
from .reporting import TestResult


class TestBenchFault(RuntimeError):
    pass


class OperatorAbort(KeyboardInterrupt):
    pass


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

    def jog(self, direction: Direction, duration: float | None = None) -> float:
        timeout = min(duration, self.config.jog_timeout_seconds) if duration is not None else self.config.jog_timeout_seconds
        return self.move_until_limit(direction, timeout)

    def run_test(self, cycles: int) -> TestResult:
        if cycles <= 0:
            raise ValueError("cycles must be greater than zero")
        self.stop_event.clear()
        result = TestResult(cycles)
        self.logger.info("Test Started; Target Cycles: %d", cycles)
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
