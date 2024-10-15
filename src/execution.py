from subprocess import Popen, PIPE, STDOUT
from logging import getLogger, INFO, CRITICAL
from tqdm import tqdm


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


def perform_benchmarks(benchmarks: list, samples: int) -> list:
    results = []
    logger.info("Performing benchmarks...")
    bar = tqdm(total=(len(benchmarks) * samples * len(benchmarks[0]["metrics"])))
    bar.set_description("Performing benchmarks")
    for benchmark in benchmarks:
        try:
            for _ in range(0, samples):
                partial_results = []
                for metric in benchmark["metrics"]:
                    logger.debug(f"Running benchmark: {benchmark}")
                    if "before" in benchmark:
                        run_multiple_commands(benchmark["before"])
                    partial_result = metric(benchmark["benchmark"])
                    partial_results.append(partial_result)
                    if "after" in benchmark:
                        run_multiple_commands(benchmark["after"])
                    bar.update(1)
                results.append(
                    [benchmark["matrix"][key] for key in benchmark["matrix"]]
                    + partial_results
                )
        except KeyboardInterrupt:
            logger.warning("Stopped benchmarks.")
            logger.warning("Creating output...")
            break
    bar.close()
    logger.info("Finished performing benchmarks.")
    logger.debug(f"Benchmark results: {results}")
    return results
