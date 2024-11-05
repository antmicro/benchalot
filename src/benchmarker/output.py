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
    output_config: dict[str, BarChartOutput | CsvOutput | TableMdOutput],
    variable_names: list[str],
    measurement_columns: list[str],
    include: list,
) -> None:
    """Create output for the results, optionally including old results.

    Args:
        results: Dictionary containing columns with results and values of the variables.
        output_config: Configuration file's output section.
        matrix: Configuration file's matrix section.
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
    _output_results(results_df, output_config, variable_names, measurement_columns)


def output_results_from_file(
    output_config: dict[str, BarChartOutput | CsvOutput | TableMdOutput],
    include: list,
    variable_names: list[str],
    measurement_columns: list[str],
) -> None:
    """Create output for the results contained in files.

    Args:
        output_config: Configuration file's output section.
        include: List of file names with old results.
        matrix: Configuration file's matrix section.
    """
    old_outputs = read_old_outputs(include)
    _output_results(old_outputs, output_config, variable_names, measurement_columns)


def get_stat_table(
    input_df: pd.DataFrame,
    result_column: str,
    measurement_columns: list[str],
    show_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Create summary table with specified columns.

    Args:
        results_df: Dataframe containing the results.
        result_column: A name of a metric which will be included in the table.
        show_columns: Variable names which will be included in the table.
    """
    results_df = input_df.copy()
    results_df = results_df.loc[results_df["metric"] == result_column]
    is_numeric = True
    try:
        results_df[measurement_columns] = results_df[measurement_columns].apply(
            pd.to_numeric
        )
    except ValueError:
        is_numeric = False
    result_columns = measurement_columns.copy()
    if len(measurement_columns) > 1:
        results_df["total"] = results_df[measurement_columns].sum(axis=1)
        result_columns.append("total")
    group_table = len(show_columns) > 0
    if results_df[TIME_STAMP_COLUMN].nunique() == 1:
        results_df = results_df.drop(TIME_STAMP_COLUMN, axis=1)
    else:
        show_columns = [TIME_STAMP_COLUMN] + show_columns
    if not group_table:
        if is_numeric:
            result_stat = dict()
            for col in result_column:
                col_name = col + " " + result_column
                result_stat["min " + col_name] = [results_df[col].min()]
                result_stat["median " + col_name] = [results_df[col].min()]
                result_stat["max " + col_name] = [results_df[col].min()]
            table_df = pd.DataFrame(result_stat)
        else:
            table_df = results_df.drop_duplicates().reset_index(drop=True)
        return table_df
    else:
        statistics = ["min", "median", "max"]
        table_df = results_df.loc[:, show_columns + result_columns]
        math_df = table_df.groupby(show_columns, observed=False)
        for col in result_columns:
            if is_numeric:
                for stat in statistics:
                    col_name = col + " " + result_column
                    table_df[stat + " " + col_name] = math_df[col].transform(stat)
                table_df = table_df.drop(col, axis=1).reset_index(drop=True)
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
        x_axis: Name of the variable used as x-axis of the plot.
        y_axis: Name of the variable used as y-axis of the plot.
        color: Name of the variable used as color channel of the plot.
        facet: Name of the variable used to facet the plot.

    Returns:
        ggplot: The bar chart object.
    """
    output_df = input_df.copy()
    output_df = output_df.loc[output_df["metric"] == y_axis]
    try:
        output_df[measurement_columns] = output_df[measurement_columns].apply(
            pd.to_numeric
        )
    except ValueError:
        logger.error(
            f"y-axis ({y_axis}) of bar-chart has non-numeric type; bar-chart will not be generated"
        )
        return None
    stack = len(measurement_columns) > 1
    if stack and color:
        logger.warning("'bar-chart': color setting is present, bars won't be stacked.")

    if stack and not color:
        output_df = output_df.melt(
            id_vars=list(variable_names),
            value_vars=measurement_columns,
            var_name="stage",
            value_name="total",
        )
        # prevent rearranging by plotnine
        series = output_df["stage"]
        output_df["stage"] = pd.Categorical(series, categories=series.unique())
    else:
        output_df["total"] = output_df[measurement_columns].sum(axis=1)

    plot = ggplot(output_df, aes(y="total"))
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


def _output_results(
    results_df: pd.DataFrame,
    output_config: dict[str, CsvOutput | TableMdOutput | BarChartOutput],
    variable_names: list[str],
    measurement_columns: list[str],
) -> None:
    """Create output based on results and configuration.

    Args:
        results_df: Dataframe containing benchmark results.
        output_config: Configuration file's output section.
        matrix: Configuration file's matrix section.

    """
    # Convert all string columns to categorical to prevent rearranging by plotnine
    for column in variable_names:
        if is_string_dtype(results_df[column]):
            series = results_df[column]
            results_df[column] = pd.Categorical(series, categories=series.unique())

    logger.info("Outputting results...")
    logger.debug(results_df)
    first_metric = results_df["metric"][0]
    print_table = get_stat_table(
        results_df, first_metric, measurement_columns, variable_names
    )
    if os.getuid() == 0:
        prev_umask = os.umask(0)
    for key in output_config:
        output = output_config[key]
        logger.debug(f"Creating output for {output}")
        output_df = results_df
        logger.debug(output_df.head())
        if output.format == "csv":
            logger.debug("Outputting .csv file.")
            output_df.to_csv(output.filename, encoding="utf-8", index=False)
        elif output.format == "bar-chart":
            logger.debug("Outputting bar chart.")
            plot = get_bar_chart(
                input_df=output_df,
                variable_names=variable_names,
                measurement_columns=measurement_columns,
                x_axis=output.x_axis,
                y_axis=output.y_axis,
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
            result_column = output.result_column
            table = get_stat_table(
                results_df,
                measurement_columns=measurement_columns,
                show_columns=output.columns,
                result_column=result_column,
            )
            table.to_markdown(output.filename, index=False)
            print_table = table
    if os.getuid() == 0:
        os.umask(prev_umask)
    print(print_table.to_markdown(index=False))
    logger.info("Finished outputting results.")
