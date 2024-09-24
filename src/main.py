import yaml
from itertools import product
from subprocess import run
from timeit import timeit
import pandas as pd

with open("config.yml", "r") as file:
    config = yaml.safe_load(file)


def product_dict(**kwargs):
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


def run_multiple_commands(commands: list):
    for c in commands:
        run(c, shell=True)


def prepare_command(command: str, var_combination) -> str:

    for var in var_combination:
        command = command.replace(f"$matrix.{var}", str(var_combination[var]))
    return command


var_combinations = list(product_dict(**config["matrix"]))
results = pd.DataFrame(
    columns=[key for key in config["matrix"].keys()] + ["measurement[s]"]
)
print(results)
for var_combination in var_combinations:
    print(f"Exectuting with variables set to: {var_combination}.")
    for command in config["run"]["before"]:
        c = prepare_command(command, var_combination)
        print(f"Running {c}")
        run(c, shell=True)

    benchmarked_commands = []
    for command in config["run"]["benchmark"]:
        c = prepare_command(command, var_combination)
        print(f"Queueing: {c}")
        benchmarked_commands.append(c)
    result = timeit(lambda: run_multiple_commands(benchmarked_commands), number=1)
    results.loc[len(results.index)] = [
        var_combination[key] for key in var_combination
    ] + [result]
    for command in config["run"]["after"]:
        c = prepare_command(command, var_combination)
        print(f"Running {c}")
        run(
            c,
            shell=True,
        )
    print()

print(results.head())

results.to_csv(config["output"]["name"], encoding="utf-8", index=False)
