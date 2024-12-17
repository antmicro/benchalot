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


logger = getLogger(f"benchmarker.{__name__}")


class FastLogger:
    def __init__(self):
        """Simple logging class without the overhead of the built-in Python logger.

        Args:
            file: File object which will be used to save output.
            verbose: If true, print to `stdout`.
        """
        self.bar = None
        self.log_q_capacity = 10000
        self.log_q = [""] * self.log_q_capacity
        self.n_in_log_q = 0

    def set_file(self, file):
        """Set logging file, the FastLogger assumes that the file is opened.
        Args:
            file: File object which will be used to save output.
        """
        self.file = file

    def set_verbose(self, verbose):
        self.verbose = verbose

    def set_bar(self, bar):
        self.bar = bar
        size = os.get_terminal_size()
        self.max_lines = size.lines - 1
        print("\n" * (max_lines - 1))

    def write(self, text: str, save_to_file=False):
        """Write `text` to file and/or terminal."""
        if self.n_in_log_q >= self.log_q_capacity:
            self.flush()
        self.log_q[self.n_in_log_q] = text
        self.n_in_log_q += 1

        if save_to_file:
            assert self.file is not None
            self.file.write(text)

    def flush(self):
        if not self.bar:
            for i in range(self.n_in_log_q):
                print(self.log_q[i], end="")
            self.n_in_log_q = 0
        else:
            for i in range(self.n_in_log_q):
                self.bar.display(self.log_q[i], abs(self.bar.pos - self.max_lines + i))


fast_logger = FastLogger()


def setup_benchmarker_logging(verbose: bool, debug: bool) -> None:
    """Setup loggers.

    Args:
        verbose: If true, set logging level to `INFO`.
        debug: If true, set logging level to `DEBUG`.
    """
    fast_logger.set_verbose(verbose or debug)
    console = StreamHandler(stream=fast_logger)
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
