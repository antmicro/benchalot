from logging import getLogger
from benchmarker.interpolate import (
    create_variable_combinations,
    interpolate_variables,
)
from dataclasses import dataclass
from itertools import chain
from benchmarker.config import ConfigFile

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
        custom_metrics: List of custom_metrics (names and commands) to be gathered during execution.
        cleanup: Commands to be executed after the measurement, not multiplied by number of samples.
    """

    matrix: dict[str, str]
    setup: list[str]
    prepare: list[str]
    benchmark: dict[str, list[str]]
    conclude: list[str]
    custom_metrics: list[dict[str, str]]
    cleanup: list[str]
    env: dict[str, str]
    cwd: str | None
    save_output: str | None


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
    exclude: list[dict[str, str | int | float | dict]],
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


def prepare_benchmarks(config: ConfigFile) -> list[PreparedBenchmark]:
    """Prepare benchmark commands.

    Args:

    Returns:
        list[PreparedBenchmark]: List of unique benchmarks containing their variable combination, modified commands and metrics.
    """
    if config.system.isolate_cpus:
        for name in config.benchmark:
            commands = config.benchmark[name]
            for i, c in enumerate(commands):
                config.benchmark[name][i] = "cset shield --exec -- " + c
    benchmarks: list[PreparedBenchmark] = []
    logger.info("Preparing benchmarks...")
    if not config.matrix:
        logger.debug("`matrix` not found in the config.")
        cm = process_custom_metrics(config.custom_metrics)
        prepared_benchmark = PreparedBenchmark(
            matrix={},
            setup=config.setup,
            prepare=config.prepare,
            benchmark=config.benchmark,
            conclude=config.conclude,
            custom_metrics=cm,
            cleanup=config.cleanup,
            env=config.env,
            cwd=config.cwd,
            save_output=config.save_output,
        )
        benchmarks.append(prepared_benchmark)
    else:
        logger.debug("Creating variable combinations...")
        var_combinations = create_variable_combinations(**config.matrix)
        for var_combination in chain(var_combinations, config.include):
            if exclude_combination(var_combination, config.exclude):
                continue
            setup = interpolate_commands(config.setup, var_combination)
            prepare = interpolate_commands(config.prepare, var_combination)
            benchmark = {}
            for name in config.benchmark:
                benchmark[name] = interpolate_commands(
                    config.benchmark[name], var_combination
                )
            custom_metrics = process_custom_metrics(
                config.custom_metrics, var_combination
            )

            conclude = interpolate_commands(config.conclude, var_combination)
            cleanup = interpolate_commands(config.cleanup, var_combination)

            env = config.env.copy()
            for var in env:
                env[var] = interpolate_variables(env[var], var_combination)
            cwd: str | None
            if config.cwd:
                cwd = interpolate_variables(config.cwd, var_combination)
            else:
                cwd = config.cwd
            if config.save_output:
                save_output = interpolate_variables(config.save_output, var_combination)
            else:
                save_output = config.save_output
            prepared_benchmark = PreparedBenchmark(
                matrix=var_combination,
                setup=setup,
                prepare=prepare,
                benchmark=benchmark,
                conclude=conclude,
                custom_metrics=custom_metrics,
                cleanup=cleanup,
                env=env,
                cwd=cwd,
                save_output=save_output,
            )
            benchmarks.append(prepared_benchmark)
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
