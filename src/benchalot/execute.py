from subprocess import Popen, PIPE
from logging import getLogger
from os import (
    getcwd,
    wait4,
    waitstatus_to_exitcode,
    environ,
    WNOHANG,
    waitid,
    WNOWAIT,
    WEXITED,
    P_PID,
)
from time import monotonic_ns
from io import StringIO
from csv import DictReader
from benchalot.prepare import PreparedBenchmark
from benchalot.output_constants import (
    HAS_FAILED_COLUMN,
    METRIC_COLUMN,
    STAGE_COLUMN,
    RESULT_COLUMN,
    BENCHMARK_ID_COLUMN,
    DEFAULT_STAGE_NAME,
)
from uuid import uuid4
from benchalot.log import console
from benchalot.config import BuiltInMetrics, SystemSection
from benchalot.system import modify_system_state, restore_system_state
from os.path import isdir
import threading
from collections import deque

logger = getLogger(f"benchalot.{__name__}")
working_directory = getcwd()


def set_working_directory(cwd: str) -> None:
    """Set working directory of executed commands"""
    global working_directory
    if not isdir(cwd):
        logger.critical(f"Directory '{cwd}' not found")
        exit(1)
    working_directory = cwd


def check_return_code(command: str, code: int) -> bool:
    """Check return code of the command and exit benchalot if it is not 0

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
        separate_stderr: If set to `True`, will create a separate pipe for stderr.

    Returns:
        Popen: Process object.
    """
    global working_directory
    logger.info(command)
    return Popen(command, shell=True, stdout=PIPE, stderr=PIPE, cwd=working_directory)


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
    console.log_command_output(output)
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


def read_pipe(pipe, queue):
    start = monotonic_ns()
    if pipe:
        while True:
            # NOTE: read1 gets any data with at most one read() call
            #       normal read() would block here unitl EOF is reached
            data = pipe.read1()
            if not data:
                break
            queue.append(data)
        pipe.close()
    queue.append(None)
    end = monotonic_ns() - start
    logger.debug(f"Reading output from pipe took: {end/1e9}s")


class OutputLogger:
    def __init__(self, file, store=False):
        # NOTE: deque.append and deque.popleft are atomic operations
        self.queue = deque()
        self.stderr_done = False
        self.done = False
        self.store = store
        self.output = b""
        threading.Thread(target=read_pipe, args=(file, self.queue), daemon=True).start()
        self.total_log_time = 0

    def log(self):
        start = monotonic_ns()
        if self.done:
            return
        if len(self.queue) > 0:
            output = self.queue.popleft()
            if output is None:
                self.done = True
                console.flush()
            else:
                if self.store:
                    self.output += output
                console.log_command_output(output.decode("utf-8"))
        end = monotonic_ns() - start
        self.total_log_time += end

    def __del__(self):
        logger.debug(f"Logging output took: {self.total_log_time/1e9}s")


def poll(process):
    """Without blocking, check if process returned. Process needs to be reaped later"""
    status = waitid(P_PID, process.pid, WNOHANG | WNOWAIT | WEXITED)
    finished = status is not None
    return finished


def reap(process):
    """Get information about finished process"""
    pid, wait_status, resources = wait4(process.pid, 0)
    return pid, waitstatus_to_exitcode(wait_status), resources


