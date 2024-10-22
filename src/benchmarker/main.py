import yaml
from sys import argv, executable
from benchmarker.validation import validate_config
from benchmarker.preparation import prepare_benchmarks
from benchmarker.execution import (
    perform_benchmarks,
    execute_section,
    set_working_directory,
)
from os import geteuid, execvp
from benchmarker.variance import modify_system_state, restore_system_state
from benchmarker.output import output_results_from_list, output_results_from_file
from argparse import ArgumentParser
from os.path import isfile
from benchmarker.log import (
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


def main():
    parser = ArgumentParser(
        prog="benchmarker",
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
        if config["system"]["modify"] and not is_root:
            print(
                "To perform system configuration, root privileges are required. Running sudo..."
            )
            execvp("sudo", ["sudo", executable] + argv)
        if config["system"]["modify"]:
            modify_system_state(config["system"])

        benchmarks = prepare_benchmarks(
            config["run"], config["matrix"], config["system"]["isolate-cpus"]
        )

        if config["run"]["save-output"]:
            setup_command_logging(config["run"]["save-output"])
        set_working_directory(config["run"]["cwd"])

        execute_section(config["run"]["before-all"], "before-all")
        results = perform_benchmarks(benchmarks, config["run"]["samples"])
        execute_section(config["run"]["after-all"], "after-all")

        if config["system"]["modify"]:
            restore_system_state(config["system"])

        output_results_from_list(
            results,
            config["output"],
            config["matrix"],
            config["run"]["metrics"],
            args.include,
        )
    else:
        old_outputs = args.update_output
        for file in old_outputs:
            if not isfile(file):
                logger.critical(f"File '{file}' not found")
                exit(1)
        output_results_from_file(config["output"], old_outputs, config["matrix"])
    logger.info("Exiting Benchmarker...")
    unregister(crash_msg_log_file)
