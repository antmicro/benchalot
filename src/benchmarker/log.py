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
from tqdm import tqdm


logger = getLogger(f"benchmarker.{__name__}")


class FastConsole:
    def __init__(self):
        """
        Simple logging class without the overhead of the built-in Python logger.
        It's main purpose is to allow provide live progress bar with very small performance penalty.
        It is achieved by using string buffer.
        """
        self._bar = None
        self.capacity = 1024
        self.buffer = ""
        self.verbose = False
        self.file = None

    def set_verbose(self, verbose):
        """Whether to print command output to `stdout`"""
        self.verbose = verbose

    def write(self, text: str):
        """Write `text` to buffer. Flush the buffer if it is full."""
        if len(self.buffer) + len(text) >= self.capacity:
            self.flush()
        self.buffer += text

    @contextmanager
    def log_to_file(self, filename: str | None):
        """
        Convenience function for logging command output to a file.

        Args:
            filename: name of the logfile.  If `None`, the output will redirected to `/dev/null`
        """
        if not filename:
            log_file_desc = "/dev/null"
        else:
            log_file_desc = filename
        with open(log_file_desc, "w") as log_file:
            self.file = log_file
            yield
        self.file = None

    @contextmanager
    def bar(self, n_iter: int):
        """
        Function used to create live progress bar.
        Caller of the function is responsible for tracking the bar progress.

        Args:
            n_iter: total number of iterations.
        """
        try:
            if not self._bar:
                bar = tqdm(total=n_iter, leave=False, mininterval=1)
                self._bar = bar
            else:
                raise RuntimeError(
                    "bar() cannot be called with while other bar still exists."
                )
            yield self._bar
        finally:
            self._bar.close()
            self._bar = None

    def log_command_output(self, text: str):
        """Print command output to stdout and/or save it to a file"""
        if self.verbose:
            self.write(text)
        self.file.write(text)

    def print(self, text="", end="\n"):
        """Print text to stdout, above the live progress bar"""
        self.write(text + end)
        self.flush()

    def flush(self) -> None:
        """
        If the bar is present print the buffer above the bar,
        else simply print it to stdout.
        """
        if self._bar:
            self._bar.write(self.buffer, end="")
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
