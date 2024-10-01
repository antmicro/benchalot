import yaml
from sys import stderr, argv, executable
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from output import output_results
from os import geteuid, execvp
from variance import enable_variance_reductions, revert_variance_reductions


# load configuration file
if len(argv) != 2:
    print(f"Usage: {argv[0]} <config>", file=stderr)
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
is_root = geteuid() == 0

if "options" in config and not is_root:
    print(
        "To use variance reducing options root privileges are required. Running sudo..."
    )
    print(argv)
    execvp("sudo", ["sudo", executable] + argv)
benchmarks = prepare_benchmarks(config)

if "options" in config:
    enable_variance_reductions(config["options"])

results = perform_benchmarks(benchmarks, config["run"]["samples"])

if "options" in config:
    revert_variance_reductions(config["options"])

output_results(results, config)
