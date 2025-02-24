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
from time import monotonic


logger = getLogger(f"benchalot.{__name__}")


class Bar:
    def __init__(self, n_iter):
        self.n_iter = n_iter
        self.curr_iter = 0

        self.bar = "".join(["·"] * 20)
        self.title = ""
        self.anim = ["|", "/", "-", "\\"]
        self.spinner_state = 0

        self.start_time = monotonic()
        self.prev_tic = monotonic()

        self.redraw_bar = True
        self._write_impl("\33[?25l")  # hide cursor
        self.total_drawing_time = 0

    def _write_impl(self, txt):
        sys.stdout.write(txt)

    def _flush_impl(self):
        sys.stdout.flush()

    def refresh(self):
        time_curr = monotonic()
        if (time_curr - self.prev_tic) >= 0.100:
            buffer = ""
            if self.redraw_bar:
                self.erase()
                buffer += f"{self.title} [{self.bar}]"
                self.redraw_bar = False
            time_elapsed = time_curr - self.start_time
            buffer += "\033[s"  # save cursor position
            buffer += f"  {self.curr_iter}/{self.n_iter}  [{self.anim[self.spinner_state]} {time_elapsed:.1f}s]"
            buffer += "\033[u"  # restore cursor position
            self.spinner_state = (self.spinner_state + 1) % len(self.anim)
            self.prev_tic = time_curr
            self._write_impl(buffer)
            self._flush_impl()
        self.total_drawing_time += monotonic() - time_curr

    def progress(self):
        self.curr_iter += 1
        completion_rate = self.curr_iter / self.n_iter * 100
        tick_rate = 100 / len(self.bar)
        progress = int(completion_rate / tick_rate)
        bar = ["·"] * len(self.bar)
        for i in range(progress):
            bar[i] = "█"
        self.bar = "".join(bar)
        self.redraw_bar = True
        logger.debug(f"Drawing live progress bar took: {self.total_drawing_time:.2f}s")

    def write(self, buffer):
        self.erase()
        self._write_impl(buffer)
        self.redraw_bar = True

    def erase(self):
        self._write_impl("\33[2K")  # erase entire line
        self._write_impl("\33[0G")  # move cursor to the first column

    def set_description(self, title):
        self.title = title
        self.redraw_bar = True

    def __del__(self):
        self._write_impl("\33[?25h")  # show cursor again
        self._flush_impl()


class FastConsole:
    def __init__(self):
        """
        Simple logging class without the overhead of the built-in Python logger.
        It's main purpose is to allow provide live progress bar with very small performance penalty.
        It is achieved by using string buffer.
        """
        self._bar = None
        self.verbose = False
        self.file = None

    def set_verbose(self, verbose):
        """Whether to print command output to `stdout`"""
        self.verbose = verbose

    def write(self, text: str):
        """Write `text` to terminal. If a bar is present, display it above the bar."""
        if self._bar:
            self._bar.write(text)
        else:
            print(text, end="")

    @contextmanager
    def log_to_file(self, filename: str | None):
        """
        Convenience function for logging command output to a file.

        Args:
            filename: name of the logfile.
        """
        if not filename:
            yield
        else:
            with open(filename, "a") as log_file:
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
        if self.file:
            self.file.write(text)

    def print(self, text="", end="\n"):
        """Print text to stdout, above the live progress bar"""
        self.write(text + end)

    def flush(self) -> None:
        """Left here for compatiblity reasons"""
        pass


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
