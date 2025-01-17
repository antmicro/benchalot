from logging import getLogger
from benchmarker.interpolate import (
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
        setup: Commands to be executed before the measurement, not multiplied by number of samples.
        prepare: Commands to be executed before the measurement.
        benchmark: Commands to be measured.
        conclude: Commands to be executed after the measurement.
        cleanup: Commands to be executed after the measurement, not multiplied by number of samples.
        custom_metrics: List of custom_metrics (names and commands) to be gathered during execution.
    """

    matrix: dict[str, str]
    setup: list[str]
    prepare: list[str]
    benchmark: dict[str, list[str]]
    custom_metrics: list[dict[str, str]]
    conclude: list[str]
    cleanup: list[str]


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


def exclude_combination(
    var_value_assignments: dict[str, int | str],
    exclude: list[dict[str, int | str]],
) -> bool:
    """Check if given set of value assignments should be excluded based on exclude list.

    Args:
        var_value_assignments:  Assignment of variable values.
        exclude: List of exclude.

    Returns:
        bool: `True` if assignment should be excluded, otherwiese `False`.
    """
    for exclusion in exclude:
        if exclusion.items() <= var_value_assignments.items():
            return True
    return False


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
    setup: list[str],
    prepare: list[str],
    benchmark: dict[str, list[str]],
    conclude: list[str],
    cleanup: list[str],
    custom_metrics: list[dict],
    matrix: dict[str, list[str]],
    exclude: list[dict[str, int | str]],
    include: list[dict[str, int | str]],
    isolate_cpus: bool,
) -> list[PreparedBenchmark]:
    """Prepare benchmark commands.

    Args:
        setup: Configuration file's `setup` section.
        prepare: Configuration file's `prepare` section.
        benchmark: Configuration file's `benchmark` section.
        conclude: Configuration file's `conclude` section.
        cleanup: Configuration file's `cleanup` section.
        cusom_metrics: Configuration file's `custom-metrics` section.
        matrix: Configuration file's `matrix` section.
        exclude: Configuration file's `exclude` section, which excludes given var combinations.
        include: Configuration file's `include` section, which includes given value combinations.
        isolate_cpus: Whether to prepend `cset shield --exec -- ` to `benchmark` commands.

    Returns:
        list[PreparedBenchmark]: List of unique benchmarks containing their variable combination, modified commands and metrics.
    """
    if isolate_cpus:
        for name in benchmark:
            commands = benchmark[name]
            for i, c in enumerate(commands):
                benchmark[name][i] = "cset shield --exec -- " + c
    benchmarks: list[PreparedBenchmark] = []
    logger.info("Preparing benchmarks...")
    if not matrix:
        logger.debug("`matrix` not found in the config.")
        cm = process_custom_metrics(custom_metrics)
        prepared_benchmark = PreparedBenchmark(
            matrix={},
            setup=setup,
            prepare=prepare,
            benchmark=benchmark,
            custom_metrics=cm,
            conclude=conclude,
            cleanup=cleanup,
        )
        benchmarks.append(prepared_benchmark)
    else:
        logger.debug("Creating variable combinations...")
        var_combinations = create_variable_combinations(**matrix)
        for var_combination in chain(var_combinations, include):
            if exclude_combination(var_combination, exclude):
                continue
            stp = interpolate_commands(setup, var_combination)
            pre_bench = interpolate_commands(prepare, var_combination)
            bench = {}
            for name in benchmark:
                bench[name] = interpolate_commands(benchmark[name], var_combination)
            cm = process_custom_metrics(custom_metrics, var_combination)

            conc_bench = interpolate_commands(conclude, var_combination)
            clean = interpolate_commands(cleanup, var_combination)
            prepared_benchmark = PreparedBenchmark(
                matrix=var_combination,
                setup=stp,
                prepare=pre_bench,
                benchmark=bench,
                custom_metrics=cm,
                conclude=conc_bench,
                cleanup=clean,
            )
            benchmarks.append(prepared_benchmark)
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
