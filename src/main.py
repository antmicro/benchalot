import yaml
import pandas as pd
from itertools import product
from subprocess import run
from timeit import timeit
from sys import stderr


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
    return timeit(lambda: run_multiple_commands(commands), number=1)


# load configuration file
try:
    config_file = open("config.yml", "r")
except FileNotFoundError:
    print("'config.yml' not found.", file=stderr)
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

resultsDf = pd.DataFrame(results)
print(resultsDf.head())

if "output" in config and "name" in config["output"]:
    resultsDf.to_csv(config["output"]["name"], encoding="utf-8", index=False)
