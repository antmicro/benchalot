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
from sys import stderr, stdout


logger = getLogger(f"benchmarker.{__name__}")


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


def setup_command_logging(output_filename: str) -> None:
    """Setup `run` logger so that it writes command output to a file/`stdout`/`stderr`.

    Args:
        output_filename: Name of the file where output of commands will be written. If "STDERR", then output to `stderr`. If "STDOUT", then output to `stdout`.
    """
    handler: StreamHandler | FileHandler | None = None
    if output_filename == "STDERR":
        handler = StreamHandler(stream=stderr)
    elif output_filename == "STDOUT":
        handler = StreamHandler(stream=stdout)
    else:
        handler = FileHandler(output_filename)
    formatter = Formatter("%(message)s")
    handler.setFormatter(formatter)
    command_logger = getLogger("run")
    command_logger.addHandler(handler)
    command_logger.setLevel(INFO)


def crash_msg_log_file(filename):
    """Print crash message.

    Args:
        filename: Name of the debug log file.
    """
    logger.critical(f"Benchmarker exited abnormally! Log files generated: {filename}.")
