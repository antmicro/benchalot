from subprocess import Popen, PIPE
from logging import getLogger, INFO, ERROR
from tqdm import tqdm
from os import getcwd


logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")
working_directory = getcwd()


def set_working_directory(cwd):
    global working_directory
    working_directory = cwd


def check_return_code(command, code):
    if code != 0:
        logger.error(f"Subprocess '{command}' exited abnormally (exit code {code})")
        exit(1)


def execute_command(command):
    global working_directory
    return Popen(command, shell=True, stdout=PIPE, stderr=PIPE, cwd=working_directory)


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
    process = execute_command(command)
    total = handle_output(process, capture_stdout, capture_stderr)
    result = process.wait()
    check_return_code(command, result)
    return total


def execute_section(commands: list[str], section_name=""):
    if not commands:
        return
    logger.info(f"Executing '{section_name}' section...")
    logger.debug(f"Executing: {commands}")
    bar = tqdm(commands, leave=False, delay=1)
    for c in bar:
        bar.set_description(c[:20] + "..." if len(c) > 20 else c, refresh=False)
        execute_and_handle_output(c)
    logger.info(f"Execution of '{section_name}' section finished.")


def perform_benchmarks(benchmarks: list, samples: int) -> dict[str, list]:
    results: dict[str, list] = dict()
    logger.info("Performing benchmarks...")
    bar = tqdm(
        desc="Performing benchmarks.",
        total=(len(benchmarks) * samples * len(benchmarks[0]["metrics"])),
        unit="benchmark",
        leave=False,
        mininterval=1,
    )
    for benchmark in benchmarks:
        try:
            for _ in range(0, samples):
                partial_results = dict()
                for metric in benchmark["metrics"]:
                    logger.debug(f"Running benchmark: {benchmark}")

                    execute_section(benchmark["before"], "before")

                    text = str(
                        [benchmark["benchmark"][key] for key in benchmark["benchmark"]]
                    )
                    text = text.replace("[", "")
                    text = text.replace("]", "")
                    bar.set_description(
                        f"Executing {text[:20] + '...' if len(text)>20 else text}"
                    )
                    partial_result = metric(benchmark["benchmark"])
                    bar.refresh(nolock=True)
                    partial_results.update(partial_result)

                    execute_section(benchmark["after"], "after")
                    bar.update(1)
                for key in benchmark["matrix"]:
                    results.setdefault(key, []).append(benchmark["matrix"][key])

                for key in partial_results:
                    results.setdefault(key, []).append(partial_results[key])

        except KeyboardInterrupt:
            logger.warning("Stopped benchmarks.")
            logger.warning("Creating output...")
            break
    bar.close()
    logger.info("Finished performing benchmarks.")
    logger.debug(f"Benchmark results: {results}")
    return results
