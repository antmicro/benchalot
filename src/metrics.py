from time import monotonic_ns
from subprocess import run, DEVNULL
from logging import getLogger

logger = getLogger(f"benchmarker.{__name__}")


def measure_time(commands):
    total = 0
    for command in commands:
        start = monotonic_ns()
        result = run(command, shell=True, stdout=DEVNULL, stderr=DEVNULL)
        total += monotonic_ns() - start
        if result.returncode != 0:
            logger.critical(
                f"Subprocess '{command}' exited abnormally (exit code {result.returncode})"
            )
            logger.critical(result.stderr.decode("utf-8").strip())
    return total / 1e9


def gather_stdout(commands):
    total = ""
    for command in commands:
        result = run(command, shell=True, capture_output=True)
        if result.returncode != 0:
            logger.critical(
                f"Subprocess '{command}' exited abnormally (exit code {result.returncode})"
            )
            logger.critical(result.stderr.decode("utf-8").strip())
        total += result.stdout.decode("utf-8").strip()
    return total


def gather_stderr(commands):
    total = ""
    for command in commands:
        result = run(command, shell=True, capture_output=True)
        if result.returncode != 0:
            logger.critical(
                f"Subprocess '{command}' exited abnormally (exit code {result.returncode})"
            )
            logger.critical(result.stderr.decode("utf-8").strip())
        total += result.stderr.decode("utf-8").strip()
    return total


def gather_exit_codes(commands):
    exit_codes = []
    for command in commands:
        result = run(command, shell=True, stdout=DEVNULL, stderr=DEVNULL)
        exit_codes.append(result.returncode)
    if len(commands) == 1:
        return exit_codes[0]
    return tuple(exit_codes)
