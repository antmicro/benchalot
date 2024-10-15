from plotnine import ggplot, aes, geom_bar, facet_grid, theme_classic, labs
import pandas as pd
from logging import getLogger
from datetime import timezone, datetime
from numpy import median
from sys import stderr

logger = getLogger(f"benchmarker.{__name__}")

RESULTS_COLUMN = "time"
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


def output_results_from_list(results: list, config, include: list):
    if "matrix" in config:
        logger.debug("Found `matrix` section, creating columns.")
        results_df = pd.DataFrame(
            data=results,
            columns=([key for key in config["matrix"].keys()] + [RESULTS_COLUMN]),
        )

    else:
        results_df = pd.DataFrame(data=results, columns=[RESULTS_COLUMN])
    results_df.insert(
        0, TIME_STAMP_COLUMN, datetime.now(timezone.utc).strftime("%y/%m/%d %H:%M")
    )
    old_outputs = read_old_outputs(include)
    results_df = pd.concat([old_outputs, results_df], ignore_index=True)
    output_results(results_df, config)


def output_results_from_file(config, include):
    old_outputs = read_old_outputs(include)
    output_results(old_outputs, config)

def get_printable_table(results_df: pd.DataFrame, columns = None):
    stats = ["mean", "median", "std", "min", "max"]
    if columns is not None:
        table_df = results_df.loc[:, columns + [RESULTS_COLUMN]]
        table_df = table_df.groupby(columns)
        table_df = (
            table_df[RESULTS_COLUMN]
            .agg(stats)
            .reset_index()
        )
    else:
        table_df = results_df.loc[:, :]
        table_df = table_df.groupby([col for col in results_df.columns if col != RESULTS_COLUMN])
        table_df = (
            results_df[RESULTS_COLUMN]
            .agg(stats)
            .reset_index()
        )
    return table_df

def output_results(results_df: pd.DataFrame, config: dict):
    logger.info("Outputting results...")
    print(get_printable_table(results_df).to_markdown())
    for key in config["output"]:
        output = config["output"][key]
        logger.debug(f"Creating output for {output}")
        output_df = results_df
        logger.debug(output_df.head())
        if output["format"] == "csv":
            logger.debug("Outputting .csv file.")
            output_df.to_csv(output["filename"], encoding="utf-8", index=False)
        elif output["format"] == "bar-chart":
            logger.debug("Outputting bar chart.")
            plot = (
                ggplot(
                    output_df,
                    aes(
                        x=f"factor({output['x-axis']})",
                        y=RESULTS_COLUMN,
                    ),
                )
                + geom_bar(position="dodge", stat="summary", fun_y=median)
                + theme_classic()
                + labs(x=output["x-axis"])
            )
            if "facet" in output:
                plot += facet_grid(cols=output["facet"])
            if "color" in output:
                plot += aes(fill=f"factor({output['color']})")
                plot += labs(fill=output["color"])
            width = 10
            height = 9
            dpi = 100
            if "width" in output:
                width = output["width"]
            if "height" in output:
                height = output["height"]
            if "dpi" in output:
                dpi = output["dpi"]
            plot.save(
                output["filename"],
                width=width,
                height=height,
                dpi=dpi,
                limitsize=False,
                verbose=False,
            )
        elif output["format"] == "table-md":
            logger.debug("Outputting markdown table.")
            if "columns" in output:
                get_printable_table(results_df,columns=output["columns"]).to_markdown(output["filename"], index=False)
            else:
                get_printable_table(results_df).to_markdown(output["filename"], index=False)
    logger.info("Finished outputting results.")
