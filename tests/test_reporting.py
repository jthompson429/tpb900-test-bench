from tpb9000_testbench.reporting import TestResult as RunResult
from tpb9000_testbench.reporting import build_run_provenance, create_test_logger


def test_back_to_back_runs_get_unique_log_paths(tmp_path):
    first_logger, first_path = create_test_logger(tmp_path)
    second_logger, second_path = create_test_logger(tmp_path)
    try:
        assert first_path != second_path
        assert first_path.exists()
        assert second_path.exists()
    finally:
        for logger in (first_logger, second_logger):
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


def test_provenance_snapshot_is_json_ready(config):
    provenance = build_run_provenance(
        config, "config/testbench.yaml", backend="GPIO", hostname="test-bench",
    )
    summary = RunResult(1, provenance=provenance).summary()
    assert summary["provenance"]["backend"] == "GPIO"
    assert summary["provenance"]["hostname"] == "test-bench"
    assert summary["provenance"]["simulation_fault"] is None
    assert isinstance(summary["provenance"]["effective_configuration"]["log_directory"], str)
