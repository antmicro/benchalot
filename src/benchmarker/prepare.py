from logging import getLogger
from re import findall
from benchmarker.interpolate import (
    VAR_REGEX,
    create_variable_combinations,
    interpolate_variables,
)
from dataclasses import dataclass
from itertools import chain

logger = getLogger(f"benchmarker.{__name__}")


@dataclass
class PreparedBenchmark:
    """Structure representing a single benchmark.

    Attributes:
        matrix: Combination of variable values used for this benchmark.
        pre_benchmark: Commands to be executed before the measurement.
        benchmark: Commands to be measured.
        post_benchmark: Commands to be executed after the measurement.
        custom_metrics: List of custom_metrics (names and commands) to be gathered during execution.
    """

    matrix: dict[str, str]
    pre_benchmark: list[str]
    benchmark: dict[str, list[str]]
    post_benchmark: list[str]
    custom_metrics: list[dict[str, str]]


def interpolate_commands(commands: list, variables: dict[str, str | int]) -> list[str]:
    """Replace variable references with values in multiple commands.

    Args:
        command: List of commands.
        variables: Variable names paired with values.
    Returns:
        list[str]: List of commands with all variable references replaced.
    """
    prepared_commands = []
    for command in commands:
        prepared_commands.append(interpolate_variables(command, variables))
    return prepared_commands


def exclude(
    var_value_assignments: dict[str, int | str],
    exclusions: list[dict[str, int | str]],
) -> bool:
    """Check if given set of value assignments should be excluded based on exclusions list.

    Args:
        var_value_assignments:  Assignment of variable values.
        exclusions: List of exclusions.

    Returns:
        bool: `True` if assignment should be excluded, otherwiese `False`.
    """
    for exclusion in exclusions:
        if exclusion.items() <= var_value_assignments.items():
            return True
    return False


def prepare_init_cleanup_commands(
    init: list[str],
    cleanup: list[str],
    matrix: dict[str, list],
    exclusions: list[dict[str, int | str]],
    inclusions: list[dict[str, int | str]],
) -> tuple[list[str], list[str]]:
    """Create command variants for each combination of values of variables present in init and cleanup sections.

    Args:
        run_config: Configuration file's `run` section.
        matrix: Configuration file's `matrix` section.
        exclusions: Configuration file's `exclusions` section, which excludes given value combinations.
        inclusions: Configuration file's `inclusions` section, which includes given value combinations.

    Returns:
        tuple[list[str], list[str]]: Two lists with command combinations for each section.
    """
    logger.info("Preparing 'init' and 'cleanup' commands...")

    ret = []
    for section in [init, cleanup]:
        curr_section_commands = []
        if section:
            vars = set()
            for command in section:
                for var_name in findall(VAR_REGEX, command):
                    vars.add(var_name.split(".")[0])
            if vars:
                var_combinations = create_variable_combinations(
                    **{k: v for k, v in matrix.items() if k in vars}
                )
                relevant_inclusions = []
                for var_combination in inclusions:
                    for var in var_combination:
                        if var in vars:
                            relevant_inclusions.append(var_combination)
                for var_combination in chain(var_combinations, relevant_inclusions):
                    if exclude(var_combination, exclusions):
                        continue
                    curr_section_commands += interpolate_commands(
                        section, var_combination
                    )
            else:
                curr_section_commands += section
        ret.append(curr_section_commands)

    logger.debug(ret)
    return (ret[0], ret[1])


def process_custom_metrics(
    metrics: list[dict[str, str]],
    variables: dict[str, str | int] | None = None,
) -> list[dict[str, str]]:
    """Divide metrics into custom and built-in metrics.

    Args:
        metrics: List of metrics.
        variables: Variable names paired with their values. Used with custom metrics.

    Returns:
        List of custom metrics.
    """
    custom_metrics = []
    for metric in metrics:
        metric_command = list(metric.items())[0][1]  # type: ignore
        metric_name = list(metric.items())[0][0]  # type: ignore
        if variables:
            metric_command = interpolate_variables(metric_command, variables)
        custom_metrics.append({metric_name: metric_command})
    return custom_metrics


def prepare_benchmarks(
    bench: dict[str, list[str]],
    pre_bench: list[str],
    post_bench: list[str],
    custom_metrics: list[dict],
    matrix: dict[str, list[str]],
    exclusions: list[dict[str, int | str]],
    inclusions: list[dict[str, int | str]],
    isolate_cpus: bool,
) -> list[PreparedBenchmark]:
    """Prepare `pre_benchmark`, `benchmark` and `post_benchmark` commands so that they can be executed as part of one benchmark.

    Args:
        run_config: Configuration file's `run` section.
        matrix: Configuration file's `matrix` section.
        exclusions: Configuration file's `exclusions` section, which excludes given var combinations.
        inclusions: Configuration file's `inclusions` section, which includes given value combinations.
        isolate_cpus: Whether to prepend `cset shield --exec -- ` to `benchmark` commands.

    Returns:
        list[PreparedBenchmark]: List of unique benchmarks containing their variable combination, modified commands and metrics.
    """
    if isolate_cpus:
        for name in bench:
            commands = bench[name]
            for i, c in enumerate(commands):
                bench[name][i] = "cset shield --exec -- " + c
    benchmarks: list[PreparedBenchmark] = []
    logger.info("Preparing benchmarks...")
    if not matrix:
        logger.debug("`matrix` not found in the config.")
        cm = process_custom_metrics(custom_metrics)
        benchmark = PreparedBenchmark(
            matrix={},
            pre_benchmark=pre_bench,
            benchmark=bench,
            post_benchmark=post_bench,
            custom_metrics=cm,
        )
        benchmarks.append(benchmark)
    else:
        logger.debug("Creating variable combinations...")
        var_combinations = create_variable_combinations(**matrix)
        for var_combination in chain(var_combinations, inclusions):
            if exclude(var_combination, exclusions):
                continue
            pre_benchmark = interpolate_commands(pre_bench, var_combination)
            post_benchmark = interpolate_commands(post_bench, var_combination)
            b = {}
            for name in bench:
                b[name] = interpolate_commands(bench[name], var_combination)
            cm = process_custom_metrics(custom_metrics, var_combination)
            benchmark = PreparedBenchmark(
                matrix=var_combination,
                pre_benchmark=pre_benchmark,
                benchmark=b,
                post_benchmark=post_benchmark,
                custom_metrics=cm,
            )
            benchmarks.append(benchmark)
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
