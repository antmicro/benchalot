import yaml
from sys import stderr, argv, executable
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from output import output_results_from_list, output_results_from_file


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


if len(argv) == 2:
    config = load_configuration_file(argv[1])
    config = validate_config(config)
    benchmarks = prepare_benchmarks(config)
    results = perform_benchmarks(benchmarks, config["run"]["samples"])
    output_results_from_list(results, config)
elif (len(argv) == 3 or len(argv) == 4) and argv[2] == "--update-output":
    config = load_configuration_file(argv[1])
    backup_file = ".a.out.csv"
    if len(argv) == 4:
        backup_file = argv[3]
    try:
        csv_file = open(backup_file, "r")
    except FileNotFoundError:
        print(f"ERROR:'{backup_file}' not found.", file=stderr)
        exit(1)
    else:
        with csv_file:
            output_results_from_file(csv_file, config)
else:
    print(f"Usage: {argv[0]}" + "<config> [--update-output]", file=stderr)
    print("\t --update-output [<old_output>]", file=stderr)
    exit(1)
