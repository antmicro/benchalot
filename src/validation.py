from sys import stderr
from cerberus import Validator


def validate_config(config):
    def variable_exists(field, value, error):
        if "matrix" not in config or value not in config["matrix"]:
            error(field, f"Variable `{value}` does not exist")

    def variables_exist(field, value, error):
        for var in value:
            variable_exists(field, var, error)

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
                "before": {"required": False, "type": "list", "empty": False},
                "benchmark": {"required": True, "type": "list", "empty": False},
                "after": {"required": False, "type": "list", "empty": False},
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
                        }
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
    v = Validator(valid_schema)
    if not v.validate(config):
        print(v.errors)
    else:
        print("Config file validated successfully")
