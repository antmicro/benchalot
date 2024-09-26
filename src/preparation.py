from itertools import product


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


def prepare_benchmarks(config) -> list:

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
            benchmark["benchmark"] = prepare_commands(
                config["run"]["benchmark"], var_combination
            )
            if "after" in config["run"]:
                benchmark["after"] = prepare_commands(
                    config["run"]["after"], var_combination
                )
            benchmarks.append(benchmark)
    return benchmarks
