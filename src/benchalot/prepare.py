from logging import getLogger
from benchalot.interpolate import (
    create_variable_combinations,
    interpolate_variables,
)
from dataclasses import dataclass
from benchalot.config import ConfigFile
from benchalot.output_constants import TIME_STAMP_COLUMN, TIME_STAMP
from os.path import expandvars, expanduser

logger = getLogger(f"benchalot.{__name__}")


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
        env: Evironment variable values set for the benchmark.
        cwd: Working directory of the benchmark commands.
        save_output: Filename of a log file which will be used to save command output.
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


def convert_to_list(commands) -> list[str]:
    if isinstance(commands, str):
        return [c for c in commands.split("\n") if len(c) > 0]
    else:
        return commands


def prepare_benchmarks(config: ConfigFile) -> list[PreparedBenchmark]:
    """Prepare benchmark commands.

    Args:
        config: Object representing configuration file.
    Returns:
        list[PreparedBenchmark]: List of unique benchmarks containing their variable combination, modified commands and metrics.
    """
    base_setup = convert_to_list(config.setup)
    base_prepare = convert_to_list(config.prepare)
    base_benchmark = {}
    for stage in config.benchmark:
        base_benchmark[stage] = convert_to_list(config.benchmark[stage])
    base_conclude = convert_to_list(config.conclude)
    base_cleanup = convert_to_list(config.cleanup)
    if config.system.isolate_cpus:
        for name in base_benchmark:
            commands = base_benchmark[name]
            for i, c in enumerate(commands):
                base_benchmark[name][i] = "cset shield --exec -- " + c
    benchmarks: list[PreparedBenchmark] = []
    logger.info("Preparing benchmarks...")
    logger.debug("Creating variable combinations...")
    var_combinations = list(create_variable_combinations(**config.matrix))
    var_combinations += config.include
    for var_combination in var_combinations:
        if not var_combination and len(var_combinations) > 1:
            continue
        if exclude_combination(var_combination, config.exclude):
            continue

        tmp = {TIME_STAMP_COLUMN: TIME_STAMP}
        tmp.update(var_combination)
        var_combination = tmp

        setup = interpolate_commands(base_setup, var_combination)
        prepare = interpolate_commands(base_prepare, var_combination)
        benchmark = {}
        for name in base_benchmark:
            benchmark[name] = interpolate_commands(
                base_benchmark[name], var_combination
            )
        conclude = interpolate_commands(base_conclude, var_combination)
        custom_metrics = process_custom_metrics(config.custom_metrics, var_combination)
        cleanup = interpolate_commands(base_cleanup, var_combination)

        env = config.env.copy()
        for var in env:
            env[var] = interpolate_variables(env[var], var_combination)
            env[var] = expandvars(env[var])
            env[var] = expanduser(env[var])
        cwd: str | None
        if config.cwd:
            cwd = interpolate_variables(config.cwd, var_combination)
        else:
            cwd = config.cwd
        save_output: str | None
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
