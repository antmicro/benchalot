from itertools import product
from logging import getLogger
from metrics import (
    measure_time,
    gather_stdout,
    gather_stderr,
    gather_exit_codes,
    custom_metric,
)
from functools import partial
from copy import deepcopy

logger = getLogger(f"benchmarker.{__name__}")


def create_variable_combinations(**kwargs):
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


def prepare_commands(commands: list, var_combination) -> list:
    def prepare_command(command: str, var_combination) -> str:
        for var in var_combination:
            command = command.replace(f"$matrix.{var}", str(var_combination[var]))
        return command

    prepared_commands = []
    for command in commands:
        prepared_commands.append(prepare_command(command, var_combination))
    return prepared_commands


def prepare_benchmarks(config) -> list:
    metrics = []
    for metric in config["run"]["metrics"]:
        if metric == "time":
            metrics.append(measure_time)
        elif metric == "stdout":
            metrics.append(gather_stdout)
        elif metric == "stderr":
            metrics.append(gather_stderr)
        elif metric == "exit-codes":
            metrics.append(gather_exit_codes)
        else:
            metrics.append(partial(custom_metric, metric.split("@")[1]))
    if "options" in config and "isolate-cpus" in config["options"]:
        for i, c in enumerate(config["run"]["benchmark"]):
            config["run"]["benchmark"][i] = "cset shield --exec -- " + c
    benchmarks = []
    logger.info("Preparing benchmarks...")
    if "matrix" not in config:
        logger.debug("`matrix` not found in the config.")
        benchmarks.append(deepcopy(config["run"]))
        benchmarks[0]["matrix"] = {}
        benchmarks[0]["metrics"] = metrics
    else:
        logger.debug("Creating variable combinations...")
        var_combinations = list(create_variable_combinations(**config["matrix"]))
        logger.debug(f"Variable combinations {var_combinations}")
        for var_combination in var_combinations:
            benchmark = {"matrix": var_combination}
            if "before" in config["run"]:
                benchmark["before"] = prepare_commands(
                    config["run"]["before"], var_combination
                )

            benchmark["benchmark"] = prepare_commands(
                config["run"]["benchmark"], var_combination
            )
            benchmark["metrics"] = metrics
            if "after" in config["run"]:
                benchmark["after"] = prepare_commands(
                    config["run"]["after"], var_combination
                )
            benchmarks.append(benchmark)
    logger.info("Finished preparing benchmarks.")
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
