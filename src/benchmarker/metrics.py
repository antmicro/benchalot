from time import monotonic_ns
from logging import getLogger
from benchmarker.execution import (
    execute_and_handle_output,
    handle_output,
    check_return_code,
    execute_command,
)
from typing import Literal
from io import StringIO
from csv import DictReader

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")

_FORMAT = "{name}.{stage}"


def measure_time(benchmarks: dict[str, list[str]]) -> dict:
    def _measure_stage_time(commands: list[str]) -> float:
        elapsed_time = 0.0
        for command in commands:
            start = monotonic_ns()
            process = execute_command(command)
            process.wait()
            elapsed_time += monotonic_ns() - start
            handle_output(process)
        return elapsed_time / 1e9

    measurements = dict()
    for stage, commands in benchmarks.items():
        measurements[_FORMAT.format(name="time", stage=stage)] = _measure_stage_time(
            commands
        )
    measurements["time"] = sum(measurements.values())
    if len(benchmarks) == 1:
        return {"time": measurements["time"]}
    return measurements


def _gather_output(
    benchmarks: dict[str, list[str]], output: Literal["stderr", "stdout"]
) -> dict:
    def _gather_stage_output(commands: list[str]) -> str | float:
        total = ""
        for command in commands:
            if output == "stdout":
                total += execute_and_handle_output(command, capture_stdout=True)
            elif output == "stderr":
                total += execute_and_handle_output(command, capture_stderr=True)
        try:
            return float(total)
        except ValueError:
            pass
        return total

    measurements = dict()
    total_float = 0.0
    total_str = ""
    output_float = True
    for name, command in benchmarks.items():
        value = _gather_stage_output(command)
        measurements[_FORMAT.format(name=output, stage=name)] = value
        if type(value) is float:
            total_float += value
        else:
            output_float = False
        total_str += str(value)
    if output_float:
        measurements[output] = total_float
    else:
        measurements[output] = total_str
    if len(benchmarks) == 1:
        return {output: measurements[output]}
    return measurements


def gather_stdout(benchmarks: dict[str, list[str]]) -> dict:
    return _gather_output(benchmarks, "stdout")


def gather_stderr(benchmarks: dict[str, list[str]]) -> dict:
    return _gather_output(benchmarks, "stderr")


def custom_metric(
    metric_command: str, metric_name: str, benchmarks: dict[str, list[str]]
) -> dict:
    for name, commands in benchmarks.items():
        for command in commands:
            execute_and_handle_output(command)
    process = execute_command(metric_command)
    output = handle_output(process, capture_stdout=True)
    result = process.wait()
    check_return_code(metric_command, result)
    if len(output.splitlines()) == 1:
        try:
            output = float(output)
        except ValueError:
            pass
        return {metric_name: output}

    output_stream = StringIO(output)
    reader = DictReader(output_stream)
    tmp_dict = {}
    for row in reader:
        tmp_dict = row
    output_dict = {}
    total_float = 0.0
    total_str = ""
    output_float = True
    for key in tmp_dict:
        value = tmp_dict[key]
        total_str += " " + value
        try:
            value = float(value)
        except ValueError:
            pass
        if type(value) is float:
            total_float += value
        else:
            output_float = False
        output_dict[_FORMAT.format(name=metric_name, stage=key)] = value
    if output_float:
        output_dict[metric_name] = total_float
    else:
        output_dict[metric_name] = total_str
    return output_dict
