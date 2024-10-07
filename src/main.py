import yaml
from sys import argv, executable
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from logging import (
    getLogger,
    FileHandler,
    Formatter,
    getLevelNamesMapping,
    INFO,
    DEBUG,
    StreamHandler,
    CRITICAL,
)
from os import geteuid, execvp
from variance import modify_system_state, restore_system_state
from output import output_results_from_list, output_results_from_file
from argparse import ArgumentParser


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
parser.add_argument("-d", "--debug", dest="debug", default=False, action="store_true")
parser.add_argument(
    "-v", "--verbose", default=False, action="store_true", dest="verbose"
)

args = parser.parse_args()

benchmarker_logger = getLogger("benchmarker")
formatter = Formatter(
    "[%(asctime)s][%(name)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S"
)
# if args.info_log:
#     handler = FileHandler(args.info_log)
#     handler.setFormatter(formatter)
#     handler.setLevel(INFO)
#     benchmarker_logger.addHandler(handler)
#     benchmarker_logger.setLevel(INFO)
# if args.debug_log:
#     handler = FileHandler(args.debug_log)
#     handler.setFormatter(formatter)
#     handler.setLevel(DEBUG)
#     benchmarker_logger.addHandler(handler)
#     benchmarker_logger.setLevel(DEBUG)
console = StreamHandler()
console.setFormatter(
    Formatter("[%(asctime)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S")
)
getLogger().addHandler(console)
getLogger().setLevel(CRITICAL)
if args.verbose:
    getLogger().setLevel(INFO)
if args.debug:
    getLogger().setLevel(DEBUG)


config_file = load_configuration_file(args.config_filename)
config = validate_config(config_file)


#  configure loggers
if "log" in config:
    formatter = Formatter(
        "[%(asctime)s][%(levelname)s]: %(message)s", datefmt="%H:%M:%S"
    )
    handler = FileHandler(config["log"]["filename"])
    handler.setFormatter(formatter)
    command_logger = getLogger("run")
    if "level" in config["log"]:
        command_logger.setLevel(getLevelNamesMapping()[config["log"]["level"]])
    else:
        command_logger.setLevel(INFO)
    command_logger.addHandler(handler)

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
        logger.critical(f"File '{backup_file}' not found.")
        exit(1)
    else:
        with csv_file:
            output_results_from_file(csv_file, config)
