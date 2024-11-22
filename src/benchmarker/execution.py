from subprocess import Popen, PIPE
from logging import getLogger, INFO, ERROR
from tqdm import tqdm
from os import getcwd
from benchmarker.structs import PreparedBenchmark, BenchmarkResult
from benchmarker.output import HAS_FAILED_COLUMN, METRIC_COLUMN
from time import monotonic_ns
from io import StringIO
from csv import DictReader
from typing import Literal

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")
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
    return Popen(command, shell=True, stdout=PIPE, stderr=PIPE, cwd=working_directory)


def log_output(process: Popen) -> None:
    """Log output piped by the process.

    Args:
        process: Process object.
    """
    level = INFO
    with process.stdout as output:  # type: ignore
        for line in output:
            if len(line) > 0:
                if process.poll() is not None and process.poll() != 0:
                    level = ERROR
                command_logger.log(msg=line.decode("utf-8").strip(), level=level)
    with process.stderr as output:  # type: ignore
        for line in output:
            if len(line) > 0:
                if process.poll() is not None and process.poll() != 0:
                    level = ERROR
                command_logger.log(msg=line.decode("utf-8").strip(), level=level)


def execute_and_handle_output(command: str) -> bool:
    """Execute command, log its output and check its return code.

    Args:
        command: Command to be executed.

    Returns:
        bool: True if program returned 0, otherwise False.
    """
    process = execute_command(command)
    log_output(process)
    result = process.wait()
    success = check_return_code(command, result)
    return success


def execute_section(commands: list[str], section_name: str = "") -> None:
    """Execute and log output multiple of commands.

    Args:
        commands: List of commands to be executed.
        section_name: Name of the section, used in logging.
    """
    if not commands:
        return
    logger.info(f"Executing '{section_name}' section...")
    logger.debug(f"Executing: {commands}")
    bar = tqdm(commands, leave=False, delay=1)
    for c in bar:
        bar.set_description(c[:20] + "..." if len(c) > 20 else c, refresh=False)
        execute_and_handle_output(c)
    logger.info(f"Execution of '{section_name}' section finished.")


def try_convert_to_float(value: str) -> float | str:
    try:
        return float(value)
    except ValueError:
        return value


def gather_custom_metric(metric_command: str) -> dict[str, float | str]:
    """Gather custom metric measurements.
    If output has more than one line, treat output as csv file, with each column representing separate stage.

    Args:
        metric_command: Command to be executed as custom metric.
    Returns:
        dict[str, float | str]: Containing single or multi stage result.
    """
    process = execute_command(metric_command)
    output, _ = process.communicate()
    output = output.decode("utf-8")
    if len(output.splitlines()) == 1:
        return {"result": try_convert_to_float(output)}
    elif len(output.splitlines()) == 2:
        output_stream = StringIO(output)
        reader = DictReader(output_stream)
        tmp_dict = {}
        for row in reader:
            tmp_dict = row
        output_dict = {}
        for stage in tmp_dict:
            value = tmp_dict[stage]
            output_dict[stage] = try_convert_to_float(value)
        return output_dict
    else:
        logger.critical("Invalid custom metric output format:")
        logger.critical(output)
        exit(1)


