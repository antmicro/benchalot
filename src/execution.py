from subprocess import Popen, PIPE
from logging import getLogger, INFO, ERROR
from tqdm import tqdm

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")


def check_return_code(command, code):
    if code != 0:
        logger.error(f"Subprocess '{command}' exited abnormally (exit code {code})")
        exit(1)


def handle_output(process, capture_stdout=False, capture_stderr=False):
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


def execute_and_handle_output(command, capture_stdout=False, capture_stderr=False):
    process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
    total = handle_output(process, capture_stdout, capture_stderr)
    result = process.wait()
    check_return_code(command, result)
    return total


def run_multiple_commands(commands: list):
    for c in commands:
        execute_and_handle_output(c)


def perform_benchmarks(benchmarks: list, samples: int) -> list:
    results = []
    logger.info("Performing benchmarks...")
    bar = tqdm(
        desc="Performing benchmarks...",
        total=(len(benchmarks) * samples * len(benchmarks[0]["metrics"])),
        unit=" benchmarks",
        leave=False,
    )
    for benchmark in benchmarks:
        try:
            for _ in range(0, samples):
                partial_results = []
                for metric in benchmark["metrics"]:
                    logger.debug(f"Running benchmark: {benchmark}")
                    if "before" in benchmark:
                        run_multiple_commands(benchmark["before"])
                        bar.refresh(nolock=True)
                    bar.set_description(f"Benchmarking `{benchmark['benchmark']}`")
                    partial_result = metric(benchmark["benchmark"])
                    bar.refresh(nolock=True)
                    partial_results.append(partial_result)
                    if "after" in benchmark:
                        run_multiple_commands(benchmark["after"])
                        bar.refresh(nolock=True)
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
