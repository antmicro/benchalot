from time import monotonic_ns
from subprocess import Popen, PIPE, STDOUT
from yaspin import yaspin
from logging import getLogger


logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")


def log_program_output(pipe):
    for line in pipe:
        if len(line) > 0:
            command_logger.info(line.decode("utf-8").strip())


def execute_command(command: str):
    process = Popen(command, shell=True, stdout=PIPE, stderr=STDOUT)
    with process.stdout as output:  # type: ignore
        log_program_output(output)
    return process.wait()


def run_multiple_commands(commands: list):
    for c in commands:
        result = execute_command(c)
        if result != 0:
            logger.critical(f"Subprocess '{c}' exited abnormally (exit code {result})")
            exit(1)


def measure_time_command(command: str) -> tuple:
    start = monotonic_ns()
    result = execute_command(command)
    time = monotonic_ns() - start

    return time, result


def benchmark_commands(commands: list) -> float:
    total = 0
    with yaspin(text=f"Benchmarking {commands}...", timer=True):
        for command in commands:
            time, result = measure_time_command(command)
            if result != 0:
                logger.critical(
                    f"Subprocess '{command}' exited abnormally (exit code {result})"
                )
            total += time
    return total / 1e9  # convert to seconds


def perform_benchmarks(benchmarks: list, samples: int) -> list:
    results = []
    logger.info("Performing benchmarks...")
    for benchmark in benchmarks:
        try:
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
        except KeyboardInterrupt:
            logger.warning("Stopped benchmarks.")
            logger.warning("Creating output...")
            break
    logger.info("Finished performing benchmarks.")
    logger.debug(f"Benchmark results: {results}")
    return results
