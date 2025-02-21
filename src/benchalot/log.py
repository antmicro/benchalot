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
from time import monotonic_ns


logger = getLogger(f"benchalot.{__name__}")


class Bar:
    def __init__(self, n_iter):
        self.n_iter = n_iter
        self.curr_iter = 0

        self.bar = "".join([" "] * 50)
        self.title = ""
        self.spinner_state = 0

        self.start_time = monotonic_ns()

        self.prev_tic = monotonic_ns()

        self.redraw_bar = True
        self._write_now("\33[?25l")  # hide cursor

    def _write_now(self, txt):
        sys.stdout.write(txt)
        sys.stdout.flush()

    def refresh(self):
        time_curr = monotonic_ns()

        if self.redraw_bar:
            self.erase()
            self._write_now(f"{self.title}:[{self.bar}]")
            self.redraw_bar = False

        anim = ["|", "/", "-", "\\"]
        time_string = ""

        time_elapsed = time_curr - self.start_time

        time_string = f" {time_elapsed/1e9:.1f}s"

        self.save_cursor_pos()
        self._write_now(f"[{anim[self.spinner_state]}{time_string}]")

        self.restore_cursor_pos()

        if (time_curr - self.prev_tic) / 1e6 >= 100.0:
            self.spinner_state = (self.spinner_state + 1) % len(anim)
            self.prev_tic = time_curr

    def progress(self):
        self.curr_iter += 1
        completion_rate = self.curr_iter / self.n_iter * 100
        tick_rate = 100 / len(self.bar)
        progress = int(completion_rate / tick_rate)
        bar = [" "] * len(self.bar)
        for i in range(progress):
            bar[i] = "#"
        self.bar = "".join(bar)
        self.redraw_bar = True

    def save_cursor_pos(self):
        self._write_now("\033[s")

    def restore_cursor_pos(self):
        self._write_now("\033[u")

    def write(self, buffer):
        self.erase()
        self._write_now(buffer)
        self.redraw_bar = True

    def erase(self):
        self._write_now("\33[2K")  # erase entire line
        self._write_now("\33[0G")  # move cursor to the first column

    def set_description(self, title):
        self.title = title
        self.redraw_bar = True

    def __del__(self):
        self._write_now("\33[?25h")  # show cursor again


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
            self._bar.erase()
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
