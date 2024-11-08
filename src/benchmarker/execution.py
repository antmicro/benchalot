from subprocess import Popen, PIPE
from logging import getLogger, INFO, ERROR
from tqdm import tqdm
from os import getcwd
from benchmarker.structs import PreparedBenchmark, BenchmarkResult


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


def handle_output(
    process: Popen, capture_stdout: bool = False, capture_stderr: bool = False
) -> str:
    """Log and/or save output piped by the process.

    Args:
        process: Process object.
        capture_stdout: If true, return `stdout` of the process.
        capture_stderr: If true, return `stderr` of the process.

    Returns:
        str: Containing `stdout` and/or `stderr` of the process.
    """
    total = ""
    level = INFO
    with process.stdout as output:  # type: ignore
        for line in output:
            if len(line) > 0:
                if process.poll() is not None and process.poll() != 0:
                    level = ERROR
                command_logger.log(msg=line.decode("utf-8").strip(), level=level)
                if capture_stdout:
                    total += line.decode("utf-8")
    with process.stderr as output:  # type: ignore
        for line in output:
            if len(line) > 0:
                if process.poll() is not None and process.poll() != 0:
                    level = ERROR
                command_logger.log(msg=line.decode("utf-8").strip(), level=level)
                if capture_stderr:
                    total += line.decode("utf-8")
    return total.strip()


def execute_and_handle_output(
    command: str, capture_stdout=False, capture_stderr=False
) -> tuple[str, bool]:
    """Execute command, log its output and check its return code.

    Args:
        command: Command to be executed.
        capture_stdout: If true, return `stdout` of the process.
        capture_stderr: If true, return `stderr` of the process.

    Returns:
        (str, bool): String containing `stdout` and/or `stderr` of the process and bool set to True if program returned 0.
    """
    process = execute_command(command)
    total = handle_output(process, capture_stdout, capture_stderr)
    result = process.wait()
    success = check_return_code(command, result)
    return total, success


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

                partial_result: BenchmarkResult = benchmark.metric(benchmark.benchmark)
                bar.refresh(nolock=True)

                execute_section(benchmark.after, "after")
                bar.update(1)

                for variable in benchmark.matrix:
                    results.setdefault(variable, []).append(benchmark.matrix[variable])
                results.setdefault("has_failed", []).append(partial_result.has_failed)
                results.setdefault("metric", []).append(partial_result.metric_name)
                for stage in partial_result.measurements:
                    stage_column = results.setdefault(stage, [])
                    # pad columns so that they have the same length
                    stage_column += [None] * (n_rows - len(stage_column))
                    stage_column.append(partial_result.measurements[stage])
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
