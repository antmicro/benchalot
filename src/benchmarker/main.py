import yaml
from sys import argv, executable
from benchmarker.validation import validate_config
from benchmarker.preparation import (
    prepare_benchmarks,
    name_benchmark_stages,
    prepare_before_after_all_commands,
)
from benchmarker.execution import (
    perform_benchmarks,
    execute_section,
    set_working_directory,
)
from os import geteuid, execvp
from benchmarker.variance import modify_system_state, restore_system_state
from benchmarker.output import output_results_from_dict, output_results_from_file
from argparse import ArgumentParser
from os.path import isfile
from benchmarker.log import (
    setup_benchmarker_logging,
    setup_command_logging,
    crash_msg_log_file,
)
from logging import getLogger
from atexit import unregister
from os import environ
from pathlib import Path
from pprint import pprint

logger = getLogger(f"benchmarker.{__name__}")


def main():
    parser = get_argument_parser()
    args = parser.parse_args()
    setup_benchmarker_logging(args.verbose, args.debug)

    for file in args.include:
        if not isfile(file):
            logger.critical(f"File '{file}' not found")
            exit(1)

    config_file = load_configuration_file(args.config_filename)
    config = validate_config(config_file)
    if args.split:
        generate_config_files(config, args.split)
    exit(1)
    if not args.update_output:
        is_root = geteuid() == 0
        if config["system"]["modify"] and not is_root:
            print(
                "To perform system configuration, root privileges are required. Running sudo..."
            )
            execvp("sudo", ["sudo", executable] + argv)
        if config["system"]["modify"]:
            modify_system_state(config["system"])
        run_config = config["run"]
        run_config["benchmark"] = name_benchmark_stages(run_config["benchmark"])
        benchmarks = prepare_benchmarks(
            run_config, config["matrix"], config["system"]["isolate-cpus"]
        )
        before_all_commands, after_all_commands = prepare_before_after_all_commands(
            run_config, config["matrix"]
        )

        if config["run"]["save-output"]:
            setup_command_logging(config["run"]["save-output"])
        set_working_directory(config["run"]["cwd"])
        environ.update(config["run"]["env"])

        execute_section(before_all_commands, "before-all")
        results = perform_benchmarks(benchmarks, config["run"]["samples"])
        execute_section(after_all_commands, "after-all")

        if config["system"]["modify"]:
            restore_system_state(config["system"])

        output_results_from_dict(
            results,
            config["output"],
            config["matrix"],
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


def get_argument_parser() -> ArgumentParser:
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
    mul_input_split_group = parser.add_mutually_exclusive_group()
    include_update_group = mul_input_split_group.add_mutually_exclusive_group()
    include_update_group.add_argument(
        "-i",
        "--include",
        nargs="+",
        dest="include",
        metavar="CSV_FILE",
        default=[],
        help="append previous results to the new output",
    )

    include_update_group.add_argument(
        "-u",
        "--update-output",
        dest="update_output",
        metavar="CSV_FILE",
        default=False,
        help="regenerate the output without re-running benchmarks",
        nargs="+",
    )
    mul_input_split_group.add_argument(
        "-s",
        "--split",
        nargs="+",
        dest="split",
        metavar="VAR_NAME",
        default=[],
        help="create new configuration file for each VAR_NAME",
    )
    return parser


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


def generate_config_files(config: dict, split: list[str]):
    def split_matrix(matrix, along):
        if not along:
            return [matrix]
        along_key = along[0]
        mul_m = split_matrix(
            {key: value for key, value in matrix.items() if key != along_key}, along[1:]
        )
        ret = []
        for m in mul_m:
            for value in matrix[along_key]:
                new_m = {key: value for key, value in m.items()}
                new_m[along_key] = [value]
                ret.append(new_m)
        return ret

    matrices = split_matrix(config["matrix"], split)
    for i, matrix in enumerate(matrices):
        c = {k: v for k, v in config.items() if k != "matrix"}
        c["matrix"] = matrix
        Path("configs").mkdir(exist_ok=True)
        with open(f"configs/config{i}.yml", "w") as file:
            yaml.dump(c, file)
