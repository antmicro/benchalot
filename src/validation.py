# Cerberus does not provide stubs for mypy
from cerberus import Validator  # type: ignore
from re import findall
from sys import stderr
from pprint import pprint
from logging import getLogger


logger = getLogger("benchmarker_logger")


def error_and_exit(error):
    print("ERROR: config validation failed:", file=stderr)
    pprint(error, stream=stderr, indent=1, compact=False, width=120)
    exit(1)


def validate_config(config) -> dict:
    def variable_exists(field, value, error):
        if "matrix" not in config or value not in config["matrix"]:
            error(field, f"variable `{value}` does not exist")

    def variables_exist(field, value, error):
        for var in value:
            variable_exists(field, var, error)

    def check_command_variables(field, value, error):
        if "matrix" not in config:
            return
        # unfortunately cerberus does not stop checking on first validation error.
        if value is None:
            error(field, "no commands")
            return
        for command in value:
            variables = findall(r"\$matrix\.[a-zA-Z0-9]*", command)
            for var in variables:
                var_key = var.split(".")[1]
                variable_exists(field, var_key, error)

    valid_schema = {
        "log": {
            "required": False,
            "type": "dict",
            "empty": False,
            "schema": {
                "benchmarker": {
                    "required": False,
                    "type":"string",
                    "empty": False
                },
                "run": {
                    "required": False,
                    "type":"string"
                },
            }
        },
        "matrix": {
            "required": False,
            "type": "dict",
            "valuesrules": {"type": "list", "empty": False},
            "empty": False,
        },
        "options": {
            "required": False,
            "type": "dict",
            "schema": {
                "isolate-cpus": {
                    "type": "list",
                    "empty": False,
                    "required": False,
                },
                "disable-aslr": {
                    "type": "boolean",
                    "required": False,
                },
                "governor-performance": {"type": "boolean", "required": False},
            },
        },
        "run": {
            "required": True,
            "type": "dict",
            "schema": {
                "samples": {
                    "type": "integer",
                    "required": False,
                    "min": 1,
                    "default": 1,
                },
                "before": {
                    "required": False,
                    "type": "list",
                    "empty": False,
                    "minlength": 1,
                    "check_with": check_command_variables,
                },
                "benchmark": {
                    "required": True,
                    "type": "list",
                    "empty": False,
                    "minlength": 1,
                    "check_with": check_command_variables,
                },
                "after": {
                    "required": False,
                    "type": "list",
                    "empty": False,
                    "check_with": check_command_variables,
                },
            },
        },
        "output": {
            "required": True,
            "type": "dict",
            "valuesrules": {
                "oneof": [
                    {
                        "schema": {
                            "filename": {"type": "string", "empty": False},
                            "format": {"type": "string", "allowed": ["csv"]},
                        }
                    },
                    {
                        "schema": {
                            "filename": {"type": "string", "empty": False},
                            "format": {"type": "string", "allowed": ["table-md"]},
                            "columns": {
                                "type": "list",
                                "empty": False,
                                "required": False,
                                "dependencies": "^matrix",
                                "check_with": variables_exist,
                            },
                        },
                    },
                    {
                        "schema": {
                            "filename": {"type": "string", "empty": False},
                            "format": {"type": "string", "allowed": ["bar-chart"]},
                            "x-axis": {
                                "type": "string",
                                "empty": False,
                                "required": True,
                                "dependencies": "^matrix",
                                "check_with": variable_exists,
                            },
                            "color": {
                                "type": "string",
                                "empty": False,
                                "required": False,
                                "dependencies": "^matrix",
                                "check_with": variable_exists,
                            },
                            "facet": {
                                "type": "string",
                                "empty": False,
                                "required": False,
                                "dependencies": "^matrix",
                                "check_with": variable_exists,
                            },
                            "width": {
                                "type": "integer",
                                "min": 1,
                                "max": 25,
                                "required": False,
                            },
                            "height": {
                                "type": "integer",
                                "min": 1,
                                "max": 25,
                                "required": False,
                            },
                            "dpi": {"type": "integer", "min": 10, "required": False},
                        }
                    },
                ],
                "empty": False,
            },
        },
    }
    logger.info("Validating config...")
    logger.debug(f"Config: {config}")
    v = Validator(schema=valid_schema, require_all=True)
    if not v.validate(config):
        error_and_exit(v.errors)
    logger.info("Finished validating config.")
    normalized_config = v.normalized(config)
    logger.debug(f"Normalized config {normalized_config}")
    return normalized_config
