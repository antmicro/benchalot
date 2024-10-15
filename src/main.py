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
        config_file = open(filename, "r")
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
group = parser.add_mutually_exclusive_group()
group.add_argument(
    "-i",
    "--include",
    nargs="+",
    dest="include",
    metavar="CSV_FILE",
    default=[],
    help="append previous results to the new output",
)

group.add_argument(
    "-u",
    "--update-output",
    dest="update_output",
    metavar="CSV_FILE",
    default=False,
    help="regenerate the output without re-running benchmarks",
    nargs="+",
)

args = parser.parse_args()
setup_benchmarker_logging(args.verbose, args.debug)

for file in args.include:
    if not isfile(file):
        logger.critical(f"File '{file}' not found")
        exit(1)

config_file = load_configuration_file(args.config_filename)
config = validate_config(config_file)


if not args.update_output:
    is_root = geteuid() == 0
    if "system" in config and not is_root:
        print(
            "To perform system configuration, root privileges are required. Running sudo..."
        )
        execvp("sudo", ["sudo", executable] + argv)

    if "system" in config:
        modify_system_state(config["system"])

    benchmarks = prepare_benchmarks(config)
    if "save-output" in config["run"]:
        setup_command_logging(config["run"]["save-output"])
    results = perform_benchmarks(benchmarks, config["run"]["samples"])

    if "system" in config:
        restore_system_state(config["system"])

    output_results_from_list(results, config, args.include)
else:
    old_outputs = args.update_output
    for file in old_outputs:
        if not isfile(file):
            logger.critical(f"File '{file}' not found")
            exit(1)
    output_results_from_file(config, old_outputs)
logger.info("Exiting Benchmarker...")
unregister(crash_msg_log_file)
