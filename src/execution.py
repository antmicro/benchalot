from time import monotonic_ns
from subprocess import run
from yaspin import yaspin
from logging import getLogger
from sys import stderr


logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger(f"run.{__name__}")


def log_run_results(result):
    command_logger.info(f"Run: {result.args}")
    if len(result.stdout) > 0:
        msg = result.stdout.replace("\n", " ")
        command_logger.info(f"stdout: {msg}")
    if len(result.stderr) > 0:
        msg = result.stderr.replace("\n", " ")
        command_logger.warning(f"stderr: {msg}")


def run_multiple_commands(commands: list):
    for c in commands:
        result = run(c, shell=True, capture_output=True, text=True)
        log_run_results(result)
        if result.returncode != 0:
            print(
                f"Subprocess `{c}` exited abnormally (exit code {result.returncode})",
                file=stderr,
            )
            print(f"stderr: {str(result.stderr)}")
            exit(1)


def measure_time_command(command: str) -> tuple:
    start = monotonic_ns()
    result = run(command, shell=True, capture_output=True)
    return (monotonic_ns() - start), result


def benchmark_commands(commands: list) -> float:
    total = 0
    with yaspin(text=f"Benchmarking {commands}...", timer=True):
        for command in commands:
            time, result = measure_time_command(command)
            log_run_results(result)
            if result.returncode != 0:
                print(
                    f"Subprocess `{command}` exited abnormally (exit code: {result.returncode})"
                )
                exit(1)
            total += time
    return total / 1e9  # convert to seconds


def perform_benchmarks(benchmarks: list, samples: int) -> list:
    results = []
    logger.info("Performing benchmarks...")
    for benchmark in benchmarks:
        for i in range(0, samples):
            logger.debug(f"Running benchmark: {benchmark}")
            if "before" in benchmark:
                run_multiple_commands(benchmark["before"])

            result = benchmark_commands(benchmark["benchmark"])

            if "after" in benchmark:
                run_multiple_commands(benchmark["after"])
            results.append(
                [benchmark["matrix"][key] for key in benchmark["matrix"]] + [result]
            )
    logger.info("Finished performing benchmarks.")
    logger.debug(f"Benchmark results: {results}")
    return results