def perform_benchmarks(
    benchmarks: list[PreparedBenchmark],
    samples: int,
    builtin_metrics: set[BuiltInMetrics],
    system: SystemSection,
) -> dict[str, list]:
    """Perform benchmarks and return their results.

    Args:
        benchmarks: List of benchmarks, each containing variable values, preprocessed commands and callable metrics.
        samples: How many times each benchmark needs to be repeated.
        builtin_metrics: What benchalot's builtint metrics need to be measured
        system: Configuration defining variance reducing system measures

    Returns:
        dict[str, list]: Dictionary containing results.
    """
    results: dict[str, list] = dict()
    with console.bar((len(benchmarks) * samples)) as bar:

        def _execute_section(commands):
            for c in commands:
                bar.set_description(c)
                process = execute_command(c)
                stdout_logger = OutputLogger(process.stderr)
                stderr_logger = OutputLogger(process.stdout)
                finished = False

                while not finished or not stdout_logger.done or not stderr_logger.done:
                    bar.refresh()
                    stdout_logger.log()
                    stderr_logger.log()
                    if not finished:
                        finished = poll(process)

                _, exit_code, _ = reap(process)
                if not check_return_code(c, exit_code):
                    return False
            return True

        for benchmark in benchmarks:
            try:
                logger.debug(f"Running benchmark: {benchmark}")
                if benchmark.cwd:
                    set_working_directory(benchmark.cwd)
                environ.update(benchmark.env)
                with console.log_to_file(benchmark.save_output):
                    has_failed = False
                    if not _execute_section(benchmark.setup):
                        has_failed = True
                    for _ in range(0, samples):
                        if not has_failed and not _execute_section(benchmark.prepare):
                            has_failed = True

                        measure_time = BuiltInMetrics.TIME in builtin_metrics
                        measure_utime = BuiltInMetrics.UTIME in builtin_metrics
                        measure_stime = BuiltInMetrics.STIME in builtin_metrics
                        measure_memory = BuiltInMetrics.MEM in builtin_metrics
                        measure_stdout = BuiltInMetrics.STDOUT in builtin_metrics
                        measure_stderr = BuiltInMetrics.STDERR in builtin_metrics

                        time_measurements: dict[str, float | None] = {}
                        utime_measurements: dict[str, float | None] = {}
                        stime_measurements: dict[str, float | None] = {}
                        # NOTE: float here is needed for mypy
                        memory_measurements: dict[str, float | int | None] = {}
                        stdout_measurements: dict[str, float | None] = {}
                        stderr_measurements: dict[str, float | None] = {}

                        if system.modify:
                            modify_system_state(system)

                        for stage in benchmark.benchmark:
                            stage_elapsed_time = 0.0
                            stage_stdout = ""
                            stage_stderr = ""
                            stage_utime = 0.0
                            stage_stime = 0.0
                            stage_memory = 0
                            for command in benchmark.benchmark[stage]:
                                if has_failed:
                                    break
                                bar.set_description(command)
                                process = execute_command(command)
                                start = monotonic_ns()
                                stdout_logger = OutputLogger(
                                    process.stdout, measure_stdout
                                )
                                stderr_logger = OutputLogger(
                                    process.stderr, measure_stderr
                                )

                                while not poll(process):
                                    stdout_logger.log()
                                    stderr_logger.log()
                                    bar.refresh()

                                stage_elapsed_time += monotonic_ns() - start
                                pid, exit_status, resources = reap(process)

                                start = monotonic_ns()
                                # log remaining output
                                while not (stdout_logger.done and stderr_logger.done):
                                    stdout_logger.log()
                                    stderr_logger.log()
                                    bar.refresh()
                                end = monotonic_ns() - start
                                logger.debug(
                                    f"Logging remaining output took: {end/1e9}s"
                                )

                                # source: https://manpages.debian.org/bookworm/manpages-dev/getrusage.2.en.html
                                if measure_utime:
                                    stage_utime += resources.ru_utime
                                if measure_stime:
                                    stage_stime += resources.ru_stime
                                if measure_memory:
                                    stage_memory = max(
                                        stage_memory, resources.ru_maxrss
                                    )
                                if measure_stdout:
                                    stage_stdout += stdout_logger.output.decode("utf-8")
                                if measure_stderr:
                                    stage_stderr += stderr_logger.output.decode("utf-8")
                                success = check_return_code(command, exit_status)
                                if not success:
                                    has_failed = True
                            if not has_failed:
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
                            else:
                                if measure_time:
                                    time_measurements[stage] = None
                                if measure_utime:
                                    utime_measurements[stage] = None
                                if measure_stime:
                                    stime_measurements[stage] = None
                                if measure_memory:
                                    memory_measurements[stage] = None
                                if measure_stdout:
                                    stdout_measurements[stage] = None
                                if measure_stderr:
                                    stderr_measurements[stage] = None

                        if system.modify:
                            restore_system_state()

                        if not has_failed and not _execute_section(benchmark.conclude):
                            has_failed = True

                        benchmark_results: dict[str, dict[str, float | int | None]] = {}

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
                            benchmark_results[BuiltInMetrics.STDOUT] = (
                                stdout_measurements
                            )
                        if measure_stderr:
                            benchmark_results[BuiltInMetrics.STDERR] = (
                                stderr_measurements
                            )

                        id = uuid4()
                        for metric_name, measurements in benchmark_results.items():
                            for stage, result in measurements.items():
                                results.setdefault(BENCHMARK_ID_COLUMN, []).append(id)
                                for variable in benchmark.matrix:
                                    stack = [(variable, benchmark.matrix[variable])]
                                    while stack:
                                        variable_name, value = stack.pop()
                                        if not isinstance(value, dict):
                                            results.setdefault(
                                                variable_name, []
                                            ).append(value)
                                        else:
                                            # We reverse it to keep the user defined order
                                            for k, v in reversed(list(value.items())):
                                                stack.append(
                                                    (f"{variable_name}.{k}", v)
                                                )

                                results.setdefault(HAS_FAILED_COLUMN, []).append(
                                    has_failed
                                )
                                results.setdefault(METRIC_COLUMN, []).append(
                                    metric_name
                                )
                                results.setdefault(STAGE_COLUMN, []).append(stage)
                                results.setdefault(RESULT_COLUMN, []).append(result)
                        bar.progress()

                    if not has_failed:
                        _execute_section(benchmark.cleanup)

            except KeyboardInterrupt:
                logger.warning("Stopped benchmarks.")
                logger.warning("Creating output...")
                break
    logger.debug(f"Benchmark results: {results}")
    return results
