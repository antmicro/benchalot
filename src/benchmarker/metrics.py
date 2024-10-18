from time import monotonic_ns
from logging import getLogger
from benchmarker.execution import (
    execute_and_handle_output,
    handle_output,
    check_return_code,
    execute,
)

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")


def measure_time(commands):
    total = 0
    for command in commands:
        start = monotonic_ns()
        process = execute(command)
        process.wait()
        total += monotonic_ns() - start
        handle_output(process)
    return total / 1e9


def gather_stdout(commands):
    total = ""
    for command in commands:
        total += execute_and_handle_output(command, capture_stdout=True)
    try:
        total = float(total)
    except ValueError:
        pass
    return total


def gather_stderr(commands):
    total = ""
    for command in commands:
        total += execute_and_handle_output(command, capture_stderr=True)
    try:
        total = float(total)
    except ValueError:
        pass
    return total


def custom_metric(metric, commands):
    for command in commands:
        execute_and_handle_output(command)
    process = execute(metric)
    output = handle_output(process, capture_stdout=True)
    result = process.wait()
    check_return_code(metric, result)
    try:
        output = float(output)
    except ValueError:
        pass
    return output
