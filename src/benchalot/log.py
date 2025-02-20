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
import sys
from statistics import mean
from time import monotonic_ns
import asyncio


logger = getLogger(f"benchalot.{__name__}")


class Bar:
    def __init__(self, n_iter):
        self.n_iter = n_iter
        self.curr_iter = 0
        self.saved_pos = False

        self.time_start = monotonic_ns()
        self.time_prev = monotonic_ns()

        self.time_history = []
        self.time_average = 0

        self.bar = "".join([" "] * 20)
        self.title = ""

    async def constatnly_refresh(self):
        while True:
            completion_rate = self.curr_iter / self.n_iter * 100
            if self.saved_pos:
                self.restore_cursor_pos()

            if self.time_history:
                time_estimated_completion = self.n_iter * self.time_average - (
                    monotonic_ns() - self.time_start
                )
            else:
                time_estimated_completion = 0
            self.save_cursor_pos()
            sys.stdout.write(
                f"{self.title}:[{self.bar}]{completion_rate:.0f}% {time_estimated_completion/1e9:.2f}s"
            )
            sys.stdout.flush()

            if self.curr_iter >= self.n_iter:
                self.erase_bar()
                break
            await asyncio.sleep(0.1)

    def progress(self):
        self.curr_iter += 1

        time_curr = monotonic_ns()
        time_elapsed = time_curr - self.time_prev
        self.time_history.append(time_elapsed)
        self.time_average = mean(self.time_history)
        self.time_prev = time_curr

        completion_rate = self.curr_iter / self.n_iter * 100
        bar_width = 20
        bar = [" "] * bar_width
        tick_rate = 100 / bar_width
        progress = int(completion_rate / tick_rate)
        for i in range(progress):
            bar[i] = "#"
        self.bar = "".join(bar)
        if self.curr_iter >= self.n_iter:
            self.erase_bar()

    def save_cursor_pos(self):
        sys.stdout.write("\033[s")
        sys.stdout.flush()
        self.saved_pos = True

    def restore_cursor_pos(self):
        sys.stdout.write("\033[u")
        sys.stdout.flush()
        self.saved_pos = False

    def write(self, buffer):
        self.erase_bar()
        sys.stdout.write(buffer)
        sys.stdout.flush()

    def erase_bar(self):
        if self.saved_pos:
            self.restore_cursor_pos()
            sys.stdout.write("\033[0K")
            sys.stdout.flush()

    def set_description(self, title):
        self.title = title


class FastConsole:
    def __init__(self):
        """
        Simple logging class without the overhead of the built-in Python logger.
        It's main purpose is to allow provide live progress bar with very small performance penalty.
        It is achieved by using string buffer.
        """
        self._bar = False

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
        with open(log_file_desc, "a") as log_file:
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
                bar = Bar(n_iter)
                self._bar = bar
            else:
                raise RuntimeError(
                    "bar() cannot be called with while other bar still exists."
                )
            yield bar
        finally:
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
            self._bar.write(self.buffer)
        else:
            print(self.buffer, end="")
        self.buffer = ""


console = FastConsole()


def setup_benchalot_logging(verbose: bool, debug: bool) -> None:
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
    benchalot_formatter = Formatter(
        "[%(asctime)s][%(name)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S"
    )
    benchalot_logger = getLogger("benchalot")
    temp_log_file = NamedTemporaryFile(prefix="benchalot-", suffix=".log", delete=False)
    benchalot_handler = FileHandler(temp_log_file.name)
    benchalot_handler.setFormatter(benchalot_formatter)
    benchalot_logger.addHandler(benchalot_handler)
    benchalot_logger.setLevel(DEBUG)
    register(crash_msg_log_file, temp_log_file.name)


def crash_msg_log_file(filename):
    """Print crash message.

    Args:
        filename: Name of the debug log file.
    """
    logger.critical(f"benchalot exited abnormally! Log files generated: {filename}.")
