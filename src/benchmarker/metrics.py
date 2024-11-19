from time import monotonic_ns
from logging import getLogger
from benchmarker.execution import (
    handle_output,
    check_return_code,
    execute_command,
)
from io import StringIO
from csv import DictReader
from benchmarker.structs import BenchmarkResult

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")


def execute_benchmark(
    benchmarks: dict[str, list[str]], builtin_metrics, custom_metrics
) -> list[BenchmarkResult]:
    has_failed = False
    measure_time = "time" in builtin_metrics
    gather_stdout = "stdout" in builtin_metrics
    gather_stderr = "stderr" in builtin_metrics

    time_measurements = {}
    output_measurements = {}

    for stage in benchmarks:
        elapsed_time = 0.0
        output = ""
        for command in benchmarks[stage]:
            start = monotonic_ns()
            process = execute_command(command)
            code = process.wait()
            elapsed_time += monotonic_ns() - start
            output += handle_output(
                process, capture_stdout=gather_stdout, capture_stderr=gather_stderr
            )
            success = check_return_code(command, code)
            if not success:
                has_failed = True
        if measure_time:
            time_measurements[stage] = elapsed_time / 1e9
        if gather_stderr or gather_stdout:
            try:
                output_measurements[stage] = float(output)
            except ValueError:
                logger.error("Conversion of '{output}' to float failed.'")

    benchmark_results: list[BenchmarkResult] = []

    for metric_name, command in custom_metrics:
        custom_measurements = custom_metric(command)
        benchmark_results.append(
            BenchmarkResult(metric_name, has_failed, custom_measurements)
        )

    if measure_time:
        benchmark_results.append(BenchmarkResult("time", has_failed, time_measurements))
    if gather_stderr or gather_stdout:
        benchmark_results.append(
            BenchmarkResult("output", has_failed, output_measurements)
        )

    return benchmark_results


def custom_metric(metric_command: str) -> dict[str, float]:
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
    process = execute_command(metric_command)
    output = handle_output(process, capture_stdout=True)
    process.wait()

    if len(output.splitlines()) == 1:
        try:
            return {"result": float(output)}
        except ValueError:
            logger.error("Conversion of '{output}' to float failed.'")
            return None
    elif len(output.splitlines()) == 2:
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
                logger.error("Conversion of '{output}' to float failed.'")
                return None
            output_dict[stage] = value
        return output_dict
    else:
        logger.critical("Invalid custom metric output format:")
        logger.critical(output)
        exit(1)
