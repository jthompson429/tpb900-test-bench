from tpb9000_testbench.reporting import create_test_logger


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
