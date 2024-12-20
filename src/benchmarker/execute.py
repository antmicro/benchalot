from subprocess import Popen, PIPE
from logging import getLogger
from os import getcwd, wait4, waitstatus_to_exitcode
from time import monotonic_ns
from io import StringIO
from csv import DictReader
from benchmarker.prepare import PreparedBenchmark
from benchmarker.output_constants import (
    HAS_FAILED_COLUMN,
    METRIC_COLUMN,
    STAGE_COLUMN,
    RESULT_COLUMN,
    BENCHMARK_ID_COLUMN,
    DEFAULT_STAGE_NAME,
)
from uuid import uuid4
from benchmarker.log import console
from benchmarker.config import BuiltInMetrics

logger = getLogger(f"benchmarker.{__name__}")
working_directory = getcwd()


def set_working_directory(cwd: str) -> None:
    """Set working directory of executed commands"""
    global working_directory
    working_directory = cwd


def check_return_code(command: str, code: int) -> bool:
    """Check return code of the command and exit Benchmarker if it is not 0

    Args:
        command: Command string, used in logging.
        code: Return code of the command.

    Returns:
        bool: True if program returned 0, otherwise False .
    """
    if code != 0:
        logger.error(f"Subprocess '{command}' exited abnormally (exit code {code})")
        return False
    return True


def execute_command(command: str) -> Popen:
    """Execute command in shell, with `stdout` and `stderr` piped.

    Args:
        command: Command to be executed.

    Returns:
        Popen: Process object.
    """
    global working_directory
    logger.info(command)
    return Popen(command, shell=True, stdout=PIPE, stderr=PIPE, cwd=working_directory)


def log_output(process: Popen) -> None:
    """Log output piped by the process.

    Args:
        process: Process object.
    """
    with process.stdout as output:  # type: ignore
        for line in output:
            decoded = line.decode("utf-8")
            console.log_command_output(decoded)
    console.flush()
    with process.stderr as output:  # type: ignore
        for line in output:
            decoded = line.decode("utf-8")
            console.log_command_output(decoded)
    console.flush()


def try_convert_to_float(value: str) -> float | None:
    """Try to convert string to float.

    Args:
        value: String to be converted.

    Retruns:
        float | None: Depending on whether the conversion succeeded.
    """
    try:
        return float(value)
    except ValueError:
        logger.error(f"Converting '{value.strip()}' to float failed!")
        return None


def gather_custom_metric(metric_command: str) -> tuple[dict[str, float | None], bool]:
    """Gather custom metric measurements.
    If output has more than one line, treat output as csv file, with each column representing separate stage.

    Args:
        metric_command: Command to be executed as custom metric.
    Returns:
        tuple[dict[str, float | None], bool]: Containing single or multi stage result and whether the custom_metric failed.
    """
    process = execute_command(metric_command)
    output, _ = process.communicate()
    output = output.decode("utf-8")
    if len(output.splitlines()) == 1:
        out = try_convert_to_float(output)
        return ({DEFAULT_STAGE_NAME: out}, out is None)
    elif len(output.splitlines()) == 2:
        output_stream = StringIO(output)
        reader = DictReader(output_stream)
        tmp_dict = {}
        for row in reader:
            tmp_dict = row
        output_dict: dict[str, float | None] = {}
        has_failed = False
        for stage in tmp_dict:
            value = tmp_dict[stage]
            out = try_convert_to_float(value)
            output_dict[stage] = out
            if out is None:
                has_failed = True
        return (output_dict, has_failed)
    else:
        logger.warning("Invalid custom metric output format:")
        logger.warning(output)
        return ({DEFAULT_STAGE_NAME: None}, True)


