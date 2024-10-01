import yaml
from sys import stderr, argv
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from output import output_results
from subprocess import run
from os import geteuid
from atexit import register, unregister


def enable_variance_reductions(options):
    if "disable-aslr" in options and options["disable-aslr"]:
        f = open("/proc/sys/kernel/randomize_va_space", "w")
        f.write(str(0))
        f.close()

    if "isolate-cpus" in options:
        cpu_str = ""
        for cpu in options["isolate-cpus"]:
            cpu_str += str(cpu) + ","
        cpu_str = cpu_str[:-1]
        run(f"cset shield --cpu={cpu_str} --kthread=on", shell=True)
        if "governor-performance" in options and options["governor-performance"]:
            run(
                f"cpupower --cpu {cpu_str} frequency-set --governor performance",
                shell=True,
            )
    elif "governor-performance" in options and options["governor-performance"]:
        run("cpupower frequency-set --governor performance", shell=True)
    register(revert_variance_reductions, options)


def revert_variance_reductions(options):
    if "isolate-cpus" in options:
        run("cset shield --reset", shell=True)
    if "disable-aslr" in options and options["disable-aslr"]:
        f = open("/proc/sys/kernel/randomize_va_space", "w")
        f.write(str(2))
        f.close()
    unregister(revert_variance_reductions)


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
        f"ERROR: to use {config['options']} root privileges are required.", file=stderr
    )
    exit(1)
benchmarks = prepare_benchmarks(config)

if is_root:
    enable_variance_reductions(config["options"])

results = perform_benchmarks(benchmarks, config["run"]["samples"])

if is_root:
    revert_variance_reductions(config["options"])

output_results(results, config)
