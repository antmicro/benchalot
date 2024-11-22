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
from sys import argv

logger = getLogger(f"benchmarker.{__name__}")

TIME_STAMP_COLUMN = "benchmark_date"
HAS_FAILED_COLUMN = "has_failed"
METRIC_COLUMN = "metric"
CONSTANT_COLUMNS = [TIME_STAMP_COLUMN, HAS_FAILED_COLUMN, METRIC_COLUMN]


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
    variable_names: list[str],
    include: list,
    include_failed: bool,
) -> None:
    """Create output for the results, optionally including old results.

    Args:
        results: Dictionary containing columns with results and values of the variables.
        output_config: Configuration file's output section.
        variable_names: List of variable names.
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
    _output_results(results_df, output_config, variable_names, include_failed)


def output_results_from_file(
    output_config: dict[str, BarChartOutput | CsvOutput | TableMdOutput],
    variable_names: list[str],
    include: list,
    include_failed: bool,
) -> None:
    """Create output for the results contained in files.

    Args:
        output_config: Configuration file's output section.
        variable_names: List of variable names.
        include: List of file names with old results.
        include_failed: Whether to filter out failed benchmarks.
    """
    old_outputs = read_old_outputs(include)
    _output_results(old_outputs, output_config, variable_names, include_failed)


def get_stat_table(
    input_df: pd.DataFrame,
    metric: str,
    measurement_columns: list[str],
    show_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Create summary table with specified columns.

    Args:
        results_df: Dataframe containing the results.
        result_column: A name of a metric which will be included in the table.
        measurement_columns: List of column names containing measurements.
        show_columns: Variable names which will be included in the table.
    """
    results_df = input_df.copy()
    is_numeric = True
    try:
        results_df[measurement_columns] = results_df[measurement_columns].apply(
            pd.to_numeric
        )
    except (ValueError, TypeError):
        is_numeric = False

    if len(measurement_columns) > 1:
        results_df["total"] = results_df[measurement_columns].sum(axis=1)
        measurement_columns.append("total")
    elif len(measurement_columns) == 1:
        results_df = results_df.rename(columns={measurement_columns[0]: metric})
        measurement_columns = [metric]
    else:
        raise ValueError("No measurement columns specified.")

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
            for col in measurement_columns:
                if col != metric:
                    col_name = col + " " + metric
                else:
                    col_name = col
                result_stat["min " + col_name] = [results_df[col].min()]
                result_stat["median " + col_name] = [results_df[col].median()]
                result_stat["max " + col_name] = [results_df[col].max()]
            table_df = pd.DataFrame(result_stat)
        else:
            table_df = results_df.drop_duplicates().reset_index(drop=True)
        return table_df
    else:
        table_df = results_df.loc[:, show_columns + measurement_columns]
        if is_numeric:
            grouped_df = table_df.groupby(show_columns, observed=True)[
                measurement_columns
            ].agg(["min", "median", "max"])
            new_column_names = []
            for old_col in grouped_df.columns:
                col_name = old_col[0]
                stat_name = old_col[1]
                if col_name != metric:
                    new_name = stat_name + " " + col_name + " " + metric
                else:
                    new_name = stat_name + " " + col_name
                new_column_names.append(new_name)
            grouped_df.columns = pd.Index(new_column_names)
            table_df = grouped_df.reset_index()
        table_df = table_df.drop_duplicates().reset_index(drop=True)
        return table_df


def get_bar_chart(
    input_df: pd.DataFrame,
    variable_names: list[str],
    measurement_columns: list[str],
    x_axis: str | None,
    y_axis: str,
    color: str | None,
    facet: str | None,
    stat: str,
) -> ggplot | None:
    """Create bar plot object.

    Args:
        output_df: Dataframe containing benchmark results.
        variable_names: List of variable names.
        measurement_columns: List of column names containing measurements.
        x_axis: Name of the variable used as x-axis of the plot.
        y_axis: Name of the variable used as y-axis of the plot.
        color: Name of the variable used as color channel of the plot.
        facet: Name of the variable used to facet the plot.

    Returns:
        ggplot: The bar chart object.
    """
    output_df = input_df.copy()
    try:
        output_df[measurement_columns] = output_df[measurement_columns].apply(
            pd.to_numeric
        )
    except (ValueError, TypeError):
        logger.error(
            f"y-axis ({y_axis}) of bar-chart has non-numeric type; bar-chart will not be generated"
        )
        return None

    stack = len(measurement_columns) > 1
    if stack and color:
        logger.warning("'bar-chart': color setting is present, bars won't be stacked.")

    dummy_y_axis = str(uuid4())
    if stack and not color:
        output_df = output_df.melt(
            id_vars=list(variable_names),
            value_vars=measurement_columns,
            var_name="stage",
            value_name=dummy_y_axis,
        )
        # prevent rearranging by plotnine
        series = output_df["stage"]
        output_df["stage"] = pd.Categorical(series, categories=series.unique())
    else:
        output_df[dummy_y_axis] = output_df[measurement_columns].sum(axis=1)

    plot = ggplot(output_df, aes(y=dummy_y_axis))
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
        plot += scale_fill_discrete(labels=measurement_columns)
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


def extract_measurement_columns(
    column_names: list[str], variable_names: list[str]
) -> list[str]:
    """Get measurement column names.

    Args:
        column_names: List of all column names.
        variable_names: List of variable names.

    Returns:
        list[str]: Measurement column names.
    """
    not_measurement_columns = set(variable_names + CONSTANT_COLUMNS)
    return [col for col in column_names if col not in not_measurement_columns]


def _output_results(
    results_df: pd.DataFrame,
    output_config: dict[str, CsvOutput | TableMdOutput | BarChartOutput],
    variable_names: list[str],
    include_failed: bool,
) -> None:
    """Create output based on results and configuration.

    Args:
        results_df: Dataframe containing benchmark results.
        output_config: Configuration file's output section.
        variable_names: List of variable names.
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
    n_failed = failed_benchmarks.shape[0]
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
        measurement_columns = extract_measurement_columns(
            list(filtered_df.columns), variable_names
        )
        if output.format == "bar-chart":
            logger.debug("Outputting bar chart.")
            plot = get_bar_chart(
                input_df=filtered_df,
                variable_names=variable_names,
                measurement_columns=measurement_columns,
                x_axis=output.x_axis,
                y_axis=output.metric,  # type: ignore
                color=output.color,
                facet=output.facet,
                stat=output.stat,
            )
            if not plot:
                continue
            plot.save(
                output.filename,
                width=output.width,
                height=output.height,
                dpi=output.dpi,
                limitsize=False,
                verbose=False,
            )

        elif output.format == "table-md":
            logger.debug("Outputting markdown table.")
            table = get_stat_table(
                filtered_df,
                measurement_columns=measurement_columns,
                show_columns=output.columns,
                metric=output.metric,  # type: ignore
            )
            table.to_markdown(output.filename, index=False)
            print_table = table

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
                measurement_cols = extract_measurement_columns(
                    list(table_df.columns), variable_names
                )
                print_table = get_stat_table(
                    table_df, metric, measurement_cols, variable_names
                )
                print(f"{metric}:")
                print(print_table.to_markdown(index=False))
        else:
            print(print_table.to_markdown(index=False))
    logger.info("Finished outputting results.")
