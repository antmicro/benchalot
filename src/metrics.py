from time import monotonic_ns
from subprocess import run, PIPE, Popen
from logging import getLogger
from execution import execute_command

logger = getLogger(f"benchmarker.{__name__}")
command_logger = getLogger("run")


def measure_time(commands):
    total = 0
    for command in commands:
        start = monotonic_ns()
        execute_command(command)
        total += monotonic_ns() - start
    return total / 1e9


def gather_output(process, stdout=False, stderr=False):
    total = ""
    with process.stdout as output:  # type: ignore
        for line in output:
            if len(line) > 0:
                command_logger.info(line.decode("utf-8").strip())
                if stdout:
                    total += line.decode("utf-8").strip()
    with process.stderr as output:  # type: ignore
        for line in output:
            if len(line) > 0:
                command_logger.info(line.decode("utf-8").strip())
                if stderr:
                    total += line.decode("utf-8").strip()
    return total


def gather_stdout(commands):
    total = ""
    for command in commands:
        process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
        total += gather_output(process, stdout=True)
        result = process.wait()
        if result != 0:
            logger.critical(
                f"Subprocess '{command}' exited abnormally (exit code {result})"
            )
            exit(1)
    return total


def gather_stderr(commands):
    total = ""
    for command in commands:
        process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
        total += gather_output(process, stderr=True)
        result = process.wait()
        if result != 0:
            logger.critical(
                f"Subprocess '{command}' exited abnormally (exit code {result})"
            )
            exit(1)
    return total


def gather_exit_codes(commands):
    exit_codes = []
    for command in commands:
        result = execute_command(command)
        exit_codes.append(result)
    if len(commands) == 1:
        return exit_codes[0]
    return tuple(exit_codes)


def custom_metric(metric, commands):
    args = '" "'.join(commands)
    args = ' "' + args
    args += '"'
    result = run(metric + args, shell=True, capture_output=True)
    if result.returncode != 0:
        logger.critical(
            f"Subprocess '{metric}' exited abnormally (exit code {result.returncode})"
        )
        logger.critical(result.stderr.decode("utf-8").strip())
        exit(1)
    return result.stdout.decode("utf-8").strip()
