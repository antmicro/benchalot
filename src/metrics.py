from time import monotonic_ns
from subprocess import run
from logging import getLogger
from execution import execute_command

logger = getLogger(f"benchmarker.{__name__}")


def measure_time(commands):
    total = 0
    for command in commands:
        start = monotonic_ns()
        execute_command(command)
        total += monotonic_ns() - start
    return total / 1e9


def gather_stdout(commands):
    total = ""
    for command in commands:
        result = run(command, capture_output=True, shell=True)
        if result.returncode != 0:
            logger.critical(
                f"Subprocess '{command}' exited abnormally (exit code {result.returncode})"
            )
            exit(1)
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
            exit(1)
        total += result.stderr.decode("utf-8").strip()
    return total


def gather_exit_codes(commands):
    exit_codes = []
    for command in commands:
        result = execute_command(command)
        exit_codes.append(result)
    if len(commands) == 1:
        return exit_codes[0]
    return tuple(exit_codes)


def custom_metric(metric, commands):
    args = '" "'.join(commands)
    args = ' "' + args
    args += '"'
    result = run(metric + args, shell=True, capture_output=True)
    if result.returncode != 0:
        logger.critical(
            f"Subprocess '{metric}' exited abnormally (exit code {result.returncode})"
        )
        logger.critical(result.stderr.decode("utf-8").strip())
        exit(1)
    return result.stdout.decode("utf-8").strip()
