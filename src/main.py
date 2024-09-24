import yaml
from itertools import product
from subprocess import run
from timeit import timeit

with open("config.yml", "r") as file:
    config = yaml.safe_load(file)


def product_dict(**kwargs):
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


def run_multiple_commands(commands: list) -> float:
    for c in commands:
        run(c, shell=True)


def prepare_command(command: str, var_combination) -> list:

    for var in var_combination:
        command = command.replace(f"$matrix.{var}", str(var_combination[var]))
    return command


var_combinations = list(product_dict(**config["matrix"]))
results = {}
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
    results[tuple(var_combination.items())] =  result

    for command in config["run"]["after"]:
        c = prepare_command(command, var_combination)
        print(f"Running {c}")
        run(c, shell=True, )
    print()
print(results)