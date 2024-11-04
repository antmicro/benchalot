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
from benchmarker.structs import BenchmarkResult

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")



def measure_time(benchmarks: dict[str, list[str]]) -> Result:
    """Measure execution time of the commands.

    Args:
        benchmarks: Commands divided into stages.

    Returns:
        dict: Containing execution time of each stage and total execution time.
    """
    has_failed = False
    def _measure_stage_time(commands: list[str]) -> float:
        nonlocal has_failed
        elapsed_time = 0.0
        for command in commands:
            start = monotonic_ns()
            process = execute_command(command)
            process.wait()
            elapsed_time += monotonic_ns() - start
            handle_output(process)
            success = check_return_code(command)
            if not success:
                has_failed = True
        return elapsed_time / 1e9

    measurements = dict()
    for stage, commands in benchmarks.items():
        measurements[stage] = _measure_stage_time(
            commands
        )
    measurements["total"] = sum(measurements.values())
    if len(benchmarks) == 1:
        measurements = {"total": measurements["total"]}
    result = BenchmarkResult("time", has_failed, measurements)
    return result


def _gather_output(
    benchmarks: dict[str, list[str]], output: Literal["stderr", "stdout"]
) -> BenchmarkResult:
    """Gather `stdout` or `stderr` of each command in each stage.

    Args:
        benchmarks: Commands divided into stages.
        output: Set  to "stderr" to gather `stderr` or set to "stdout" to gather `stdout`.

    Returns:
        dict: Containing `stderr` or `stdout` of each stage and their total. If possible, output will be converted to float.
    """
    has_failed = False
    def _gather_stage_output(commands: list[str]) -> str | float:
        nonlocal has_failed
        total = ""
        for command in commands:
            success = True
            ret = ""
            if output == "stdout":
                ret, success = execute_and_handle_output(command, capture_stdout=True)
            elif output == "stderr":
                ret, success = execute_and_handle_output(command, capture_stderr=True)
            total += ret

            if not success:
                has_failed = False
        try:
            return float(total)
        except ValueError:
            pass
        return total

    measurements = dict()
    total_float = 0.0
    total_str = ""
    output_float = True
    for stage, command in benchmarks.items():
        value = _gather_stage_output(command)
        measurements[stage] = value
        if type(value) is float:
            total_float += value
        else:
            output_float = False
        total_str += str(value)
    if output_float:
        measurements["total"] = total_float
    else:
        measurements["total"] = total_str
    if len(benchmarks) == 1:
        measurements = {"total": measurements["total"]}, success
    return measurements, success


def gather_stdout(benchmarks: dict[str, list[str]]) -> tuple(dict,bool):
    """Calls `_gather_output` with `output` set to "stdout"."""
    return _gather_output(benchmarks, "stdout")


def gather_stderr(benchmarks: dict[str, list[str]]) -> tuple(dict,bool):
    """Calls `_gather_output` with `output` set to "stderr"."""
    return _gather_output(benchmarks, "stderr")


def custom_metric(
    metric_command: str, metric_name: str, benchmarks: dict[str, list[str]]
) -> tuple(dict, bool):
    """Execute all the benchmark commands, then execute custom metric command and process its output.
    If output has more than one line, treat output as csv file, with each column representing separate stage.
    Sum stages under `metric_name`.

    Args:
        metric_command: Command to be executed as custom metric.
        metric_name: Custom metric's name.
        benchmarks: Stages with their commands.

    Returns:
        dict: Containing multistage result with its total, or just total if metric's command outputs one line.
    """
    succes = True
    for name, commands in benchmarks.items():
        for command in commands:
            _, _success = execute_and_handle_output(command)
            if not _success:
                succes = False
    process = execute_command(metric_command)
    output = handle_output(process, capture_stdout=True)
    result = process.wait()
    check_return_code(metric_command, result)
    if len(output.splitlines()) == 1:
        try:
            return {metric_name: float(output)}
        except ValueError:
            pass
        return {metric_name: output}, succes

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
    return output_dict, success
