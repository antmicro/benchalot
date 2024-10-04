import yaml
from sys import stderr, argv
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from output import output_results
from logging import getLogger, DEBUG, FileHandler, Formatter, INFO

logger = getLogger("benchmarker_logger")
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
if "log" in config: 
    if "benchmarker" in config["log"]:
        handler = FileHandler(config["benchmarker"])
        formatter = Formatter("[%(asctime)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(DEBUG)
        handler = FileHandler("execution.log")
    formatter = Formatter("[%(asctime)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    command_logger = getLogger("execution_logger")
    command_logger.setLevel(INFO)
    command_logger.addHandler(handler)

benchmarks = prepare_benchmarks(config)

results = perform_benchmarks(benchmarks, config["run"]["samples"])

output_results(results, config)

logger.info("Exiting Benchmarker.")
