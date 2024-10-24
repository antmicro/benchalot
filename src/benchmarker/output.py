from plotnine import ggplot, aes, geom_bar, facet_grid, theme_classic, labs
import pandas as pd
from logging import getLogger
from datetime import timezone, datetime
import numpy as np
import os
from pandas.api.types import is_numeric_dtype, is_string_dtype

logger = getLogger(f"benchmarker.{__name__}")

TIME_STAMP_COLUMN = "benchmark_date"


def read_old_outputs(include: list) -> pd.DataFrame:
    logger.debug(f"Include list for output: {include}")
    results_df = pd.DataFrame()
    for file in include:
        logger.debug(f"Reading file '{file}'")
        old_output = pd.read_csv(file)
        logger.debug(old_output.head())
        results_df = pd.concat([results_df, old_output], ignore_index=True)
    return results_df


def output_results_from_list(
    results: list,
    output_config: dict,
    matrix: dict[str, list],
    metrics: list,
    include: list,
):
    metrics_columns = [
        metric if type(metric) is not dict else list(metric.keys())[0]
        for metric in metrics
    ]
    results_df = pd.DataFrame(
        data=results,
        columns=([key for key in matrix] + metrics_columns),
    )

    results_df.insert(
        0, TIME_STAMP_COLUMN, datetime.now(timezone.utc).strftime("%y/%m/%d %H:%M")
    )
    old_outputs = read_old_outputs(include)
    results_df = pd.concat([old_outputs, results_df], ignore_index=True)
    output_results(results_df, output_config, matrix)


def output_results_from_file(
    output_config: dict, include: list, matrix: dict[str, list]
):
    old_outputs = read_old_outputs(include)
    output_results(old_outputs, output_config, matrix)


def get_stat_table(
    results_df: pd.DataFrame,
    result_column: str,
    show_columns: list[str] | None = None,
) -> pd.DataFrame:
    statistics = ["min", "median", "max"]
    if not show_columns:
        if results_df[TIME_STAMP_COLUMN].nunique() == 1:
            results_df = results_df.drop(TIME_STAMP_COLUMN, axis=1)
        if is_numeric_dtype(results_df[result_column]):
            table_df = pd.DataFrame(columns=statistics)
            table_df.loc[0] = [
                results_df[result_column].min(),
                results_df[result_column].median(),
                results_df[result_column].max(),
            ]
        else:
            table_df = results_df.drop_duplicates().reset_index(drop=True)
        return table_df
    else:
        if results_df[TIME_STAMP_COLUMN].nunique() == 1:
            results_df = results_df.drop(TIME_STAMP_COLUMN, axis=1)
        else:
            show_columns = [TIME_STAMP_COLUMN] + show_columns
        return get_grouped_stat_table(results_df, result_column, show_columns)


def get_grouped_stat_table(
    results_df: pd.DataFrame, result_column: str, show_columns: list[str]
) -> pd.DataFrame:
    statistics = ["min", "median", "max"]
    table_df = results_df.loc[:, show_columns + [result_column]]
    math_df = table_df.groupby(show_columns)
    if is_numeric_dtype(table_df[result_column]):
        for stat in statistics:
            table_df[stat] = math_df[result_column].transform(stat)
        table_df = table_df.drop(result_column, axis=1).reset_index(drop=True)
    table_df = table_df.drop_duplicates().reset_index(drop=True)
    return table_df


def output_results(
    results_df: pd.DataFrame, output_config: dict, matrix: dict[str, list]
):

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
            plot = (
                ggplot(
                    output_df,
                    aes(
                        x=f"factor({output['x-axis']})",
                        y=output["y-axis"],
                    ),
                )
                + geom_bar(position="dodge", stat="summary", fun_y=np.median)
                + theme_classic()
                + labs(x=output["x-axis"])
            )
            if output["facet"]:
                plot += facet_grid(cols=output["facet"])
            if output["color"]:
                plot += aes(fill=f"factor({output['color']})")
                plot += labs(fill=output["color"])
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
