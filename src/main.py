import yaml
from sys import argv, executable
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from os import geteuid, execvp
from variance import modify_system_state, restore_system_state
from output import output_results_from_list, output_results_from_file
from argparse import ArgumentParser
from os.path import isfile
from log import (
    setup_benchmarker_logging,
    setup_command_logging,
    crash_msg_log_file,
)
from logging import getLogger
from atexit import unregister

logger = getLogger(f"benchmarker.{__name__}")


# load configuration file
def load_configuration_file(filename):
    try:
        config_file = open(argv[1], "r")
    except FileNotFoundError:
        logger.critical(f"File '{filename}' not found.")
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
parser.add_argument(
    "-d",
    "--debug",
    dest="debug",
    default=False,
    action="store_true",
    help="print debug information during Benchmarker execution",
)
parser.add_argument(
    "-v",
    "--verbose",
    default=False,
    action="store_true",
    dest="verbose",
    help="print basic information during Benchmarker execution",
)

parser.add_argument(
    "-i",
    "--include",
    nargs="+",
    dest="include",
    metavar="CSV_FILE",
    default=[],
    help="append previous results to the new output",
)

args = parser.parse_args()
setup_benchmarker_logging(args.verbose, args.debug)

for file in args.include:
    if not isfile(file):
        logger.critical(f"File '{file}' not found")
        exit(1)

config_file = load_configuration_file(args.config_filename)
config = validate_config(config_file)


if not args.regenerate_output:
    config = load_configuration_file(args.config_filename)
    config = validate_config(config)
    benchmarks = prepare_benchmarks(config)
    if "save-output" in config["run"]:
        setup_command_logging(config["run"]["save-output"])
    results = perform_benchmarks(benchmarks, config["run"]["samples"])
    if "system" in config:
        restore_system_state(config["system"])
    output_results_from_list(results, config, args.include)
else:
    config = load_configuration_file(args.config_filename)
    backup_file = args.regenerate_output
    try:
        csv_file = open(backup_file, "r")
    except FileNotFoundError:
        logger.critical(f"File '{backup_file}' not found.")
        exit(1)
    else:
        with csv_file:
            output_results_from_file(csv_file, config, args.include)
logger.info("Exiting Benchmarker...")
unregister(crash_msg_log_file)
