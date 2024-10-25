from time import monotonic_ns
from logging import getLogger
from benchmarker.execution import (
    execute_and_handle_output,
    handle_output,
    check_return_code,
    execute_command,
)
from collections import OrderedDict

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")

_FORMAT = "{name}.{stepno}"

def measure_time(commands: list[str]) -> OrderedDict:
    measurements = OrderedDict()
    for i, command in enumerate(commands):
        start = monotonic_ns()
        process = execute_command(command)
        process.wait()
        elapsed_time = monotonic_ns() - start
        measurements[_FORMAT.format(name="time",stepno=i)] = elapsed_time / 1e9
        handle_output(process)
    measurements["time"] = sum(measurements.values())
    if len(commands) == 1:
        return OrderedDict({"time": measurements["time"]})
    return measurements


def _gather_output(commands: list[str], output: str) -> OrderedDict:
    measurements = OrderedDict()
    for i, command in enumerate(commands):
        if output == "stdout":
            value = execute_and_handle_output(command, capture_stdout=True)
        elif output == "stderr":
            value = execute_and_handle_output(command, capture_stderr=True)
        try:
            value = float(value)
        except ValueError:
            pass
        measurements[_FORMAT.format(name=output, stepno=i)] = value
    try:
        measurements[output] = sum(measurements.values())
    except TypeError:
        measurements[output] = " ".join(measurements.values())
    if len(commands) == 1:
        return OrderedDict({output: measurements[output]})
    return measurements


def gather_stdout(commands: list[str]) -> OrderedDict:
    return _gather_output(commands,"stdout")


def gather_stderr(commands: list[str]) -> OrderedDict:
    return _gather_output(commands,"stderr")


def custom_metric(metric_command: str,metric_name:str, commands: list[str]) -> OrderedDict:
    for command in commands:
        execute_and_handle_output(command)
    process = execute_command(metric_command)
    output = handle_output(process, capture_stdout=True)
    result = process.wait()
    check_return_code(metric_command, result)
    measurements = OrderedDict()
    for i, line in enumerate(output.split("\n")):
        try:
            output = float(line)
        except ValueError:
            pass
        measurements[_FORMAT.format(name=metric_name, stepno=i)] = output
    try:
        measurements[metric_name] = sum(measurements.values())
    except TypeError:
        measurements[metric_name] = " ".join(measurements.values())
    if len(commands) == 1:
        return OrderedDict({metric_name: measurements[metric_name]})
    return measurements
