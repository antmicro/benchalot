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
from contextlib import contextmanager


logger = getLogger(f"benchmarker.{__name__}")


class FastConsole:
    def __init__(self):
        """Simple logging class without the overhead of the built-in Python logger.

        Args:
            file: File object which will be used to save output.
            verbose: If true, print to `stdout`.
        """
        self.bar = None
        self.capacity = 1024
        self.buffer = ""
        self.file_buffer = ""
        self.verbose = False
        self.file = None

    def set_verbose(self, verbose):
        self.verbose = verbose

    def set_bar(self, bar):
        self.bar = bar

    def write(self, text: str):
        """Write `text` to file and/or terminal."""
        if len(self.buffer) + len(text) >= self.capacity:
            self.flush()
        self.buffer += text

    @contextmanager
    def log_to_file(self, filename):
        if not filename:
            log_file_desc = "/dev/null"
        else:
            log_file_desc = filename
        with open(log_file_desc, "w") as log_file:
            self.file = log_file
            yield
        self.file = None

    def log(self, msg):
        if self.verbose:
            self.write(msg)
        self.file.write(msg)

    def print(self, text, end="\n"):
        self.write(text + end)
        self.flush()

    def flush(self):
        # simplified implementation of self.bar.write
        if self.bar:
            self.bar.write(self.buffer, end="")
        else:
            print(self.buffer, end="")
        self.buffer = ""


console = FastConsole()


def setup_benchmarker_logging(verbose: bool, debug: bool) -> None:
    """Setup loggers.

    Args:
        verbose: If true, set logging level to `INFO`.
        debug: If true, set logging level to `DEBUG`.
    """
    global console
    console.set_verbose(verbose or debug)
    consoleHandler = StreamHandler(stream=console)
    consoleHandler.setFormatter(
        Formatter("[%(asctime)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S")
    )
    consoleHandler.setLevel(WARNING)
    getLogger().setLevel(WARNING)
    if verbose:
        consoleHandler.setLevel(INFO)
        getLogger().setLevel(INFO)
    if debug:
        consoleHandler.setLevel(DEBUG)
        getLogger().setLevel(DEBUG)
    getLogger().addHandler(consoleHandler)
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
