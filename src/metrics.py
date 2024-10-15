from time import monotonic_ns
from subprocess import PIPE, Popen
from logging import getLogger
from execution import execute_and_handle_output, handle_output, check_return_code

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")


def measure_time(commands):
    total = 0
    for command in commands:
        start = monotonic_ns()
        process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
        process.wait()
        total += monotonic_ns() - start
        handle_output(process)
    return total / 1e9


def gather_stdout(commands):
    total = ""
    for command in commands:
        total += execute_and_handle_output(command, capture_stdout=True)
    return total


def gather_stderr(commands):
    total = ""
    for command in commands:
        total += execute_and_handle_output(command, capture_stderr=True)
    return total


def gather_exit_codes(commands):
    exit_codes = []
    for command in commands:
        process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
        result = process.wait()
        exit_codes.append(result)
        handle_output(process)
    if len(commands) == 1:
        return exit_codes[0]
    return tuple(exit_codes)


def custom_metric(metric, commands):
    for command in commands:
        execute_and_handle_output(command)
    process = Popen(metric, shell=True, stdout=PIPE, stderr=PIPE)
    output = handle_output(process, capture_stdout=True)
    result = process.wait()
    check_return_code(metric, result)
    try:
        output = float(output)
    except ValueError:
        pass
    return output
