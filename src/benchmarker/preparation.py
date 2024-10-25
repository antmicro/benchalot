from itertools import product
from logging import getLogger
from benchmarker.metrics import (
    measure_time,
    gather_stdout,
    gather_stderr,
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


def name_benchmark_steps(
    benchmarks: list[str] | dict[str, list[str]],
) -> dict[str, list[str]]:
    if type(benchmarks) is dict:
        return benchmarks
    named_benchmarks = dict()
    for i, benchmark in enumerate(benchmarks):
        named_benchmarks["step_" + str(i)] = [benchmark]
    return named_benchmarks


def prepare_benchmarks(
    run_config: dict, matrix: dict[str, list[str]], isolate_cpus: bool
) -> list:
    metrics_functions = []
    for metric in run_config["metrics"]:
        if metric == "time":
            metrics_functions.append(measure_time)
        elif metric == "stdout":
            metrics_functions.append(gather_stdout)
        elif metric == "stderr":
            metrics_functions.append(gather_stderr)
        else:
            metrics_functions.append(
                partial(
                    custom_metric,
                    list(metric.items())[0][1],
                    list(metric.items())[0][0],
                )
            )
    if isolate_cpus:
        for i, c in enumerate(run_config["benchmark"]):
            run_config["benchmark"][i] = "cset shield --exec -- " + c
    benchmarks = []
    logger.info("Preparing benchmarks...")
    if not matrix:
        logger.debug("`matrix` not found in the config.")
        benchmarks.append(deepcopy(run_config))
        benchmarks[0]["matrix"] = {}
        benchmarks[0]["metrics"] = metrics_functions
    else:
        logger.debug("Creating variable combinations...")
        var_combinations = list(create_variable_combinations(**matrix))
        logger.debug(f"Variable combinations {var_combinations}")
        for var_combination in var_combinations:
            benchmark = {"matrix": var_combination}
            for section in ["before", "after"]:
                benchmark[section] = prepare_commands(
                    run_config[section], var_combination
                )
            for name in run_config["benchmark"]:
                benchmark["benchmark"][name] = prepare_commands(
                    run_config["benchmark"][name], var_combination
                )
            benchmark["metrics"] = metrics_functions
            benchmarks.append(benchmark)
    logger.info("Finished preparing benchmarks.")
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
