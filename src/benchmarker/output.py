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
from uuid import uuid4
from benchmarker.validation import BarChartOutput, CsvOutput, TableMdOutput
from benchmarker.interpolation import (
    create_variable_combinations,
    VAR_REGEX,
    interpolate_variables,
)
from benchmarker.structs import (
    RESULT_COLUMN,
    TIME_STAMP_COLUMN,
    STAGE_COLUMN,
    HAS_FAILED_COLUMN,
    BENCHMARK_ID_COLUMN,
    METRIC_COLUMN,
)
from sys import argv
from re import findall
from atexit import register, unregister
from collections.abc import Generator

logger = getLogger(f"benchmarker.{__name__}")


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
        0, TIME_STAMP_COLUMN, datetime.now(timezone.utc).strftime("%y.%m.%d %H.%M")
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


def create_non_csv_output(
    filtered_df: pd.DataFrame,
    output: BarChartOutput | TableMdOutput,
    overwrite_filename: str | None = None,
):
    if filtered_df.shape[0] == 0:
        logger.error(f"No results to create output '{output}'.")
        return
    if not overwrite_filename:
        output_filename = output.filename
    else:
        output_filename = overwrite_filename
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
                    output_filename,
                    width=bar_chart_output.width,
                    height=bar_chart_output.height,
                    dpi=bar_chart_output.dpi,
                    limitsize=False,
                    verbose=False,
                )
            else:
                return
        case "table-md":
            logger.debug("Outputting markdown table.")
            table_md_output: TableMdOutput = output  # type: ignore
            table = get_stat_table(
                filtered_df,
                show_columns=table_md_output.columns,
                metric=table_md_output.metric,  # type: ignore
            )
            table.to_markdown(output_filename, index=False)
        case _:
            raise ValueError(f"Invalid output format: {output.format}.")
    print(f"Created '{output_filename}'")


def get_combination_filtered_dfs(
    df: pd.DataFrame, columns: list[str]
) -> Generator[tuple[dict, pd.DataFrame]]:
    """For each combination of values in given columns, return a filtered dataframe.

    Args:
        df: Data to be filtered.
        columns: Names of columns which will be used to create combinations.

    Returns:
        Generator[tuple[dict, pd.DataFrame]]: Generator of tuples, where each tuple contains dictionary containing combination and filtered data.
    """
    variables = {}
    for variable_name in columns:
        variables[variable_name] = df[variable_name].unique()
    combinations = create_variable_combinations(**variables)
    for comb in combinations:
        yield comb, df.loc[(df[list(comb.keys())] == pd.Series(comb)).all(axis=1)]


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

    logger.info("Outputting results...")
    logger.debug(results_df)

    # Convert all columns except result column to categorical to prevent rearranging by plotnine and help with grouping.
    for column in results_df.columns:
        if column != RESULT_COLUMN:
            series = results_df[column]
            results_df[column] = pd.Categorical(series, categories=series.unique())

    # If is root, set file permissions for other users
    if os.getuid() == 0:
        prev_umask = os.umask(0)

    # Output csv files first, in case that one of the more advanced outputs fails.
    non_csv_outputs = []
    csv_output_filenames = []
    for output_name, output in output_config.items():
        if output.format == "csv":
            logger.debug("Outputting .csv file.")
            variables_in_filename = findall(VAR_REGEX, output.filename)
            if not variables_in_filename:
                results_df.to_csv(output.filename, encoding="utf-8", index=False)
                csv_output_filenames.append(output.filename)
                print(f"Created '{output.filename}'")
            else:
                for comb, combination_df in get_combination_filtered_dfs(
                    results_df, variables_in_filename
                ):
                    overwrite_filename = interpolate_variables(output.filename, comb)
                    combination_df.to_csv(
                        overwrite_filename, encoding="utf-8", index=False
                    )
                    csv_output_filenames.append(overwrite_filename)
                    print(f"Created '{overwrite_filename}'")
        else:
            non_csv_outputs.append(output_name)

    def notify_about_csv(filenames: list[str]):
        logger.critical("Benchmarker crashed while creating output.")
        files_str = ""
        for file in filenames:
            files_str += "'" + file + "' "
        files_str = files_str.strip()
        logger.critical(f"Benchmark results were saved in {files_str}")

    register(notify_about_csv, csv_output_filenames)

    # Filter out failed output.
    without_failed_df: pd.DataFrame = results_df
    has_filtered_output: bool = False
    if not include_failed:
        failed_benchmarks = results_df[
            results_df[HAS_FAILED_COLUMN] == True  # noqa: E712
        ]
        n_failed = failed_benchmarks[BENCHMARK_ID_COLUMN].nunique()
        if n_failed > 0:
            has_filtered_output = True
            logger.error(f"{n_failed} benchmarks failed!")
            logger.warning("Failed benchmarks:\n" + failed_benchmarks.to_markdown())
            without_failed_df = pd.DataFrame(
                results_df.loc[results_df[HAS_FAILED_COLUMN] == False]  # noqa: E712
            )

    # Output non-csv file formats.
    for output_name in non_csv_outputs:
        output = output_config[output_name]
        logger.debug(f"Creating output for {output}")
        if has_filtered_output:
            logger.warning(f"Generating {output_name} without failed benchmarks...")
        single_metric_df = without_failed_df.loc[
            without_failed_df[METRIC_COLUMN] == output.metric
        ]
        single_metric_df = single_metric_df.dropna(axis=1, how="all")
        variables_in_filename = findall(VAR_REGEX, output.filename)
        if not variables_in_filename:
            create_non_csv_output(single_metric_df, output)  # type: ignore
        else:
            for comb, combination_df in get_combination_filtered_dfs(
                single_metric_df, variables_in_filename
            ):
                overwrite_filename = interpolate_variables(output.filename, comb)
                create_non_csv_output(combination_df, output, overwrite_filename)  # type: ignore

    if os.getuid() == 0:
        os.umask(prev_umask)
    unregister(notify_about_csv)
    # Warn user if Benchmarker created  output without failed benchmarks, otherwise print summary tables
    if has_filtered_output and len(non_csv_outputs) > 0:
        files_str = ""
        for file in csv_output_filenames:
            files_str += file + " "
        files_str = files_str.strip()
        logger.warning(
            f"To generate output with failed benchmarks included run:\n\t{argv[0]} {argv[1]} -u {files_str} --include-failed"
        )
    else:
        for metric in results_df[METRIC_COLUMN].unique():
            table_df = results_df.loc[results_df[METRIC_COLUMN] == metric]
            table_df = table_df.dropna(axis=1, how="all")
            excluded_columns = [
                HAS_FAILED_COLUMN,
                BENCHMARK_ID_COLUMN,
                METRIC_COLUMN,
                RESULT_COLUMN,
            ]
            if table_df[TIME_STAMP_COLUMN].nunique() == 1:
                excluded_columns += [TIME_STAMP_COLUMN]
            if table_df[STAGE_COLUMN].nunique() == 1:
                excluded_columns += [STAGE_COLUMN]
            print_table = get_stat_table(
                table_df,
                metric,
                [col for col in table_df.columns if col not in excluded_columns],
            )
            print()
            print(print_table.to_markdown(index=False))

    logger.info("Finished outputting results.")
