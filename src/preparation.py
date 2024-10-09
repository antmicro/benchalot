from itertools import product
from logging import getLogger
from metrics import BaseMetric, TimeMetric, StdOutMetric


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
    if "options" in config and "isolate-cpus" in config["options"]:
        for i, c in enumerate(config["run"]["benchmark"]):
            config["run"]["benchmark"][i] = "cset shield --exec -- " + c
    benchmarks = []
    logger.info("Preparing benchmarks...")
    if "matrix" not in config:
        logger.debug("`matrix` not found in the config.")
        benchmarks.append(config["run"])
        benchmarks[0]["matrix"] = {}
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

            if "after" in config["run"]:
                benchmark["after"] = prepare_commands(
                    config["run"]["after"], var_combination
                )
            benchmarks.append(benchmark)
    logger.info("Finished preparing benchmarks.")
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks


def prepare_metrics(config):
    metrics = []
    for metric in config["run"]["metrics"]:
        metric_constructor = BaseMetric
        if metric == "time":
            metric_constructor = TimeMetric
        elif metric == "stdout":
            metric_constructor = StdOutMetric
        metrics.append(metric_constructor)
    return metrics
