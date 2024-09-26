from sys import stderr
from schema import Schema, Optional, And, Or


def error(msg):
    print(f"ERROR: {msg}", file=stderr)
    exit(1)


def validate_config(config):
    reqs_for_commands = And(list, lambda x: len(x) > 0)
    config_schema = Schema({
        Optional("matrix"):{ 
            str: And(list, lambda x: len(x) > 0 ) # if matrix section exists it should contain variables which are non empty lists
        },
        "run": {
            "benchmark": reqs_for_commands,
            Optional("before"): reqs_for_commands,
            Optional("after"): reqs_for_commands
        },
        "output": {
            str: Or({"format":"csv",
                        "filename":str},
                       {"format":"table-md",
                        "filename":str,
                        Optional("columns"): And(list, lambda x: len(x) > 0)})
                        
        
        }
    })

    print(config_schema.validate(config))

    return
