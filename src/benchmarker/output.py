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
from pandas.api.types import is_numeric_dtype, is_string_dtype
from uuid import uuid4

logger = getLogger(f"benchmarker.{__name__}")

TIME_STAMP_COLUMN = "benchmark_date"


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
    output_config: dict,
    matrix: dict[str, list],
    include: list,
) -> None:
    """Create output for the results. Optionally include old results.

    Args:
        results: Dictionary containing columns with results and variables' values.
        output_config: Configuration file's output section.
        matrix: Configuration file's matrix section.
    """
    try:
        results_df = pd.DataFrame(results)
    except ValueError as e:
        logger.critical(e)
    results_df.insert(
        0, TIME_STAMP_COLUMN, datetime.now(timezone.utc).strftime("%y/%m/%d %H:%M")
    )
    old_outputs = read_old_outputs(include)
    results_df = pd.concat([old_outputs, results_df], ignore_index=True)
    _output_results(results_df, output_config, matrix)


def output_results_from_file(
    output_config: dict, include: list, matrix: dict[str, list]
) -> None:
    """Create output for the old results.

    Args:
        output_config: Configuration file's output section.
        include: List of names of files to with old results.
        matrix: Configuration file's matrix section.
    """
    old_outputs = read_old_outputs(include)
    _output_results(old_outputs, output_config, matrix)


