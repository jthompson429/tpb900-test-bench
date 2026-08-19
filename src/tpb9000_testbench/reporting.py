from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean


@dataclass
class TestResult:
    requested_cycles: int
    started_at: datetime = field(default_factory=datetime.now)
    completed_cycles: int = 0
    close_times: list[float] = field(default_factory=list)
    open_times: list[float] = field(default_factory=list)
    result: str = "RUNNING"
    fault_reason: str | None = None
    ended_at: datetime | None = None

    def summary(self) -> dict:
        def stats(values: list[float]) -> dict[str, float | None]:
            return {"average": mean(values) if values else None, "minimum": min(values) if values else None,
                    "maximum": max(values) if values else None}
        end = self.ended_at or datetime.now()
        return {
            "requested_cycles": self.requested_cycles,
            "completed_cycles": self.completed_cycles,
            "passed_cycles": self.completed_cycles,
            "failed_cycles": 1 if self.result == "FAIL" else 0,
            "duration_seconds": (end - self.started_at).total_seconds(),
            "close_travel_seconds": stats(self.close_times),
            "open_travel_seconds": stats(self.open_times),
            "fault_reason": self.fault_reason,
            "result": self.result,
            "started_at": self.started_at.isoformat(),
            "ended_at": end.isoformat(),
        }


def create_test_logger(directory: Path) -> tuple[logging.Logger, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"test-{stamp}.log"
    logger = logging.getLogger(f"tpb9000.{stamp}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.FileHandler(path), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger, path


def save_summary(result: TestResult, log_path: Path) -> Path:
    path = log_path.with_name(log_path.stem + "-summary.json")
    path.write_text(json.dumps(result.summary(), indent=2) + "\n")
    return path
