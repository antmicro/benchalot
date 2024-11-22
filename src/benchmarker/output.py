from plotnine import (
    ggplot,
    aes,
    geom_bar,
    facet_grid,
    theme_classic,
    labs,
    scale_fill_discrete,
    element_blank,
    theme,
)
import pandas as pd
from logging import getLogger
from datetime import timezone, datetime
import numpy as np
import os
from pandas.api.types import is_string_dtype
from uuid import uuid4
from benchmarker.validation import BarChartOutput, CsvOutput, TableMdOutput
from benchmarker.utils import (
    create_variable_combinations,
    VAR_REGEX,
    interpolate_variables,
)
from sys import argv
from re import findall

logger = getLogger(f"benchmarker.{__name__}")

TIME_STAMP_COLUMN = "benchmark_date"
BENCHMARK_ID_COLUMN = "benchmark_id"
HAS_FAILED_COLUMN = "has_failed"
METRIC_COLUMN = "metric"
STAGE_COLUMN = "stage"
RESULT_COLUMN = "result"
CONSTANT_COLUMNS = [
    BENCHMARK_ID_COLUMN,
    TIME_STAMP_COLUMN,
    HAS_FAILED_COLUMN,
    METRIC_COLUMN,
    STAGE_COLUMN,
    RESULT_COLUMN,
]


def read_old_outputs(include: list[str]) -> pd.DataFrame:
    """Parse files containing old results and concatenate them into a single dataframe.

    Args:
        include: List of names of files with old results.

    Returns:
        DataFrame: Containing concatenated old results.
    """
    logger.debug(f"Include list for output: {include}")
    results_df = pd.DataFrame()
    for file in include:
        logger.debug(f"Reading file '{file}'")
        old_output = pd.read_csv(file)
        logger.debug(old_output.head())
        results_df = pd.concat([results_df, old_output], ignore_index=True)
    return results_df


def output_results_from_dict(
    results: dict,
    output_config: dict[str, BarChartOutput | CsvOutput | TableMdOutput],
    include: list,
    include_failed: bool,
) -> None:
    """Create output for the results, optionally including old results.

    Args:
        results: Dictionary containing columns with results and values of the variables.
        output_config: Configuration file's output section.
        include: Lit of previous results file names to be combined with new results.
        include_failed: Whether to filter out failed benchmarks.
    """
    try:
        results_df = pd.DataFrame(results)
    except ValueError as e:
        logger.critical(e)
        exit(1)
    results_df.insert(
        0, TIME_STAMP_COLUMN, datetime.now(timezone.utc).strftime("%y/%m/%d %H:%M")
    )
    old_outputs = read_old_outputs(include)
    results_df = pd.concat([old_outputs, results_df], ignore_index=True)
    _output_results(results_df, output_config, include_failed)


def output_results_from_file(
    output_config: dict[str, BarChartOutput | CsvOutput | TableMdOutput],
    include: list,
    include_failed: bool,
) -> None:
    """Create output for the results contained in files.

    Args:
        output_config: Configuration file's output section.
        include: List of file names with old results.
        include_failed: Whether to filter out failed benchmarks.
    """
    old_outputs = read_old_outputs(include)
    _output_results(old_outputs, output_config, include_failed)


