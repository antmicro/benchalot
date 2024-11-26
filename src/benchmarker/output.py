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
from benchmarker.config import BarChartOutput, CsvOutput, TableMdOutput
from benchmarker.interpolate import (
    create_variable_combinations,
    VAR_REGEX,
    interpolate_variables,
)
from benchmarker.output_constants import (
    RESULT_COLUMN,
    TIME_STAMP_COLUMN,
    STAGE_COLUMN,
    HAS_FAILED_COLUMN,
    BENCHMARK_ID_COLUMN,
    METRIC_COLUMN,
    CONSTANT_COLUMNS,
)
from sys import argv
from re import findall, sub
from atexit import register, unregister
from collections.abc import Generator, Iterable, Sequence
from typing import Literal

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
        old_output[CONSTANT_COLUMNS] = old_output[CONSTANT_COLUMNS].fillna("")
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
    stats: Sequence[Literal["max", "min", "median", "mean", "relative", "std"]],
    show_columns: list[str] | None = None,
    pivot: str | None = None,
    metrics: list[str] | None = None,
) -> pd.DataFrame:
    """Create summary table with specified columns.

    Args:
        input_df: Dataframe containing the results.
        stats: What mathematical functions should be used to determine values in result columns.
        show_columns: Variable names which will be included in the table.
        pivot: String containing variable names determining names and contents of result columns.
        metrics: List of metrics to be included in the table.

    """
    results_df = input_df.copy()
    if metrics:
        results_df = results_df[results_df[METRIC_COLUMN].isin(metrics)]
    is_numeric = True
    try:
        results_df[RESULT_COLUMN] = results_df[RESULT_COLUMN].apply(pd.to_numeric)
    except (ValueError, TypeError):
        is_numeric = False

    if show_columns is None:
        show_columns = []
    if pivot:
        pivot_columns = findall(VAR_REGEX, pivot)
    else:
        pivot_columns = []
    show_columns = [col for col in show_columns if col not in pivot_columns]

    result_columns = []
    if pivot_columns:
        results_df = results_df.pivot(
            index=[
                col
                for col in results_df.columns
                if col not in pivot_columns + [RESULT_COLUMN]
            ],
            columns=pivot_columns,
            values=[RESULT_COLUMN],
        )
        for old_name in results_df.columns:
            comb = {}
            for variable_name, value in zip(pivot_columns, old_name[1:]):
                comb[variable_name] = value
            new_name = interpolate_variables(pivot, comb)  # type: ignore
            new_name = sub(r"\s+", " ", new_name.strip())
            result_columns.append(new_name)
        results_df.columns = pd.Index(result_columns)
        results_df = results_df.reset_index()
    else:
        result_columns = [RESULT_COLUMN]

    results_df = results_df.loc[:, show_columns + result_columns]

    if show_columns:
        grouped = results_df.groupby(show_columns, observed=True)
        stat_table = grouped.size().reset_index()[show_columns]
    else:
        grouped = results_df  # type: ignore
        stat_table = pd.DataFrame()
    if is_numeric:
        for col in result_columns:
            for stat in stats:
                match stat:
                    case "min":
                        statistic_column = grouped[col].min()
                    case "max":
                        statistic_column = grouped[col].max()
                    case "median":
                        statistic_column = grouped[col].median()
                    case "mean":
                        if "std" in stats:
                            continue
                        statistic_column = grouped[col].mean()
                    case "relative":
                        statistic_column = grouped[col].mean() / np.min(
                            grouped[col].mean()
                        )
                    case "std":
                        if "mean" in stats:
                            mean = pd.Series(grouped[col].mean())
                            std = pd.Series(grouped[col].std())
                            mean_std = []
                            for m, s in zip(mean, std):
                                row = f"{m:.3f} ± {s:.3f}"
                                mean_std.append(row)

                            if show_columns:
                                statistic_column = pd.Series(mean_std, name=col)
                            else:
                                statistic_column = mean_std[0]  # type: ignore
                            stat = "mean"
                        else:
                            statistic_column = grouped[col].std()
                if show_columns:
                    statistic_column = statistic_column.reset_index()[col]
                else:
                    statistic_column = [statistic_column]  # type: ignore
                new_name = stat + " " + col
                stat_table[new_name] = statistic_column
    else:
        stat_table = results_df.drop_duplicates().reset_index(drop=True)
    return stat_table


