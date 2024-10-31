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
from re import sub, findall
from collections.abc import Callable
from typing import Any


logger = getLogger(f"benchmarker.{__name__}")

VAR_REGEX = r"{{[a-zA-Z0-9_\-.]*}}"


def create_variable_combinations(**kwargs):
    """Create all possible variable values combinations

    Args:
        kwargs: Dictionary containing list of variable values.
    """
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


def prepare_command(command: str, variables: dict[str, str | int]) -> str:
    """Replace variable references with values.

    Args:
        command: Command to be modified.
        variables: Variable names paired with values.

    Returns:
        str: Command with all variable references replaced.
    """

    def replace_substring(match):
        variable_name = match.group(0).removeprefix("{{").removesuffix("}}")
        try:
            return str(variables[variable_name])
        except KeyError:
            logger.critical(f"'{command}': Variable '{variable_name}' not found")
            exit(1)

    new_command = sub(VAR_REGEX, replace_substring, command)
    return new_command


def prepare_commands(commands: list, variables: dict[str, str | int]) -> list[str]:
    """Replace variable references with values in multiple commands.

    Args:
        command: List of commands.
        variables: Variable names paired with values.
    Returns:
        list[str]: List of commands with all variable references replaced.
    """
    prepared_commands = []
    for command in commands:
        prepared_commands.append(prepare_command(command, variables))
    return prepared_commands


def name_benchmark_stages(
    benchmarks: list[str] | dict[str, list[str]]
) -> dict[str, list[str]]:
    """Transform list of commands to dictionary of lists of commands.

    Args:
        benchmarks: List or dictionary of lists of commands.

    Returns:
        dict[str, list[str]]: Stage names paired with lists of commands.
    """
    if type(benchmarks) is dict:
        return benchmarks
    elif type(benchmarks) is list:
        return {"onlystage": benchmarks}
    assert "Unreachable!"
    return None  # type: ignore


def prepare_before_after_all_commands(
    run_config: dict, matrix: dict[str, list]
) -> tuple[list[str], list[str]]:
    """Create command variants for each combination of values of variables present in before-all and after-all sections.

    Args:
        run_config: Configuration file's `run` section.
        matrix: Configuration file's `matrix` section.

    Returns:
        tuple[list[str], list[str]]: Two lists with command combinations for each section.
    """
    logger.info("Preparing 'before-all' and 'after-all' commands...")
    ret = []
    for section in ["before-all", "after-all"]:
        curr_section_commands = []
        if run_config[section]:
            vars = set()
            for command in run_config[section]:
                for var_name in findall(VAR_REGEX, command):
                    vars.add(var_name.removeprefix("{{").removesuffix("}}"))
            if vars:
                var_combinations = create_variable_combinations(
                    **{k: v for k, v in matrix.items() if k in vars}
                )
                for var_combination in var_combinations:
                    curr_section_commands += prepare_commands(
                        run_config[section], var_combination
                    )
            else:
                curr_section_commands += run_config[section]
        ret.append(curr_section_commands)
    logger.info("Finished preparing 'before-all' and 'after-all' commands.")
    logger.debug(ret)
    return (ret[0], ret[1])


def get_metrics_functions(
    metrics: list[str | dict[str, str]],
    variables: dict[str, str | int] | None = None,
) -> list[Callable[[dict], dict]]:
    """Get list of callable metrics functions.

    Args:
        metrics: List of metric names.
        variables: Variable names paired with their values. Used with custom metrics.

    Returns:
        list[Callable[[dict],dict]]: List of callable objects that perform specified measurements.
    """
    metrics_functions: list[Callable[[dict[Any, Any]], dict[Any, Any]]] = []
    for metric in metrics:
        if metric == "time":
            metrics_functions.append(measure_time)
        elif metric == "stdout":
            metrics_functions.append(gather_stdout)
        elif metric == "stderr":
            metrics_functions.append(gather_stderr)
        else:
            metric_command = list(metric.items())[0][1]  # type: ignore
            metric_name = list(metric.items())[0][0]  # type: ignore
            if variables:
                metric_command = prepare_command(metric_command, variables)
            metrics_functions.append(
                partial(custom_metric, metric_command, metric_name)
            )
    return metrics_functions


def prepare_benchmarks(
    run_config: dict, matrix: dict[str, list[str]], isolate_cpus: bool
) -> list[dict]:
    """Prepare `before`, `benchmark` and `after` commands so that they can be executed as part of one benchmark.

    Args:
        run_config: Configuration file's `run` section.
        matrix: Configuration file's `matrix` section.
        isolate_cpus: Whether to prepend `cset shield --exec -- ` to `benchmark` commands.

    Returns:
        list[dict]: List of unique benchmarks containing their variable combination, modified commands and metrics.
    """
    if isolate_cpus:
        for name in run_config["benchmark"]:
            for i, c in enumerate(run_config["benchmark"][name]):
                run_config["benchmark"][name][i] = "cset shield --exec -- " + c
    benchmarks = []
    logger.info("Preparing benchmarks...")
    if not matrix:
        logger.debug("`matrix` not found in the config.")
        benchmarks.append(deepcopy(run_config))
        benchmarks[0]["matrix"] = {}
        benchmarks[0]["metrics"] = get_metrics_functions(metrics=run_config["metrics"])
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
            benchmark["benchmark"] = {}
            for name in run_config["benchmark"]:
                benchmark["benchmark"][name] = prepare_commands(
                    run_config["benchmark"][name], var_combination
                )
            benchmark["metrics"] = get_metrics_functions(
                run_config["metrics"], var_combination
            )
            benchmarks.append(benchmark)
    logger.info("Finished preparing benchmarks.")
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
