from time import monotonic_ns
from subprocess import run
from yaspin import yaspin
from logging import getLogger, FileHandler, Formatter, INFO

formatter = Formatter("%(levelname)s:%(message)s")

logger = getLogger(__name__)
handler = FileHandler("execution.log")
handler.setFormatter(formatter)
command_logger = getLogger(__name__)
command_logger.setLevel(INFO)
command_logger.addHandler(handler)


def log_run_results(result):
    msg = f"Executed: {result.args}"
    if len(result.stdout) > 0:
        msg += f"\nstdout:\n{result.stdout}"
    if len(result.stderr) > 0:
        msg += f"\nstderr:\n{result.stderr}"
    command_logger.info(msg)


def run_multiple_commands(commands: list):
    for c in commands:
        result = run(c, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(
                f"Subprocess `{c}` exited abnormally (exit code: {result.returncode})"
            )
            print(f"stderr: {str(result.stderr)}")
            exit(1)
        log_run_results(result)


def measure_time_command(command: str) -> tuple:
    start = monotonic_ns()
    result = run(command, shell=True, capture_output=True)
    return (monotonic_ns() - start), result


def benchmark_commands(commands: list) -> float:
    total = 0
    with yaspin(text=f"Benchmarking {commands}...", timer=True):
        for command in commands:
            time, result = measure_time_command(command)
            if result.returncode != 0:
                print(
                    f"Subprocess `{command}` exited abnormally (exit code: {result.returncode})"
                )
                exit(1)
            log_run_results(result)
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
