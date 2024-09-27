# Cerberus does not provide stubs for mypy
from cerberus import Validator  # type: ignore
from re import findall
from sys import stderr
from pprint import pprint


def error_and_exit(error):
    print("ERROR: config validation failed:", file=stderr)
    pprint(error, stream=stderr, indent=1, compact=False, width=120)
    exit(1)


def validate_config(config):
    def variable_exists(field, value, error):
        if value not in config["matrix"]:
            error(field, f"variable `{value}` does not exist")

    def variables_exist(field, value, error):
        for var in value:
            variable_exists(field, var, error)

    def check_command_variables(field, value, error):
        if "matrix" not in config:
            error(field, "`matrix` section does not exist")
            return
        for command in value:
            variables = findall(r"\$matrix\.[a-zA-Z0-9]*", command)
            for var in variables:
                var_key = var.split(".")[1]
                variable_exists(field, var_key, error)

    valid_schema = {
        "matrix": {
            "required": False,
            "type": "dict",
            "valuesrules": {"type": "list", "empty": False},
            "empty": False,
        },
        "run": {
            "required": True,
            "type": "dict",
            "schema": {
                "before": {
                    "allof": [
                        {
                            "required": False,
                            "type": "list",
                            "empty": False,
                        },
                        {
                            "check_with": check_command_variables,
                        },
                    ]
                },
                "benchmark": {
                    "allof": [
                        {
                            "required": True,
                            "type": "list",
                            "empty": False,
                        },
                        {
                            "check_with": check_command_variables,
                        },
                    ]
                },
                "after": {
                    "allof": [
                        {
                            "required": False,
                            "type": "list",
                            "empty": False,
                        },
                        {
                            "check_with": check_command_variables,
                        },
                    ]
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
                                "allof": [
                                    {
                                        "type": "list",
                                        "empty": False,
                                        "required": False,
                                        "dependencies": "^matrix",
                                    },
                                    {
                                        "check_with": variables_exist,
                                    },
                                ]
                            },
                        }
                    },
                    {
                        "schema": {
                            "filename": {"type": "string", "empty": False},
                            "format": {"type": "string", "allowed": ["bar-chart"]},
                            "x-axis": {
                                "allof": [
                                    {
                                        "type": "string",
                                        "empty": False,
                                        "required": True,
                                        "dependencies": "^matrix",
                                    },
                                    {
                                        "check_with": variable_exists,
                                    },
                                ]
                            },
                            "color": {
                                "allof": [
                                    {
                                        "type": "string",
                                        "empty": False,
                                        "required": False,
                                        "dependencies": "^matrix",
                                    },
                                    {
                                        "check_with": variable_exists,
                                    },
                                ]
                            },
                            "facet": {
                                "allof": [
                                    {
                                        "type": "string",
                                        "empty": False,
                                        "required": False,
                                        "dependencies": "^matrix",
                                    },
                                    {
                                        "check_with": variable_exists,
                                    },
                                ]
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
    v = Validator(schema=valid_schema)
    if not v.validate(config):
        error_and_exit(v.errors)
