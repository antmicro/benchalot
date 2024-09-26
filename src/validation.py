from re import findall
from sys import stderr


def error(msg):
    print(f"ERROR: {msg}", file=stderr)
    exit(1)


def validate_config(config):

    if "run" not in config:
        error("`run` section not found.")
    if "benchmark" not in config["run"]:
        error("'run.benchmark' section not found.")
    for section in ["before", "benchmark", "after"]:
        if section not in config["run"]:
            continue
        for command in config["run"][section]:
            variables = findall(r"\$matrix\.[a-zA-Z0-9]*", command)
            for var in variables:
                var_key = var.split(".")[1]
                if "matrix" not in config or var_key not in config["matrix"]:
                    error(
                        f"Variable `{var}` in the command `{command}` not found in the `matrix` section."
                    )

    if "output" not in config or config["output"] is None:
        error("`output` section not found.")

    for key in config["output"]:
        output = config["output"][key]
        if "filename" not in output:
            error(f"`filename` section not found in `output.{key}`.")
        if "format" not in output:
            error(f"`format` section not found in `output.{key}`.")
        if output["format"] == "bar-chart":
            if "matrix" not in config:
                error("`matrix` section not found.")
            if "x-axis" not in output:
                error(f"`x-axis` section not found in `output.{key}`.")
            for option in ["facet", "color", "x-axis"]:
                if option not in config["output"][key]:
                    continue
                if output[option] not in config["matrix"]:
                    error(
                        f"Variable `{output[option]}` in the `output.{key}.{option}` not found in the `matrix` section."
                    )
        elif output["format"] == "table-md":
            if "columns" in output:
                for var in output['columns']:
                    if var not in config["matrix"]:
                        error(
                            f"Variable `{var}` in the `output.{key}.columns` not found in the `matrix` section."
                        )

