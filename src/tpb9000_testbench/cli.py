from __future__ import annotations

import argparse
import signal
import sys
from dataclasses import replace

from .config import ConfigurationError, load_config
from .controller import Controller, OperatorAbort, TestBenchFault
from .hardware import Direction, GpioHardware, SimulatedHardware
from .reporting import create_test_logger, save_summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="TPB9000 feeder-cover test bench")
    p.add_argument("--config", default="config/testbench.yaml")
    p.add_argument("--simulate", action="store_true",
                   help="use the in-memory mechanism model; never access GPIO")
    p.add_argument("--simulate-start", choices=("open", "between", "closed"), default="open",
                   help="initial mechanism position in simulation (default: open)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show limit and motor state")
    for name in ("jog-open", "jog-close"):
        jog = sub.add_parser(name, help=f"move cautiously toward {name[4:].upper()}")
        jog.add_argument("--seconds", type=float, help="shorter duration; default is configured safety timeout")
    test = sub.add_parser("test", help="run automated endurance cycles")
    test.add_argument("--cycles", type=int)
    return p


def print_status(controller: Controller) -> None:
    state = controller.status()
    print("TPB9000 Test Bench\n")
    print(f"OPEN limit:     {'active' if state.open_active else 'inactive'}")
    print(f"CLOSED limit:   {'active' if state.closed_active else 'inactive'}")
    print(f"Mechanism state: {state.mechanism_state}\nMotor: STOPPED")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    hardware = None
    controller = None
    try:
        config = load_config(args.config)
        if args.simulate:
            sim = config.simulation
            hardware = SimulatedHardware(sim.open_travel_seconds, sim.close_travel_seconds,
                                         start=args.simulate_start)
            config = replace(config, pause_after_close_seconds=sim.endpoint_pause_seconds,
                             pause_after_open_seconds=sim.endpoint_pause_seconds)
            print("SIMULATION MODE - no GPIO will be accessed")
        else:
            hardware = GpioHardware(config.motor, config.limits)
        controller = Controller(hardware, config)
        def stop_now(_signum: int, _frame: object) -> None:
            controller.request_stop()
        signal.signal(signal.SIGINT, stop_now)
        signal.signal(signal.SIGTERM, stop_now)
        print_status(controller)
        if args.command == "status":
            return 0
        if args.command.startswith("jog-"):
            direction = Direction.OPEN if args.command == "jog-open" else Direction.CLOSE
            elapsed = controller.jog(direction, args.seconds)
            print(f"Stopped after {elapsed:.2f} sec")
            return 0
        logger, log_path = create_test_logger(config.log_directory)
        controller.logger = logger
        result = controller.run_test(args.cycles or config.max_cycles)
        summary = save_summary(result, log_path)
        print(f"Log: {log_path}\nSummary: {summary}")
        return 0 if result.result == "PASS" else 2
    except (ConfigurationError, TestBenchFault, OperatorAbort, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if hardware is not None:
            hardware.close()


if __name__ == "__main__":
    raise SystemExit(main())
