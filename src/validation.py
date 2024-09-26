from re import findall
from sys import stderr


def error(msg):
    print(f"ERROR: {msg}", file=stderr)
    exit(1)


def validate_config(config):

    if "run" not in config:
        error("`run` section not found in the config file.")
    if "benchmark" not in config["run"]:
        error("'run.benchmark' section not found in the config file.")
    if "matrix" in config:
        for section in ["before", "benchmark", "after"]:
            if section not in config["run"]:
                continue
            for command in config["run"][section]:
                variables = findall(r"\$matrix\.[a-zA-Z0-9]*", command)
                for var in variables:
                    var_key = var.split(".")[1]
                    if var_key not in config["matrix"]:
                        error(
                            f"Variable `{var}` in the command `{command}` not found in the `matrix` section."
                        )

    if "output" in config:

        def get_output_error_msg(section: str, key: str) -> str:
            return f"No `{section}` section in `output.{key}`"

        for key in config["output"]:
            output = config["output"][key]
            if "filename" not in output:
                error(get_output_error_msg("filename", key))
            if "format" not in output:
                error(get_output_error_msg("filename", key))
            if output["format"] == "bar-chart":
                if "matrix" not in config:
                    error("No `matrix` section.")
                if "x-axis" not in output:
                    error(get_output_error_msg("x-axis", key))
                for option in ["facet", "color", "x-axis"]:
                    if option not in config["output"][key]:
                        continue
                    if output[option] not in config["matrix"]:
                        error(
                            f"Variable `{output[option]}` in the `output.{key}.{option}` not found in the `matrix` section."
                        )