def execute_benchmark(
    benchmarks: dict[str, list[str]],
    builtin_metrics: list[Literal["time", "stdout", "stderr"]],
    custom_metrics: list[dict],
) -> list[BenchmarkResult]:
    """Execute benchmarks and take selected measurements.

    Args:
        benchmarks: List of benchmarks divided into stages.
        builtin_metrics: List of metrics built-in metrics, which will be gathered during execution.
        custom_metric: List of custom metrics (names and commands) which will be gathered during execution.

    Returns:
        list[BenchmarkResult]: List of benchmark results.
    """
    has_failed = False
    measure_time = "time" in builtin_metrics
    gather_stdout = "stdout" in builtin_metrics
    gather_stderr = "stderr" in builtin_metrics

    time_measurements = {}
    stdout_measurements = {}
    stderr_measurements = {}

    for stage in benchmarks:
        stage_elapsed_time = 0.0
        stage_stdout = ""
        stage_stderr = ""
        for command in benchmarks[stage]:
            start = monotonic_ns()
            process = execute_command(command)
            if gather_stderr or gather_stdout:
                process_stdout, process_stderr = process.communicate()
            else:
                log_output(process)
                process.wait()
            success = check_return_code(command, process.returncode)
            if not success:
                has_failed = True
            stage_elapsed_time += monotonic_ns() - start
            stage_stdout += process_stdout.decode("utf-8")
            stage_stderr += process_stderr.decode("utf-8")
        if measure_time:
            time_measurements[stage] = stage_elapsed_time / 1e9
        if gather_stdout:
            stdout_measurements[stage] = try_convert_to_float(stage_stdout)
        if gather_stderr:
            stderr_measurements[stage] = try_convert_to_float(stage_stderr)

    benchmark_results: list[BenchmarkResult] = []

    for custom_metric in custom_metrics:
        metric_name, command = list(custom_metric.items())[0]
        custom_measurements = gather_custom_metric(command)
        benchmark_results.append(
            BenchmarkResult(metric_name, has_failed, custom_measurements)
        )

    if measure_time:
        benchmark_results.append(BenchmarkResult("time", has_failed, time_measurements))
    if gather_stdout:
        benchmark_results.append(
            BenchmarkResult("stdout", has_failed, stdout_measurements)
        )
    if gather_stderr:
        benchmark_results.append(
            BenchmarkResult("stderr", has_failed, stderr_measurements)
        )

    return benchmark_results


def perform_benchmarks(
    benchmarks: list[PreparedBenchmark], samples: int
) -> dict[str, list]:
    """Perform benchmarks and return their results.

    Args:
        benchmarks: List of benchmarks, each containing variable values, preprocessed commands and callable metrics.
        samples: How many times each benchmark needs to be repeated.

    Returns:
        dict[str, list]: Dictionary containing results.
    """
    results: dict[str, list] = dict()
    n_rows = 0
    logger.info("Performing benchmarks...")
    bar = tqdm(
        desc="Performing benchmarks.",
        total=(len(benchmarks) * samples),
        unit="benchmark",
        leave=False,
        mininterval=1,
    )
    for benchmark in benchmarks:
        try:
            for _ in range(0, samples):
                logger.debug(f"Running benchmark: {benchmark}")

                execute_section(benchmark.before, "before")
                text = str([benchmark.benchmark[key] for key in benchmark.benchmark])
                text = text.replace("[", "")
                text = text.replace("]", "")
                bar.set_description(
                    f"Executing {text[:20] + '...' if len(text)>20 else text}"
                )

                benchmark_results: list[BenchmarkResult] = execute_benchmark(
                    benchmark.benchmark,
                    benchmark.builtin_metrics,
                    benchmark.custom_metrics,
                )
                bar.refresh(nolock=True)

                execute_section(benchmark.after, "after")
                bar.update(1)
                for single_result in benchmark_results:
                    for variable in benchmark.matrix:
                        results.setdefault(variable, []).append(
                            benchmark.matrix[variable]
                        )
                    results.setdefault(HAS_FAILED_COLUMN, []).append(
                        single_result.has_failed
                    )
                    results.setdefault(METRIC_COLUMN, []).append(
                        single_result.metric_name
                    )
                    for stage in single_result.measurements:
                        stage_column = results.setdefault(stage, [])
                        # pad columns so that they have the same length
                        stage_column += [None] * (n_rows - len(stage_column))
                        stage_column.append(single_result.measurements[stage])
                    n_rows += 1

        except KeyboardInterrupt:
            logger.warning("Stopped benchmarks.")
            logger.warning("Creating output...")
            break
    # pad columns so that they have the same length
    for _, col in results.items():
        col += [None] * (n_rows - len(col))
    bar.close()
    logger.info("Finished performing benchmarks.")
    logger.debug(f"Benchmark results: {results}")
    return results
