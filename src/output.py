from plotnine import ggplot, aes, geom_bar, facet_grid, theme_classic, labs
import pandas as pd
from logging import getLogger


logger = getLogger("benchmarker_logger")


def output_results(results: list, config):

    logger.info("Outputting results...")
    results_column = "time"
    if "matrix" in config:
        logger.debug("Found `matrix` section, creating columns.")
        results_df = pd.DataFrame(
            data=results,
            columns=([key for key in config["matrix"].keys()] + [results_column]),
        )
    else:
        logger.debug("`matrix` section not found")
        results_df = pd.DataFrame(data=results, columns=[results_column])
    print(results_df.head())
    for key in config["output"]:
        output = config["output"][key]
        logger.debug(f"Creating output for {output}")
        if output["format"] == "csv":
            logger.debug("Outputting .csv file.")
            results_df.to_csv(output["filename"], encoding="utf-8", index=False)
        elif output["format"] == "bar-chart":
            logger.debug("Outputting bar chart.")
            plot = (
                ggplot(
                    results_df,
                    aes(
                        x=f"factor({output['x-axis']})",
                        y=results_column,
                    ),
                )
                + geom_bar(position="dodge", stat="identity")
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
            plot.save(output["filename"], width=width, height=height, dpi=dpi, limitsize=False)
        elif output["format"] == "table-md":
            logger.debug("Outputting markdown table.")
            if "columns" in output:
                output_df = results_df.loc[:, output["columns"] + [results_column]]
                output_df = output_df.groupby(output["columns"])
                output_df = (
                    output_df[results_column]
                    .agg(["mean", "median", "std"])
                    .reset_index()
                )
            else:
                output_df = results_df.loc[:, :]
                if "matrix" in config:
                    output_df = output_df.groupby([var for var in config["matrix"]])
                    output_df = (
                        output_df[results_column]
                        .agg(["mean", "median", "std"])
                        .reset_index()
                    )
            output_df.to_markdown(output["filename"], index=False)
    logger.info("Finished outputting results.")
