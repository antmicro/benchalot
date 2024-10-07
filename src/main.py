import yaml
from sys import stderr, argv, executable
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from logging import getLogger, FileHandler, Formatter, getLevelNamesMapping, INFO
from os import geteuid, execvp
from variance import modify_system_state, restore_system_state
from output import output_results_from_list, output_results_from_file
from argparse import ArgumentParser


# load configuration file
def load_configuration_file(filename):
    try:
        config_file = open(argv[1], "r")
    except FileNotFoundError:
        print(f"ERROR:'{argv[1]}' not found.", file=stderr)
        exit(1)
    else:
        with config_file:
            config = yaml.safe_load(config_file)

    return config


parser = ArgumentParser(
    prog="python src/main.py",
    description="Benchmarker is a tool used for automatic benchmarking of software.",
)
parser.add_argument("config_filename", help="a path to YAML configuration file")
parser.add_argument(
    "-u",
    "--update-output",
    dest="regenerate_output",
    metavar="OLD_OUTPUT",
    default=False,
    help="regenerate the output without re-running benchmarks",
)

args = parser.parse_args()
config_file = load_configuration_file(args.config_filename)
config = validate_config(config_file)
#  configure loggers
if "log" in config:
    formatter = Formatter(
        "[%(asctime)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S"
    )
    if "benchmarker" in config["log"]:
        handler = FileHandler(config["log"]["benchmarker"]["filename"])
        handler.setFormatter(formatter)
        benchmarker_logger = getLogger("benchmarker")
        benchmarker_logger.addHandler(handler)
        if "level" in config["log"]["benchmarker"]:
            benchmarker_logger.setLevel(
                getLevelNamesMapping()[config["log"]["benchmarker"]["level"]]
            )
        else:
            benchmarker_logger.setLevel(INFO)
    if "run" in config["log"]:
        handler = FileHandler(config["log"]["run"]["filename"])
        handler.setFormatter(formatter)
        command_logger = getLogger("run")
        if "level" in config["log"]["run"]:
            command_logger.setLevel(
                getLevelNamesMapping()[config["log"]["run"]["level"]]
            )
        else:
            command_logger.setLevel(INFO)
        command_logger.addHandler(handler)

logger = getLogger(f"benchmarker.{__name__}")
if not args.regenerate_output:
    config = load_configuration_file(args.config_filename)
    config = validate_config(config)
    benchmarks = prepare_benchmarks(config)
    results = perform_benchmarks(benchmarks, config["run"]["samples"])
    if "system" in config:
        restore_system_state(config["system"])
    output_results_from_list(results, config)
else:
    config = load_configuration_file(args.config_filename)
    backup_file = args.regenerate_output
    try:
        csv_file = open(backup_file, "r")
    except FileNotFoundError:
        print(f"ERROR:'{backup_file}' not found.", file=stderr)
        exit(1)
    else:
        with csv_file:
            output_results_from_file(csv_file, config)
