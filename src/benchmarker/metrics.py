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


def measure_time(benchmarks: dict[str, list[str]]) -> BenchmarkResult:
    """Measure execution time of the commands.

    Args:
        benchmarks: Commands divided into stages.

    Returns:
        BenchmarkResult: Containing execution time of each stage.
    """
    has_failed = False

    def _measure_stage_time(commands: list[str]) -> float:
        nonlocal has_failed
        elapsed_time = 0.0
        for command in commands:
            start = monotonic_ns()
            process = execute_command(command)
            code = process.wait()
            elapsed_time += monotonic_ns() - start
            handle_output(process)
            success = check_return_code(command, code)
            if not success:
                has_failed = True
        return elapsed_time / 1e9

    measurements: dict[str, float] = {}
    for stage, commands in benchmarks.items():
        measurements[stage] = _measure_stage_time(commands)
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
        BenchmarkResult: Containing `stderr` or `stdout` of each stage. If possible, output will be converted to float.
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
                has_failed = True
        try:
            return float(total)
        except ValueError:
            pass
        return total

    measurements: dict[str, float | str] = {}

    for stage, command in benchmarks.items():
        measurements[stage] = _gather_stage_output(command)
    result = BenchmarkResult(output, has_failed, measurements)
    return result


def gather_stdout(benchmarks: dict[str, list[str]]) -> BenchmarkResult:
    """Calls `_gather_output` with `output` set to "stdout"."""
    return _gather_output(benchmarks, "stdout")


def gather_stderr(benchmarks: dict[str, list[str]]) -> BenchmarkResult:
    """Calls `_gather_output` with `output` set to "stderr"."""
    return _gather_output(benchmarks, "stderr")


def custom_metric(
    metric_command: str, metric_name: str, benchmarks: dict[str, list[str]]
) -> BenchmarkResult:
    """Execute all the benchmark commands, then execute custom metric command and process its output.
    If output has more than one line, treat output as csv file, with each column representing separate stage.
    Sum stages under `metric_name`.

    Args:
        metric_command: Command to be executed as custom metric.
        metric_name: Custom metric's name.
        benchmarks: Stages with their commands.

    Returns:
        BenchmarkResult: Containing single or multi stage result.
    """
    has_failed = False
    for _, commands in benchmarks.items():
        for command in commands:
            _, success = execute_and_handle_output(command)
            if not success:
                has_failed = True
    process = execute_command(metric_command)
    output = handle_output(process, capture_stdout=True)
    metric_return_code = process.wait()
    if not check_return_code(metric_command, metric_return_code):
        exit(1)

    if len(output.splitlines()) == 1:
        try:
            return BenchmarkResult(metric_name, has_failed, {"total": float(output)})
        except ValueError:
            pass
        return BenchmarkResult(metric_name, has_failed, {"total": output})

    output_stream = StringIO(output)
    reader = DictReader(output_stream)
    tmp_dict = {}
    for row in reader:
        tmp_dict = row
    output_dict = {}
    for stage in tmp_dict:
        value = tmp_dict[stage]
        try:
            value = float(value)
        except ValueError:
            pass
        output_dict[stage] = value
    result = BenchmarkResult(metric_name, has_failed, output_dict)
    return result
