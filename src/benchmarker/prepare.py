from logging import getLogger
from re import findall
from benchmarker.config import RunSection
from benchmarker.interpolate import (
    VAR_REGEX,
    create_variable_combinations,
    interpolate_variables,
)
from dataclasses import dataclass

logger = getLogger(f"benchmarker.{__name__}")


@dataclass
class PreparedBenchmark:
    """Structure representing a single benchmark.

    Attributes:
        matrix: Combination of variable values used for this benchmark.
        before: Commands to be executed before the measurement.
        benchmark: Commands to be measured.
        after: Commands to be executed after the measurement.
        custom_metrics: List of custom_metrics (names and commands) to be gathered during execution.
    """

    matrix: dict[str, str]
    before: list[str]
    benchmark: dict[str, list[str]]
    after: list[str]
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
    var_value_assignments: dict[str, int | float | str],
    exclusions: list[dict[str, int | str | float]],
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


def prepare_before_after_all_commands(
    run_config: RunSection,
    matrix: dict[str, list],
    exclusions: list[dict[str, int | str | float]],
) -> tuple[list[str], list[str]]:
    """Create command variants for each combination of values of variables present in before-all and after-all sections.

    Args:
        run_config: Configuration file's `run` section.
        matrix: Configuration file's `matrix` section.
        exclusions: Configuration file's `exclusions` section, which excludes given var combinations.

    Returns:
        tuple[list[str], list[str]]: Two lists with command combinations for each section.
    """
    logger.info("Preparing 'before-all' and 'after-all' commands...")

    ret = []
    for section in [run_config.before_all, run_config.after_all]:
        curr_section_commands = []
        if section:
            vars = set()
            for command in section:
                for var_name in findall(VAR_REGEX, command):
                    vars.add(var_name)
            if vars:
                var_combinations = create_variable_combinations(
                    **{k: v for k, v in matrix.items() if k in vars}
                )
                for var_combination in var_combinations:
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
    run_config: RunSection,
    matrix: dict[str, list[str]],
    exclusions: list[dict[str, int | str | float]],
    isolate_cpus: bool,
) -> list[PreparedBenchmark]:
    """Prepare `before`, `benchmark` and `after` commands so that they can be executed as part of one benchmark.

    Args:
        run_config: Configuration file's `run` section.
        matrix: Configuration file's `matrix` section.
        exclusions: Configuration file's `exclusions` section, which excludes given var combinations.
        isolate_cpus: Whether to prepend `cset shield --exec -- ` to `benchmark` commands.

    Returns:
        list[PreparedBenchmark]: List of unique benchmarks containing their variable combination, modified commands and metrics.
    """
    if isolate_cpus:
        for name in run_config.benchmark:
            commands = run_config.benchmark[name]
            for i, c in enumerate(commands):
                run_config.benchmark[name][i] = "cset shield --exec -- " + c
    benchmarks: list[PreparedBenchmark] = []
    logger.info("Preparing benchmarks...")
    if not matrix:
        logger.debug("`matrix` not found in the config.")
        custom_metrics = process_custom_metrics(run_config.custom_metrics)
        benchmark = PreparedBenchmark(
            matrix={},
            before=run_config.before,
            benchmark=run_config.benchmark,
            after=run_config.after,
            custom_metrics=custom_metrics,
        )
        benchmarks.append(benchmark)
    else:
        logger.debug("Creating variable combinations...")
        var_combinations = list(create_variable_combinations(**matrix))
        logger.debug(f"Variable combinations {var_combinations}")
        for var_combination in var_combinations:
            if exclude(var_combination, exclusions):
                continue
            before = interpolate_commands(run_config.before, var_combination)
            after = interpolate_commands(run_config.after, var_combination)
            bench = {}
            for name in run_config.benchmark:
                bench[name] = interpolate_commands(
                    run_config.benchmark[name], var_combination
                )
            custom_metrics = process_custom_metrics(
                run_config.custom_metrics, var_combination
            )
            benchmark = PreparedBenchmark(
                matrix=var_combination,
                before=before,
                benchmark=bench,
                after=after,
                custom_metrics=custom_metrics,
            )
            benchmarks.append(benchmark)
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
