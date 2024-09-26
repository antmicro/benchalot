from plotnine import ggplot, aes, geom_bar, facet_grid, theme_classic, labs
import pandas as pd


def output_results(results: list, config):

    if "matrix" in config:
        resultsDf = pd.DataFrame(
            results,
            columns=([key for key in config["matrix"].keys()] + ["measurement[s]"]),
        )
    print(resultsDf.head())
    if "output" in config:
        for key in config["output"]:
            output = config["output"][key]
            if output["format"] == "csv":
                resultsDf.to_csv(output["filename"], encoding="utf-8", index=False)
            elif output["format"] == "bar-chart":
                plot = (
                    ggplot(
                        resultsDf,
                        aes(
                            x=f"factor({output['x-axis']})",
                            y="measurement[s]",
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
                plot.save(output["filename"], width=10, height=9, dpi=100)
