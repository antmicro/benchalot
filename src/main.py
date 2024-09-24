import yaml
from itertools import product
from subprocess import run

with open("config.yml", "r") as file:
    config = yaml.safe_load(file)


def product_dict(**kwargs):
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


var_combinations = list(product_dict(**config["matrix"]))


def prepare_command(command: str, var_combination) -> list:
    for var in var_combination:
        command = command.replace(f"$matrix.{var}", str(var_combination[var]))
    subcommands = command.split(" ")
    return subcommands


for var_combination in var_combinations:
    print(f"Exectuting with variables set to: {var_combination}.")
    for command in config["run"]["before"]:
        c = prepare_command(command, var_combination)
        print(f"Running {' '.join(c)}")
        run(c, shell=True)
    for command in config["run"]["benchmark"]:
        c = prepare_command(command, var_combination)
        print(f"Running {' '.join(c)}")
        run(c, shell=True)
    for command in config["run"]["after"]:
        c = prepare_command(command, var_combination)
        print(f"Running {' '.join(c)}")
        run(c, shell=True)
    print()
