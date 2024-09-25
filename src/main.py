import yaml
import pandas as pd
from itertools import product
from subprocess import run
from time import monotonic_ns
from sys import stderr, argv
from plotnine import ggplot, aes, geom_bar, facet_grid, theme_classic, labs


def create_variable_combinations(**kwargs):
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


def prepare_commands(commands: list, var_combination) -> list:
    def prepare_command(command: str, var_combination) -> str:
        for var in var_combination:
            command = command.replace(f"$matrix.{var}", str(var_combination[var]))
        return command

    prepared_commands = []
    for command in commands:
        prepared_commands.append(prepare_command(command, var_combination))
    return prepared_commands


def run_multiple_commands(commands: list):
    for c in commands:
        run(c, shell=True)


def benchmark_commands(commands: list) -> float:
    start = monotonic_ns()
    run_multiple_commands(commands)
    return (monotonic_ns() - start) / 1e9  # convert to seconds


# load configuration file
if len(argv) < 2:
    print("ERROR: Please pass config filename as an argument.", file=stderr)
    exit(1)
try:
    config_file = open(argv[1], "r")
except FileNotFoundError:
    print(f"ERROR:'{argv[1]}' not found.", file=stderr)
    exit(1)
else:
    with config_file:
        config = yaml.safe_load(config_file)

# process commands, i.e. replace variable names with values.
if "run" not in config:
    print("ERROR: `run` section not found the config file.", file=stderr)
    exit(1)

benchmarks = []
if "matrix" not in config:
    benchmarks.append(config["run"])
    benchmarks[0]["matrix"] = {}
else:
    var_combinations = list(create_variable_combinations(**config["matrix"]))
    for var_combination in var_combinations:
        benchmark = {"matrix": var_combination}
        if "before" in config["run"]:
            benchmark["before"] = prepare_commands(
                config["run"]["before"], var_combination
            )
        if "benchmark" in config["run"]:
            benchmark["benchmark"] = prepare_commands(
                config["run"]["benchmark"], var_combination
            )
        if "after" in config["run"]:
            benchmark["after"] = prepare_commands(
                config["run"]["after"], var_combination
            )
        benchmarks.append(benchmark)

# perform benchmarks
results = []
for benchmark in benchmarks:
    if "before" in benchmark:
        run_multiple_commands(benchmark["before"])
    if "benchmark" in benchmark:
        result = benchmark_commands(benchmark["benchmark"])
    else:
        print("ERROR: No 'benchmark' section in the config file.", file=stderr)
        exit(1)
    if "after" in benchmark:
        run_multiple_commands(benchmark["after"])
    results.append([benchmark["matrix"][key] for key in benchmark["matrix"]] + [result])

# get output
resultsDf = pd.DataFrame(
    results,
    columns=[key for key in benchmarks[0]["matrix"].keys()] + ["measurement[s]"],
)
print(resultsDf.head())
if "output" in config:
    for key in config["output"]:
        output = config["output"][key]
        if "filename" not in output:
            print(f"Warning: Output: {key} lacks `filename` section. Omitting...")
            continue
        if "format" not in output:
            print(f"Warning: Output: {key} lacks `format` section. Omitting...")
            continue
        if output["format"] == "csv":
            resultsDf.to_csv(output["filename"], encoding="utf-8", index=False)
        elif output["format"] == "bar-chart":
            plot = (
                ggplot(
                    resultsDf,
                    aes(
                        x=f"factor({output['x-axis']})",
                        y="measurement[s]",
                        fill=output["color"],
                    ),
                )
                + geom_bar(position="dodge", stat="identity")
                + facet_grid(cols=output["facet"])
                + theme_classic()
                + labs(x=output["x-axis"], fill=output["color"])
            )
            plot.save(output["filename"], width=10, height=9, dpi=100)
