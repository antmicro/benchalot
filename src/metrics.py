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