def output_md(single_metric_df: pd.DataFrame, output: TableMdOutput, output_filename):
    logger.debug("Outputting markdown table.")
    table = get_stat_table(
        single_metric_df,
        show_columns=output.columns,
        pivot=output.pivot,
        stats=output.stats,
        metrics=output.metrics,
    )
    print(table.to_markdown(index=False))
    table.to_markdown(output_filename, index=False)


def output_bar_chart(
    input_df: pd.DataFrame,
    output_filename: str,
    x_axis: str | None,
    y_axis: str,
    color: str | None,
    facet: str | None,
    stat: str,
    width: int,
    height: int,
    dpi: int,
) -> None:
    """Output bar plot.

    Args:
        output_df: Dataframe containing benchmark results.
        output_filename: Name of the output plot image.
        x_axis: Name of the variable used as x-axis of the plot.
        y_axis: Name of the variable used as y-axis of the plot.
        color: Name of the variable used as color channel of the plot.
        facet: Name of the variable used to facet the plot.
        stat: Name of the statistic which will be used to determine bar heights.
        width: Output image width (in inches).
        height: Output image height (in inches).
        dpi: Output image dpi.
    """
    output_df = input_df.copy()
    output_df = output_df.loc[output_df[METRIC_COLUMN] == y_axis]
    output_df = output_df.dropna(axis=1, how="all")
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
    plot.save(
        output_filename,
        width=width,
        height=height,
        dpi=dpi,
        limitsize=False,
        verbose=False,
    )


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
    if len(results_df) == 0:
        logger.critical("No results available! Bailing out.")
        exit(1)

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
        logger.warning(
            f"Benchmark results were saved in: {' '.join(filenames).strip()}"
        )

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
            if len(without_failed_df.index) == 0:
                logger.critical("All benchmarks failed! Bailing out.")
                logger.warning(
                    f"To generate output with failed benchmarks included run:\n\t{argv[0]} {argv[1]} -u {' '.join(csv_output_filenames).strip()} --include-failed"
                )
                exit(1)

    # Output non-csv file formats.
    for output_name in non_csv_outputs:
        output = output_config[output_name]
        logger.debug(f"Creating output for {output}")
        if has_filtered_output:
            logger.warning(f"Generating {output_name} without failed benchmarks...")
        variables_in_filename = findall(VAR_REGEX, output.filename)
        multiplied_results: Iterable[tuple[dict, pd.DataFrame]]
        if not variables_in_filename:
            multiplied_results = [({}, without_failed_df)]
        else:
            multiplied_results = get_combination_filtered_dfs(
                without_failed_df, variables_in_filename
            )
        match output.format:
            case "table-md":
                for comb, df in multiplied_results:
                    table_md_output: TableMdOutput = output  # type: ignore
                    overwrite_filename = interpolate_variables(output.filename, comb)
                    output_md(df, table_md_output, overwrite_filename)
                    print(f"Created '{overwrite_filename}'")
            case "bar-chart":
                for comb, df in multiplied_results:
                    bar_chart_output: BarChartOutput = output  # type: ignore
                    overwrite_filename = interpolate_variables(output.filename, comb)
                    output_bar_chart(
                        df,
                        overwrite_filename,
                        bar_chart_output.x_axis,
                        bar_chart_output.metric,  # type: ignore
                        bar_chart_output.color,
                        bar_chart_output.facet,
                        bar_chart_output.stat,
                        bar_chart_output.width,
                        bar_chart_output.height,
                        bar_chart_output.dpi,
                    )
                    print(f"Created '{overwrite_filename}'")

    if os.getuid() == 0:
        os.umask(prev_umask)
    unregister(notify_about_csv)
    # Warn user if Benchmarker created  output without failed benchmarks, otherwise print summary tables
    if has_filtered_output and len(non_csv_outputs) > 0:
        logger.warning(
            f"To generate output with failed benchmarks included run:\n\t{argv[0]} {argv[1]} -u {' '.join(csv_output_filenames).strip()} --include-failed"
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
                ["min", "median", "max"],
                [col for col in table_df.columns if col not in excluded_columns],
                "{{" + STAGE_COLUMN + "}} {{" + METRIC_COLUMN + "}}",
            )
            print()
            print(print_table.to_markdown(index=False))

    logger.info("Finished outputting results.")
