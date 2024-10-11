from time import monotonic_ns
from subprocess import run, DEVNULL
from yaspin import yaspin
from logging import getLogger


logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")


def log_run_results(result):
    if len(result.stdout) > 0:
        command_logger.info(str(result.stdout))
    if len(result.stderr) > 0:
        command_logger.warning(str(result.stderr))


def execute_command(command: str, suppress_output: bool):
    if suppress_output:
        result = run(command, shell=True, stdout=DEVNULL, stderr=DEVNULL, text=True)
    else:
        result = run(command, shell=True, capture_output=True, text=True)
    return result


def run_multiple_commands(commands: list, suppress_output: bool):
    for c in commands:
        result = execute_command(c, suppress_output)
        if not suppress_output:
            log_run_results(result)
        if result.returncode != 0:
            logger.critical(
                f"Subprocess '{c}' exited abnormally (exit code {result.returncode})"
            )
            logger.critical(str(result.stderr).strip())
            exit(1)


def measure_time_command(command: str, suppress_output: bool) -> tuple:
    start = monotonic_ns()
    result = execute_command(command, suppress_output)
    time = monotonic_ns() - start

    return time, result


def benchmark_commands(commands: list, suppress_output: bool) -> float:
    total = 0
    with yaspin(text=f"Benchmarking {commands}...", timer=True):
        for command in commands:
            time, result = measure_time_command(command, suppress_output)
            if not suppress_output:
                log_run_results(result)
            if result.returncode != 0:
                logger.critical(
                    f"Subprocess '{command}' exited abnormally (exit code {result.returncode})"
                )
                logger.critical(str(result.stderr).strip())
            total += time
    return total / 1e9  # convert to seconds


def perform_benchmarks(benchmarks: list, samples: int, suppress_output: bool) -> list:
    results = []
    logger.info("Performing benchmarks...")
    for benchmark in benchmarks:
        for i in range(0, samples):
            logger.debug(f"Running benchmark: {benchmark}")
            if "before" in benchmark:
                run_multiple_commands(benchmark["before"], suppress_output)

            result = benchmark_commands(benchmark["benchmark"], suppress_output)

            if "after" in benchmark:
                run_multiple_commands(benchmark["after"], suppress_output)
            results.append(
                [benchmark["matrix"][key] for key in benchmark["matrix"]] + [result]
            )
    logger.info("Finished performing benchmarks.")
    logger.debug(f"Benchmark results: {results}")
    return results
