import yaml
from sys import stderr, argv, executable
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from output import output_results_from_list, output_results_from_file

# load configuration file
if len(argv) != 2 and (len(argv) != 4 and argv[2] != "--output"):
    print(argv)
    print(f"Usage: {argv[0]} <config> [--output <csv>]", file=stderr)
    exit(1)


try:
    config_file = open(argv[1], "r")
except FileNotFoundError:
    print(f"'{argv[1]}' not found.", file=stderr)
    exit(1)
else:
    with config_file:
        config = yaml.safe_load(config_file)

config = validate_config(config)
if argv[2] == "--output":
    try:
        csv_file = open(argv[3], "r")
    except FileNotFoundError:
        print(f"ERROR:'{argv[3]}' not found.", file=stderr)
        exit(1)
    else:
        with csv_file:
            output_results_from_file(csv_file, config)
    exit(0)
results = []
benchmarks = prepare_benchmarks(config)

if "system" in config:
    modify_system_state(config["system"])

results = perform_benchmarks(benchmarks, config["run"]["samples"])

if "system" in config:
    restore_system_state(config["system"])

output_results_from_list(results, config)
