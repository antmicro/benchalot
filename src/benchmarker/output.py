import pandas as pd
from logging import getLogger
from datetime import timezone, datetime
import numpy as np
import os
from uuid import uuid4
from benchmarker.config import (
    TableMdOutput,
    TableHTMLOutput,
    BasePlotOutput,
    OutputFormat,
    OutputSection,
)
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
from collections.abc import Generator, Iterable
from typing import Literal
from copy import deepcopy
from plotnine import (
    ggplot,
    aes,
    geom_bar,
    geom_boxplot,
    facet_grid,
    theme_classic,
    labs,
    scale_fill_discrete,
    element_blank,
    theme,
    geom_point,
    geom_violin,
)
from benchmarker.log import console

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
    output_config: OutputSection,
    include: list,
    include_failed: bool,
    include_outliers: bool,
) -> None:
    """Create output for the results, optionally including old results.

    Args:
        results: Dictionary containing columns with results and values of the variables.
        output_config: Configuration file's output section.
        include: Lit of previous results file names to be combined with new results.
        include_failed: Whether to filter out failed benchmarks.
        include_outliers: Whether to filter out outliers.
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
    _output_results(results_df, output_config, include_failed, include_outliers)


def output_results_from_file(
    output_config: OutputSection,
    include: list,
    include_failed: bool,
    include_outliers: bool,
) -> None:
    """Create output for the results contained in files.

    Args:
        output_config: Configuration file's output section.
        include: List of file names with old results.
        include_failed: Whether to filter out failed benchmarks.
        include_outliers: Whether to filter out outliers.
    """
    old_outputs = read_old_outputs(include)
    _output_results(old_outputs, output_config, include_failed, include_outliers)


def get_stat_table(
    input_df: pd.DataFrame,
    stats: list[Literal["min", "median", "mean", "relative", "std", "max"]],
    show_columns: list[str] | None = [],
    pivot: str | None = None,
    metrics: list[str] | None = None,
) -> pd.DataFrame | None:
    """Create summary table with specified columns.

    Args:
        input_df: Dataframe containing the results.
        stats: What mathematical functions should be used to determine values in result columns.
        show_columns: Variable names which will be included in the table.
        pivot: String containing variable names determining names and contents of result columns.
        metrics: List of metrics to be included in the table.

    """
    results_df = input_df.copy()

    def valid(columns):
        for column in columns:
            if column not in results_df.columns:
                logger.error(
                    f"'{column}' is not a column (columns: [{', '.join(results_df.columns)}]).",
                )
                return False
        return True

    if show_columns is None:
        show_columns = [
            col for col in results_df.columns if col not in CONSTANT_COLUMNS
        ]
    else:
        show_columns = show_columns.copy()
        if not valid(show_columns):
            return None
    if pivot:
        if not valid(findall(VAR_REGEX, pivot)):
            return None
    if metrics:
        metrics_in_table = results_df[METRIC_COLUMN].unique()
        for m in metrics:
            if m not in metrics_in_table:
                logger.error(
                    f"'{m}' is not a metric (metrics: [{', '.join(metrics)}])."
                )
                return None

    if metrics:
        results_df = results_df[results_df[METRIC_COLUMN].isin(metrics)]
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
        n_in_group = grouped.size().max()
        stat_table = grouped.size().reset_index()[show_columns]
    else:
        grouped = results_df  # type: ignore
        n_in_group = 0
        for column in grouped.columns:
            group_len = len(grouped[column].dropna(axis=0, how="all"))  # type: ignore
            n_in_group = max(n_in_group, group_len)  # type: ignore
        stat_table = pd.DataFrame()

    displayable_stats: list[str] = list(stats)
    if n_in_group == 1 or n_in_group == 2:
        if n_in_group == 2:
            to_remove = ["median"]
        else:
            to_remove = ["min", "median", "mean", "max", "std"]
        for i in range(len(displayable_stats)):
            if displayable_stats[i] in to_remove:
                displayable_stats[i] = ""

    for col in result_columns:
        for stat in displayable_stats:
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
                    statistic_column = grouped[col].mean() / np.min(grouped[col].mean())
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
                case "":
                    statistic_column = grouped[col].mean()
            if show_columns:
                statistic_column = statistic_column.reset_index()[col]
            else:
                statistic_column = [statistic_column]  # type: ignore
            new_name = stat + " " + col
            stat_table[new_name] = statistic_column
    return stat_table


def output_md(results_df: pd.DataFrame, output: TableMdOutput, output_filename):
    logger.debug("Outputting markdown table.")
    table = get_stat_table(
        results_df,
        show_columns=output.columns,
        pivot=output.pivot,
        stats=output.stats,
        metrics=output.metrics,
    )
    if table is not None:
        table.to_markdown(output_filename, index=False)
        return True
    else:
        return False


def output_html(
    results_df: pd.DataFrame, output: TableHTMLOutput, output_filename
) -> bool:
    logger.debug("Outputting HTML table.")
    table = get_stat_table(
        results_df,
        show_columns=output.columns,
        pivot=output.pivot,
        stats=output.stats,
        metrics=output.metrics,
    )
    if table is not None:
        table.to_html(output_filename, index=False)
        return True
    else:
        return False


def output_plot(
    input_df: pd.DataFrame,
    output_filename: str,
    plot_config: BasePlotOutput,
) -> bool:
    """Output a plot.

    Args:
        output_df: Dataframe containing benchmark results.
        output_filename: Name of the output plot image.
        plot_config: Configuration regarding the plot.
    """

    def column_exists(option, df) -> bool:
        if option:
            if option not in df.columns:
                logger.error(
                    f"'{option}' is not a column (columns: [{', '.join(df.columns)}])."
                )
                return False
        return True

    def validate_columns(config: BasePlotOutput, df):
        plot_config = deepcopy(config)
        if not column_exists(plot_config.x_axis, df):
            return None
        if not column_exists(plot_config.color, df):
            return None
        if not column_exists(plot_config.facet, df):
            return None
        if plot_config.y_axis is None:
            if df[METRIC_COLUMN].nunique() > 1:
                logger.error("no metric specified.")
                return None
            else:
                plot_config.y_axis = df[METRIC_COLUMN].iloc[0]
        elif plot_config.y_axis not in df[METRIC_COLUMN].unique():
            logger.error(
                f"'{plot_config.y_axis}' is not a metric (metrics: [{', '.join(df[METRIC_COLUMN].unique())}])."
            )
            return None
        return plot_config

    valid_config = validate_columns(plot_config, input_df)
    if not valid_config:
        return False
    output_df = input_df.copy()
    output_df = output_df.loc[output_df[METRIC_COLUMN] == valid_config.y_axis]

    plot = ggplot(output_df, aes(y=RESULT_COLUMN))
    if valid_config.x_axis:
        plot += aes(x=valid_config.x_axis)
    else:
        dummy_column = str(uuid4())
        output_df[dummy_column] = 0
        plot += aes(x=dummy_column)

    if valid_config.color:
        plot += aes(fill=valid_config.color)
        plot += labs(fill=valid_config.color)
    match valid_config.format:
        case OutputFormat.BAR:
            funcs = {"mean": np.mean, "median": np.median, "min": np.min, "max": np.max}
            stack = output_df[STAGE_COLUMN].nunique() > 1
            if stack and valid_config.color:
                logger.warning(
                    "'bar-chart': color setting is present, bars won't be stacked."
                )
            if stack and not valid_config.color:
                plot += aes(fill="stage")
                plot += geom_bar(
                    position="stack", stat="summary", fun_y=funcs[valid_config.stat]
                )
                plot += scale_fill_discrete(
                    labels=list(output_df[STAGE_COLUMN].unique())
                )
            else:
                plot += geom_bar(
                    position="dodge", stat="summary", fun_y=funcs[valid_config.stat]
                )
        case OutputFormat.BOX:
            plot += geom_boxplot()
        case OutputFormat.SCATTER:
            plot += geom_point()
        case OutputFormat.VIOLIN:
            plot += geom_violin()

    if valid_config.facet:
        plot += facet_grid(cols=valid_config.facet)
    plot += labs(y=valid_config.y_axis)
    plot += theme_classic()
    if not valid_config.x_axis:
        plot += theme(
            axis_text_x=element_blank(),
            axis_title_x=element_blank(),
            axis_ticks_x=element_blank(),
        )
    plot.save(
        output_filename,
        width=valid_config.width,
        height=valid_config.height,
        dpi=valid_config.dpi,
        limitsize=False,
        verbose=False,
    )
    return True


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


CREATED_FILE_MSG = "Created '{filename}'"


def _output_results(
    results_df: pd.DataFrame,
    output_config: OutputSection,
    include_failed: bool,
    include_outliers: bool,
) -> None:
    """Create output based on results and configuration.

    Args:
        results_df: Dataframe containing benchmark results.
        output_config: Configuration file's output section.
        include_failed: Whether to filter out failed benchmarks.
        include_outliers: Whether to filter out outliers.
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
        if output.format == OutputFormat.CSV:
            logger.debug("Outputting .csv file.")
            variables_in_filename = findall(VAR_REGEX, output.filename)
            if not variables_in_filename:
                results_df.to_csv(output.filename, encoding="utf-8", index=False)
                csv_output_filenames.append(output.filename)
                console.print(CREATED_FILE_MSG.format(filename=output.filename))
            else:
                for comb, combination_df in get_combination_filtered_dfs(
                    results_df, variables_in_filename
                ):
                    overwrite_filename = interpolate_variables(output.filename, comb)
                    combination_df.to_csv(
                        overwrite_filename, encoding="utf-8", index=False
                    )
                    csv_output_filenames.append(overwrite_filename)
                    console.print(CREATED_FILE_MSG.format(filename=overwrite_filename))
        else:
            non_csv_outputs.append(output_name)

    def notify_about_csv(filenames: list[str]):
        logger.critical("Benchmarker crashed while creating output.")
        logger.warning(
            f"Benchmark results were saved in: {' '.join(filenames).strip()}"
        )

    register(notify_about_csv, csv_output_filenames)

    # Filter out failed output.
    if not include_failed:
        failed_benchmarks = results_df[
            results_df[HAS_FAILED_COLUMN] == True  # noqa: E712
        ]
        n_failed = failed_benchmarks[BENCHMARK_ID_COLUMN].nunique()
        if n_failed > 0:
            console.print(f"{n_failed} benchmarks failed!")
            logger.info("Failed benchmarks:\n" + failed_benchmarks.to_markdown())
            results_df = pd.DataFrame(
                results_df.loc[results_df[HAS_FAILED_COLUMN] == False]  # noqa: E712
            )
            if len(non_csv_outputs) > 0:
                console.print(
                    f"To generate output with failed benchmarks included run:\n\t{argv[0]} {argv[1]} -u {' '.join(csv_output_filenames).strip()} --include-failed"
                )
            if len(results_df.index) == 0:
                logger.critical("All benchmarks failed! Bailing out.")
                exit(1)

    # Filter out outliers
    if not include_outliers:
        # Remove outliers using modified Z-Score http://d-scholarship.pitt.edu/7948/1/Seo.pdf
        def detect_outliers(df):
            results = df.to_numpy(copy=True)
            if len(results) < 5:
                return np.full_like(results, False, np.bool)
            median = np.median(results)
            mad = np.median(np.abs(results - median))
            z_score = (0.6745 * (results - median)) / mad
            outliers = np.full_like(results, False, np.bool)
            outliers[np.where(np.abs(z_score) > 3.5)] = True
            return outliers

        grouped = results_df.groupby(
            [
                col
                for col in results_df.columns
                if col not in [RESULT_COLUMN, BENCHMARK_ID_COLUMN, HAS_FAILED_COLUMN]
            ],
            observed=True,
        )
        outlier_column_name = uuid4()
        results_df[outlier_column_name] = grouped[RESULT_COLUMN].transform(
            detect_outliers
        )
        outlier_benchmarks = results_df[
            results_df[outlier_column_name] == True  # noqa: E712
        ]
        n_outliers = len(outlier_benchmarks[BENCHMARK_ID_COLUMN].index)

        if n_outliers > 0:
            console.print(f"Detected {n_outliers} outliers.")
            results_df = pd.DataFrame(
                results_df.loc[results_df[outlier_column_name] == False]  # noqa: E712
            )
            logger.info(
                "Outliers:\n"
                + outlier_benchmarks.drop(outlier_column_name, axis=1).to_markdown()
            )
            if len(non_csv_outputs) > 0:
                console.print(
                    f"To generate output with outliers included run:\n\t{argv[0]} {argv[1]} -u {' '.join(csv_output_filenames).strip()} --include-outliers"
                )
        results_df = results_df.drop(outlier_column_name, axis=1)

    # Output non-csv file formats.
    for output_name in non_csv_outputs:
        output = output_config[output_name]
        logger.debug(f"Creating output for {output}")
        variables_in_filename = findall(VAR_REGEX, output.filename)
        multiplied_results: Iterable[tuple[dict, pd.DataFrame]]
        if not variables_in_filename:
            multiplied_results = [({}, results_df)]
        else:
            multiplied_results = get_combination_filtered_dfs(
                results_df, variables_in_filename
            )
        for comb, df in multiplied_results:
            overwrite_filename = interpolate_variables(output.filename, comb)
            success: bool
            match output.format:
                case OutputFormat.MD:
                    table_md_output: TableMdOutput = output  # type: ignore
                    success = output_md(df, table_md_output, overwrite_filename)
                case (
                    OutputFormat.BAR
                    | OutputFormat.BOX
                    | OutputFormat.SCATTER
                    | OutputFormat.VIOLIN
                ):
                    plot_output: BasePlotOutput = output  # type: ignore
                    success = output_plot(df, overwrite_filename, plot_output)
                case OutputFormat.HTML:
                    table_html_output: TableHTMLOutput = output  # type: ignore
                    success = output_html(df, table_html_output, overwrite_filename)
            if success:
                console.print(CREATED_FILE_MSG.format(filename=overwrite_filename))
            else:
                logger.error(f"Failed to create {overwrite_filename}.")

    if os.getuid() == 0:
        os.umask(prev_umask)
    unregister(notify_about_csv)
    term_size = (os.get_terminal_size().columns - len("SUMMARY")) // 2
    console.print()
    console.print(("─" * term_size) + "SUMMARY" + ("─" * term_size))
    for metric in results_df[METRIC_COLUMN].unique():
        table_df = results_df.loc[results_df[METRIC_COLUMN] == metric]
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
        if print_table is not None:
            console.print(print_table.to_markdown(index=False))
