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
from re import findall

logger = getLogger(f"benchmarker.{__name__}")

VAR_REGEX = r"{{[a-zA-Z0-9_\-.]*}}"


def create_variable_combinations(**kwargs):
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


def prepare_command(command: str, var_combination) -> str:
    for var in var_combination:
        command = command.replace("{{" + var + "}}", str(var_combination[var]))
    return command


def prepare_commands(commands: list, var_combination) -> list:
    prepared_commands = []
    for command in commands:
        prepared_commands.append(prepare_command(command, var_combination))
    return prepared_commands


def name_benchmark_stages(
    benchmarks: list[str] | dict[str, list[str]],
) -> dict[str, list[str]]:
    if type(benchmarks) is dict:
        return benchmarks
    elif type(benchmarks) is list:
        return {"onlystage": benchmarks}
    assert "Unreachable!"
    return None  # type: ignore


def prepare_before_after_all_commands(
    run_config: dict, matrix: dict[str, list]
) -> list[list[str]]:
    ret = []
    for section in ["before-all", "after-all"]:
        curr_section_commands = []
        if run_config[section]:
            for command in run_config[section]:
                vars = set()
                for var_name in findall(VAR_REGEX, command):
                    vars.add(var_name.removeprefix("{{").removesuffix("}}"))
                if vars:
                    var_combos = create_variable_combinations(
                        **{k: v for k, v in matrix.items() if k in vars}
                    )
                    for var_combo in var_combos:
                        curr_section_commands.append(
                            prepare_command(command, var_combo)
                        )
                else:
                    curr_section_commands.append(command)
        ret.append(curr_section_commands)
    return ret


3


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
        for name in run_config["benchmark"]:
            for i, c in enumerate(run_config["benchmark"][name]):
                run_config["benchmark"][name][i] = "cset shield --exec -- " + c
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
            benchmark["benchmark"] = {}
            for name in run_config["benchmark"]:
                benchmark["benchmark"][name] = prepare_commands(
                    run_config["benchmark"][name], var_combination
                )
            benchmark["metrics"] = metrics_functions
            benchmarks.append(benchmark)
    logger.info("Finished preparing benchmarks.")
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
