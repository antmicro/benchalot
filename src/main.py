import yaml
from sys import stderr, argv
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from output import output_results


# load configuration file
if len(argv) != 2:
    print(f"Usage: {argv[0]} <config>", file=stderr)
    exit(1)
try:
    config_file = open(argv[1], "r")
except FileNotFoundError:
    print(f"ERROR:'{argv[1]}' not found.", file=stderr)
    exit(1)
else:
    with config_file:
        config = yaml.safe_load(config_file)

config = validate_config(config)

benchmarks = prepare_benchmarks(config)

results = perform_benchmarks(benchmarks, config["run"]["repeat"])

output_results(results, config)