def get_stat_table(
    input_df: pd.DataFrame,
    metric: str,
    show_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Create summary table with specified columns.

    Args:
        results_df: Dataframe containing the results.
        result_column: A name of a metric which will be included in the table.
        show_columns: Variable names which will be included in the table.
    """
    results_df = input_df.copy()
    is_numeric = True
    try:
        results_df[RESULT_COLUMN] = results_df[RESULT_COLUMN].apply(pd.to_numeric)
    except (ValueError, TypeError):
        is_numeric = False

    if show_columns is None:
        show_columns = []

    group_table = len(show_columns) > 0

    if results_df[TIME_STAMP_COLUMN].nunique() == 1:
        results_df = results_df.drop(TIME_STAMP_COLUMN, axis=1)
    else:
        show_columns = [TIME_STAMP_COLUMN] + show_columns

    if not group_table:
        if is_numeric:
            result_stat = dict()
            result_stat["min " + metric] = [results_df[RESULT_COLUMN].min()]
            result_stat["median " + metric] = [results_df[RESULT_COLUMN].median()]
            result_stat["max " + metric] = [results_df[RESULT_COLUMN].max()]
            table_df = pd.DataFrame(result_stat)
        else:
            table_df = results_df.drop_duplicates().reset_index(drop=True)
        return table_df
    else:
        table_df = results_df.loc[:, show_columns + [RESULT_COLUMN]]
        if is_numeric:
            grouped_df = table_df.groupby(show_columns, observed=True)[
                RESULT_COLUMN
            ].agg(["min", "median", "max"])
            new_column_names = []
            for stat_name in grouped_df.columns:
                new_name = stat_name + " " + metric
                new_column_names.append(new_name)
            grouped_df.columns = pd.Index(new_column_names)
            table_df = grouped_df.reset_index()
        table_df = table_df.drop_duplicates().reset_index(drop=True)
        return table_df


def get_bar_chart(
    input_df: pd.DataFrame,
    x_axis: str | None,
    y_axis: str,
    color: str | None,
    facet: str | None,
    stat: str,
) -> ggplot | None:
    """Create bar plot object.

    Args:
        output_df: Dataframe containing benchmark results.
        x_axis: Name of the variable used as x-axis of the plot.
        y_axis: Name of the variable used as y-axis of the plot.
        color: Name of the variable used as color channel of the plot.
        facet: Name of the variable used to facet the plot.

    Returns:
        ggplot: The bar chart object.
    """
    output_df = input_df.copy()
    try:
        output_df[RESULT_COLUMN] = output_df[RESULT_COLUMN].apply(pd.to_numeric)
    except (ValueError, TypeError):
        logger.error(
            f"y-axis ({y_axis}) of bar-chart has non-numeric type; bar-chart will not be generated"
        )
        return None

    stack = output_df[STAGE_COLUMN].nunique() > 1
    if stack and color:
        logger.warning("'bar-chart': color setting is present, bars won't be stacked.")

    plot = ggplot(output_df, aes(y=RESULT_COLUMN))
    if x_axis:
        plot += aes(x=x_axis)
    else:
        # create dummy column since geom_bar always needs to have an x-axis
        dummy_column = str(uuid4())
        output_df[dummy_column] = 0
        plot += aes(x=dummy_column)

    funcs = {"mean": np.mean, "median": np.median, "min": np.min, "max": np.max}
    if color:
        plot += aes(fill=f"factor({color})")
        plot += labs(fill=color)
    if stack and not color:
        plot += aes(fill="stage")
        plot += geom_bar(position="stack", stat="summary", fun_y=funcs[stat])
        plot += scale_fill_discrete(labels=list(output_df[STAGE_COLUMN].unique()))
    else:
        plot += geom_bar(position="dodge", stat="summary", fun_y=funcs[stat])

    if facet:
        plot += facet_grid(cols=facet)
    plot += labs(y=y_axis)
    plot += theme_classic()
    if not x_axis:
        plot += theme(
            axis_text_x=element_blank(),
            axis_title_x=element_blank(),
            axis_ticks_x=element_blank(),
        )
    return plot


def create_fancy_output(
    filtered_df: pd.DataFrame,
    output: BarChartOutput | TableMdOutput,
    overwrite_filename: str | None = None,
):
    if not overwrite_filename:
        output_file_name = output.filename
    else:
        output_file_name = overwrite_filename
    match output.format:
        case "bar-chart":
            bar_chart_output: BarChartOutput = output  # type: ignore
            logger.debug("Outputting bar chart.")
            plot = get_bar_chart(
                input_df=filtered_df,
                x_axis=bar_chart_output.x_axis,
                y_axis=bar_chart_output.metric,
                color=bar_chart_output.color,
                facet=bar_chart_output.facet,
                stat=bar_chart_output.stat,
            )
            if plot:
                plot.save(
                    output_file_name,
                    width=bar_chart_output.width,
                    height=bar_chart_output.height,
                    dpi=bar_chart_output.dpi,
                    limitsize=False,
                    verbose=False,
                )
        case "table-md":
            logger.debug("Outputting markdown table.")
            table_md_output: TableMdOutput = output  # type: ignore
            table = get_stat_table(
                filtered_df,
                show_columns=table_md_output.columns,
                metric=table_md_output.metric,  # type: ignore
            )
            table.to_markdown(output_file_name, index=False)
        case _:
            raise ValueError(f"Invalid output format: {output.format}.")


def _output_results(
    results_df: pd.DataFrame,
    output_config: dict[str, CsvOutput | TableMdOutput | BarChartOutput],
    include_failed: bool,
) -> None:
    """Create output based on results and configuration.

    Args:
        results_df: Dataframe containing benchmark results.
        output_config: Configuration file's output section.
        include_failed: Whether to filter out failed benchmarks.
    """
    # Convert all variable columns to categorical to prevent rearranging by plotnine
    for column in results_df.columns:
        if is_string_dtype(results_df[column]):
            series = results_df[column]
            results_df[column] = pd.Categorical(series, categories=series.unique())

    logger.info("Outputting results...")
    logger.debug(results_df)

    # The summary table
    print_table: pd.DataFrame | None = None

    output_df: pd.DataFrame
    csv_output_filename = ""
    failed_benchmarks = results_df[results_df[HAS_FAILED_COLUMN] == True]  # noqa: E712
    n_failed = failed_benchmarks[BENCHMARK_ID_COLUMN].nunique()
    outputs_without_failed = []
    if n_failed > 0 and not include_failed:
        logger.error(f"{n_failed} benchmarks failed!")
        logger.warning("Failed benchmarks:\n" + failed_benchmarks.to_markdown())
        output_df = pd.DataFrame(
            results_df.loc[results_df[HAS_FAILED_COLUMN] == False]  # noqa: E712
        )
    else:
        output_df = results_df

    if os.getuid() == 0:
        prev_umask = os.umask(0)

    for output_name, output in output_config.items():
        logger.debug(f"Creating output for {output}")
        logger.debug(results_df.head())
        if output.format == "csv":
            logger.debug("Outputting .csv file.")
            results_df.to_csv(output.filename, encoding="utf-8", index=False)
            csv_output_filename = output.filename
            continue

        if n_failed > 0:
            outputs_without_failed.append(output_name)
        filtered_df = output_df.loc[output_df[METRIC_COLUMN] == output.metric]
        filtered_df = filtered_df = filtered_df.dropna(axis=1, how="all")
        variable_names = findall(VAR_REGEX, output.filename)
        variables = {}
        for variable_name in variable_names:
            print(variable_name)
            variables[variable_name] = filtered_df[variable_name].unique()
        if len(variables) > 0:
            combinations = create_variable_combinations(**variables)
            for comb in combinations:
                combination_df = filtered_df.loc[
                    (filtered_df[list(comb.keys())] == pd.Series(comb)).all(axis=1)
                ]
                overwrite_filename = interpolate_variables(output.filename, comb)
                create_fancy_output(combination_df, output, overwrite_filename)
        else:
            create_fancy_output(filtered_df, output)

    if os.getuid() == 0:
        os.umask(prev_umask)
    if len(outputs_without_failed) >= 1 and not include_failed:
        logger.warning(
            f"Outputs generated without failed benchmarks: {', '.join(outputs_without_failed)}"
        )
        logger.warning(
            f"To generate output with failed benchmarks included run:\n\t{argv[0]} {argv[1]} -u {csv_output_filename} --include-failed"
        )
    else:
        if print_table is None:
            for metric in output_df[METRIC_COLUMN].unique():
                table_df = output_df.loc[output_df[METRIC_COLUMN] == metric]
                table_df = table_df.dropna(axis=1, how="all")
                print_table = get_stat_table(
                    table_df,
                    metric,
                    [col for col in table_df.columns if col not in CONSTANT_COLUMNS],
                )
                print(f"{metric}:")
                print(print_table.to_markdown(index=False))
        else:
            print(print_table.to_markdown(index=False))
    logger.info("Finished outputting results.")