def perform_benchmarks(
    benchmarks: list[PreparedBenchmark],
    samples: int,
    builtin_metrics: set[BuiltInMetrics]
) -> dict[str, list]:
    """Perform benchmarks and return their results.

    Args:
        benchmarks: List of benchmarks, each containing variable values, preprocessed commands and callable metrics.
        samples: How many times each benchmark needs to be repeated.

    Returns:
        dict[str, list]: Dictionary containing results.
    """
    results: dict[str, list] = dict()
    with console.bar((len(benchmarks) * samples)) as bar:

        def _execute_section(commands):
            for c in commands:
                bar.set_description(c)
                process = execute_command(c)
                log_output(process)
                process.wait()

        for benchmark in benchmarks:
            try:
                for _ in range(0, samples):
                    logger.debug(f"Running benchmark: {benchmark}")

                    _execute_section(benchmark.before)

                    measure_time = BuiltInMetrics.TIME in builtin_metrics
                    measure_utime = BuiltInMetrics.UTIME in builtin_metrics
                    measure_stime = BuiltInMetrics.STIME in builtin_metrics
                    measure_memory = BuiltInMetrics.MEM in builtin_metrics
                    measure_stdout = BuiltInMetrics.STDOUT in builtin_metrics
                    measure_stderr = BuiltInMetrics.STDERR in builtin_metrics

                    has_failed = False

                    time_measurements: dict[str, float | None] = {}
                    utime_measurements: dict[str, float | None] = {}
                    stime_measurements: dict[str, float | None] = {}
                    memory_measurements: dict[str, float | None] = {}
                    stdout_measurements: dict[str, float | None] = {}
                    stderr_measurements: dict[str, float | None] = {}

                    for stage in benchmark.benchmark:
                        stage_elapsed_time = 0.0
                        stage_stdout = ""
                        stage_stderr = ""
                        stage_utime = 0.0
                        stage_stime = 0.0
                        stage_memory = -1
                        for command in benchmark.benchmark[stage]:
                            bar.set_description(command)
                            start = monotonic_ns()
                            process = execute_command(command)
                            # taking parts of process.communicate implementation, src: https://github.com/python/cpython/blob/main/Lib/subprocess.py
                            if measure_stderr or measure_stdout:
                                if process.stdout:
                                    process_stdout = process.stdout.read()
                                    process.stdout.close()
                                if process.stderr:
                                    process_stderr = process.stderr.read()
                                    process_stderr = process.stderr.close()
                            else:
                                log_output(process)
                            _, exit_status, resources = wait4(process.pid, 0)
                            stage_elapsed_time += monotonic_ns() - start
                            # source: https://manpages.debian.org/bookworm/manpages-dev/getrusage.2.en.html
                            if measure_utime:
                                stage_utime += resources.ru_utime
                            if measure_stime:
                                stage_stime += resources.ru_stime
                            if measure_memory:
                                stage_memory = max(stage_memory, resources.ru_maxrss)
                            if measure_stdout:
                                stage_stdout += process_stdout.decode("utf-8")
                            if measure_stderr:
                                stage_stderr += process_stderr.decode("utf-8")
                            success = check_return_code(
                                command, waitstatus_to_exitcode(exit_status)
                            )
                            if not success:
                                has_failed = True
                        if measure_time:
                            time_measurements[stage] = stage_elapsed_time / 1e9
                        if measure_utime:
                            utime_measurements[stage] = stage_utime
                        if measure_stime:
                            stime_measurements[stage] = stage_stime
                        if measure_memory:
                            memory_measurements[stage] = stage_memory
                        if measure_stdout:
                            out_float = try_convert_to_float(stage_stdout)
                            stdout_measurements[stage] = out_float
                            if out_float is None:
                                has_failed = True
                        if measure_stderr:
                            out_float = try_convert_to_float(stage_stderr)
                            stderr_measurements[stage] = out_float
                            if out_float is None:
                                has_failed = True

                    _execute_section(benchmark.after)

                    benchmark_results: dict[str, dict[str, float | None]] = {}

                    for custom_metric in benchmark.custom_metrics:
                        metric_name, command = list(custom_metric.items())[0]
                        custom_measurements, custom_metric_failed = (
                            gather_custom_metric(command)
                        )
                        if custom_metric_failed:
                            has_failed = True
                        benchmark_results[metric_name] = custom_measurements

                    if measure_time:
                        benchmark_results[BuiltInMetrics.TIME] = time_measurements
                    if measure_utime:
                        benchmark_results[BuiltInMetrics.UTIME] = utime_measurements
                    if measure_stime:
                        benchmark_results[BuiltInMetrics.STIME] = stime_measurements
                    if measure_memory:
                        benchmark_results[BuiltInMetrics.MEM] = memory_measurements
                    if measure_stdout:
                        benchmark_results[BuiltInMetrics.STDOUT] = stdout_measurements
                    if measure_stderr:
                        benchmark_results[BuiltInMetrics.STDERR] = stderr_measurements

                    bar.update(1)
                    id = uuid4()
                    for metric_name, measurements in benchmark_results.items():
                        for stage, result in measurements.items():
                            results.setdefault(BENCHMARK_ID_COLUMN, []).append(id)
                            for variable in benchmark.matrix:
                                results.setdefault(variable, []).append(
                                    benchmark.matrix[variable]
                                )
                            results.setdefault(HAS_FAILED_COLUMN, []).append(has_failed)
                            results.setdefault(METRIC_COLUMN, []).append(metric_name)
                            results.setdefault(STAGE_COLUMN, []).append(stage)
                            results.setdefault(RESULT_COLUMN, []).append(result)

            except KeyboardInterrupt:
                logger.warning("Stopped benchmarks.")
                logger.warning("Creating output...")
                break
    logger.debug(f"Benchmark results: {results}")
    return results