def get_stat_table(
    results_df: pd.DataFrame,
    result_column: str,
    show_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Create table with specified columns.
    Compute basic statistics if result column has numeric type.

    Args:
        results_df: Dataframe containing the results.
        result_column: Name of a metric which will be included in the table.
        show_columns: Variables' names which will be included in the table.
    """
    sub_result_columns = _get_substages(list(results_df.columns), result_column)
    if not show_columns:
        if results_df[TIME_STAMP_COLUMN].nunique() == 1:
            results_df = results_df.drop(TIME_STAMP_COLUMN, axis=1)
        if is_numeric_dtype(results_df[result_column]):
            output_columns = sub_result_columns + [result_column]
            result_stat = dict()
            for col in output_columns:
                col_name = col.removeprefix(result_column + ".")
                result_stat["min " + col_name] = [results_df[col].min()]
                result_stat["median " + col_name] = [results_df[col].min()]
                result_stat["max " + col_name] = [results_df[col].min()]
            table_df = pd.DataFrame(result_stat)
        else:
            table_df = results_df.drop_duplicates().reset_index(drop=True)
        return table_df
    else:
        if results_df[TIME_STAMP_COLUMN].nunique() == 1:
            results_df = results_df.drop(TIME_STAMP_COLUMN, axis=1)
        else:
            show_columns = [TIME_STAMP_COLUMN] + show_columns
        return _get_grouped_stat_table(results_df, result_column, show_columns)


def _get_grouped_stat_table(
    results_df: pd.DataFrame, result_column: str, show_columns: list[str]
) -> pd.DataFrame:
    """Helper function for the `get_stat_table` which performs column grouping."""
    statistics = ["min", "median", "max"]
    sub_result_columns = _get_substages(list(results_df.columns), result_column)
    table_df = results_df.loc[:, show_columns + sub_result_columns + [result_column]]
    math_df = table_df.groupby(show_columns, observed=False)
    for col in sub_result_columns + [result_column]:
        if is_numeric_dtype(table_df[result_column]):
            for stat in statistics:
                table_df[stat + " " + col.removeprefix(result_column + ".")] = math_df[
                    col
                ].transform(stat)
            table_df = table_df.drop(col, axis=1).reset_index(drop=True)
    table_df = table_df.drop_duplicates().reset_index(drop=True)
    return table_df


def _get_substages(columns: list[str], metric_name: str) -> list[str]:
    """Helper function which returns column names with stages for a given metric.

    Args:
        columns: List of column names.
        metric_name: Metric's name.

    Returns:
        list[str]: List of column names which contain results of the metric.
    """
    return [col for col in columns if col.startswith(metric_name + ".")]


def get_bar_chart(
    output_df: pd.DataFrame,
    variable_names: list[str],
    x_axis: str | None,
    y_axis: str,
    color: str | None,
    facet: str | None,
    stat: str,
) -> ggplot:
    """Get bar plot object with specified visual aspects

    Args:
        output_df: Dataframe containing benchmark results.
        variable_names: List of variable names.
        x_axis: Name of the variable used as x-axis of the plot.
        y_axis: Name of the variable used as y-axis of the plot.
        color: Name of the variable used as color channel of the plot.
        facet: Name of the variable used to facet the plot.

    Returns:
        ggplot: The bar chart object.
    """
    stack = _get_substages(list(output_df.columns), y_axis)
    if stack and color:
        logger.warning("'bar-chart': color setting is present, bars won't be stacked.")
    if stack and not color:
        output_df = output_df.drop(columns=[y_axis])
        output_df = output_df.melt(
            id_vars=list(variable_names),
            value_vars=stack,
            var_name="stage",
            value_name=y_axis,
        )
        # prevent rearranging by plotnine
        series = output_df["stage"]
        output_df["stage"] = pd.Categorical(series, categories=series.unique())

    plot = ggplot(output_df, aes(y=y_axis))
    if x_axis:
        plot += aes(x=x_axis)
    else:
        dummy_column = str(uuid4())
        output_df[dummy_column] = (
            0  # create dummy column since geom_bar always needs to have an x-axis
        )
        plot += aes(x=dummy_column)

    funcs = {"mean": np.mean, "median": np.median, "min": np.min, "max": np.max}
    if color:
        plot += aes(fill=f"factor({color})")
        plot += labs(fill=color)
    if stack and not color:
        plot += aes(fill="stage")
        plot += geom_bar(position="stack", stat="summary", fun_y=funcs[stat])
        plot += scale_fill_discrete(
            labels=[x.removeprefix(y_axis + ".") for x in stack]
        )
    else:
        plot += geom_bar(position="dodge", stat="summary", fun_y=funcs[stat])

    if facet:
        plot += facet_grid(cols=facet)
    plot += theme_classic()
    if not x_axis:
        plot += theme(
            axis_text_x=element_blank(),
            axis_title_x=element_blank(),
            axis_ticks_x=element_blank(),
        )
    return plot


def _output_results(
    results_df: pd.DataFrame, output_config: dict, matrix: dict[str, list]
) -> None:
    """Process output configuration and create output accordingly.

    Args:
        results_df: Dataframe containing benchmark results.
        output_config: Configuration file's output section.
        matrix: Configuration file's matrix section.

    """
    # Convert all string columns to categorical to prevent rearranging by plotnine
    for column in results_df.columns:
        if is_string_dtype(results_df[column]):
            series = results_df[column]
            results_df[column] = pd.Categorical(series, categories=series.unique())

    logger.info("Outputting results...")
    print_table = get_stat_table(
        results_df, results_df.columns[-1], list(matrix.keys())
    )
    if os.getuid() == 0:
        prev_umask = os.umask(0)
    for key in output_config:
        output = output_config[key]
        logger.debug(f"Creating output for {output}")
        output_df = results_df
        logger.debug(output_df.head())
        if output["format"] == "csv":
            logger.debug("Outputting .csv file.")
            output_df.to_csv(output["filename"], encoding="utf-8", index=False)
        elif output["format"] == "bar-chart":
            logger.debug("Outputting bar chart.")
            if not is_numeric_dtype(output_df[output["y-axis"]]):
                logger.error(
                    f"y-axis of output {key} has non-numeric type; bar-chart will not be generated"
                )
                continue
            plot = get_bar_chart(
                output_df=output_df,
                variable_names=list(matrix.keys()),
                x_axis=output["x-axis"],
                y_axis=output["y-axis"],
                color=output["color"],
                facet=output["facet"],
                stat=output["stat"],
            )
            plot.save(
                output["filename"],
                width=output["width"],
                height=output["height"],
                dpi=output["dpi"],
                limitsize=False,
                verbose=False,
            )

        elif output["format"] == "table-md":
            logger.debug("Outputting markdown table.")
            result_column = output["result-column"]
            table = get_stat_table(
                results_df,
                show_columns=output["columns"],
                result_column=result_column,
            )
            table.to_markdown(output["filename"], index=False)
            print_table = table
    if os.getuid() == 0:
        os.umask(prev_umask)
    print(print_table.to_markdown(index=False))
    logger.info("Finished outputting results.")
