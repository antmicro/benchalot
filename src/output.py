from plotnine import ggplot, aes, geom_bar, facet_grid, theme_classic, labs
import pandas as pd


def output_results(results: list, config):

    results_column = "time"
    if "matrix" in config:
        results_df = pd.DataFrame(
            data=results,
            columns=([key for key in config["matrix"].keys()] + [results_column]),
        )
    else:
        results_df = pd.DataFrame(data=results, columns=[results_column])
    print(results_df.head())
    for key in config["output"]:
        output = config["output"][key]
        if output["format"] == "csv":
            results_df.to_csv(output["filename"], encoding="utf-8", index=False)
        elif output["format"] == "bar-chart":
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
            plot.save(output["filename"], width=width, height=height, dpi=dpi)
        elif output["format"] == "table-md":
            if "columns" in output:
                output_df = results_df.loc[:, output["columns"] + [results_column]]
                output_df = output_df.groupby(output["columns"]).mean().reset_index()
            else:
                output_df = results_df.loc[:, :]
            output_df[results_column] = output_df[results_column].apply(
                lambda x: f"{x:.4f}"
            )
            output_df.to_markdown(output["filename"], index=False)
