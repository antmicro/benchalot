from subprocess import Popen, PIPE, STDOUT
from yaspin import yaspin
from logging import getLogger, INFO, CRITICAL

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")


def log_program_output(pipe, level=INFO):
    for line in pipe:
        if len(line) > 0:
            command_logger.log(msg=line.decode("utf-8").strip(), level=level)


def execute_command(command: str):
    process = Popen(command, shell=True, stdout=PIPE, stderr=STDOUT)
    result = process.wait()
    if result != 0:
        logger.critical(
            f"Subprocess '{command}' exited abnormally (exit code {result})"
        )
        with process.stdout as output:  # type: ignore
            log_program_output(output, level=CRITICAL)
        exit(1)
    with process.stdout as output:  # type: ignore
        log_program_output(output)


def run_multiple_commands(commands: list):
    for c in commands:
        execute_command(c)


def benchmark_commands(commands: list, metric_constructor) -> float:
    metric = metric_constructor(commands)
    with yaspin(text=f"Benchmarking {commands}...", timer=True):
        for command in commands:
            metric.before_command(command)
            execute_command(command)
            metric.after_command(command, None)
    return metric.get_result()


def perform_benchmarks(benchmarks: list, samples: int, metrics: list) -> list:
    results = []
    logger.info("Performing benchmarks...")
    for benchmark in benchmarks:
        try:
            for i in range(0, samples):
                partial_results = []
                for metric_constructor in metrics:
                    logger.debug(f"Running benchmark: {benchmark}")
                    if "before" in benchmark:
                        run_multiple_commands(benchmark["before"])
                    result = benchmark_commands(
                        benchmark["benchmark"], metric_constructor
                    )
                    partial_results.append(result)
                    if "after" in benchmark:
                        run_multiple_commands(benchmark["after"])
                results.append(
                    [benchmark["matrix"][key] for key in benchmark["matrix"]]
                    + partial_results
                )
        except KeyboardInterrupt:
            logger.warning("Stopped benchmarks.")
            logger.warning("Creating output...")
            break
    logger.info("Finished performing benchmarks.")
    logger.debug(f"Benchmark results: {results}")
    return results
