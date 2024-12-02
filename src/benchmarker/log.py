from logging import (
    getLogger,
    FileHandler,
    Formatter,
    INFO,
    DEBUG,
    StreamHandler,
    WARNING,
)
from tempfile import NamedTemporaryFile
from atexit import register
from typing import TextIO
from sys import stdout


logger = getLogger(f"benchmarker.{__name__}")


class FastLogger:
    def __init__(self, file: TextIO, verbose: bool):
        self.file = file
        self.verbose = verbose

    def write(self, text: str):
        self.file.write(text)
        if self.verbose:
            stdout.write(text)


def setup_benchmarker_logging(verbose: bool, debug: bool) -> None:
    """Setup loggers.

    Args:
        verbose: If true, set logging level to `INFO`.
        debug: If true, set logging level to `DEBUG`.
    """
    console = StreamHandler()
    console.setFormatter(
        Formatter("[%(asctime)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S")
    )
    console.setLevel(WARNING)
    getLogger().setLevel(WARNING)
    if verbose:
        console.setLevel(INFO)
        getLogger().setLevel(INFO)
    if debug:
        console.setLevel(DEBUG)
        getLogger().setLevel(DEBUG)
    getLogger().addHandler(console)
    benchmarker_formatter = Formatter(
        "[%(asctime)s][%(name)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S"
    )
    benchmarker_logger = getLogger("benchmarker")
    temp_log_file = NamedTemporaryFile(
        prefix="benchmarker-", suffix=".log", delete=False
    )
    benchmarker_handler = FileHandler(temp_log_file.name)
    benchmarker_handler.setFormatter(benchmarker_formatter)
    benchmarker_logger.addHandler(benchmarker_handler)
    benchmarker_logger.setLevel(DEBUG)
    register(crash_msg_log_file, temp_log_file.name)


def crash_msg_log_file(filename):
    """Print crash message.

    Args:
        filename: Name of the debug log file.
    """
    logger.critical(f"Benchmarker exited abnormally! Log files generated: {filename}.")
