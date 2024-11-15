from itertools import product
from logging import getLogger
from benchmarker.metrics import (
    measure_time,
    gather_stdout,
    gather_stderr,
    custom_metric,
)
from functools import partial
from re import sub, findall
from collections.abc import Callable
from benchmarker.structs import BenchmarkResult, PreparedBenchmark
from benchmarker.validation import RunSection

logger = getLogger(f"benchmarker.{__name__}")

VAR_REGEX = r"{{([a-zA-Z0-9_\-.]+)}}"


def create_variable_combinations(**kwargs):
    """Create all possible variable values combinations

    Args:
        kwargs: Dictionary containing list of variable values.
    """
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


def interpolate_command(command: str, variables: dict[str, str | int]) -> str:
    """Replace variable references with values.

    Args:
        command: Command to be modified.
        variables: Variable names paired with values.

    Returns:
        str: Command with all variable references replaced.
    """

    def replace_substring(match):
        variable_name = match.group(1)
        try:
            return str(variables[variable_name])
        except KeyError:
            logger.critical(f"'{command}': Variable '{variable_name}' not found")
            exit(1)

    new_command = sub(VAR_REGEX, replace_substring, command)
    return new_command


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
        prepared_commands.append(interpolate_command(command, variables))
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

    logger.info("Finished preparing 'before-all' and 'after-all' commands.")
    logger.debug(ret)
    return (ret[0], ret[1])


def get_metric_function(
    metric: str | dict[str, str],
    variables: dict[str, str | int] | None = None,
) -> Callable[[dict], BenchmarkResult]:
    """Get list of callable metrics functions.

    Args:
        metric: Metric's name.
        variables: Variable names paired with their values. Used with custom metrics.

    Returns:
        Callable[[dict],dict]: Callable object that perform specified measurement.
    """
    match metric:
        case "time":
            return measure_time
        case "stdout":
            return gather_stdout
        case "stderr":
            return gather_stderr
        case _:
            metric_command = list(metric.items())[0][1]  # type: ignore
            metric_name = list(metric.items())[0][0]  # type: ignore
            if variables:
                metric_command = interpolate_command(metric_command, variables)
            return partial(custom_metric, metric_command, metric_name)


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
        for metric in run_config.metrics:
            benchmark = PreparedBenchmark(
                matrix={},
                before=run_config.before,
                benchmark=run_config.benchmark,
                after=run_config.after,
                metric=get_metric_function(metric),
            )
            benchmarks.append(benchmark)
    else:
        logger.debug("Creating variable combinations...")
        var_combinations = list(create_variable_combinations(**matrix))
        logger.debug(f"Variable combinations {var_combinations}")
        for var_combination in var_combinations:
            if exclude(var_combination, exclusions):
                continue
            for metric in run_config.metrics:
                before = interpolate_commands(run_config.before, var_combination)
                after = interpolate_commands(run_config.after, var_combination)
                bench = {}
                for name in run_config.benchmark:
                    bench[name] = interpolate_commands(
                        run_config.benchmark[name], var_combination
                    )
                benchmark = PreparedBenchmark(
                    matrix=var_combination,
                    before=before,
                    benchmark=bench,
                    after=after,
                    metric=get_metric_function(metric, var_combination),
                )
                benchmarks.append(benchmark)
    logger.info("Finished preparing benchmarks.")
    logger.debug(f"Prepared benchmarks: {benchmarks}")
    return benchmarks
