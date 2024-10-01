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
    register(revert_variance_reductions, options)
    if "disable-aslr" in options and options["disable-aslr"]:
        try:
            aslr_file = open("/proc/sys/kernel/randomize_va_space", "w")
        except FileNotFoundError:
            print("ERROR: Failed to disable ASLR.")
            exit(1)
        else:
            with aslr_file:
                aslr_file.write(str(0))
                aslr_file.close()

    if "isolate-cpus" in options:
        cpu_str = ""
        for cpu in options["isolate-cpus"]:
            cpu_str += str(cpu) + ","
        cpu_str = cpu_str[:-1]
        result = run(f"cset shield --cpu={cpu_str} --kthread=on", shell=True)
        if result.returncode != 0:
            print(
                f"ERROR: Failed to isolate CPUs {cpu_str} (exit code {result.returncode})",
                file=stderr,
            )
            exit(1)
        if "governor-performance" in options and options["governor-performance"]:
            result = run(
                f"cpupower --cpu {cpu_str} frequency-set --governor performance",
                shell=True,
            )

            if result.returncode != 0:
                print(
                    f"ERROR: Failed to set CPUs {cpu_str} frequency governor to performance (exit code {result.returncode})",
                    file=stderr,
                )
                exit(1)

    elif "governor-performance" in options and options["governor-performance"]:
        result = run("cpupower frequency-set --governor performance", shell=True)
        if result.returncode != 0:
            print(
                f"ERROR: Failed to set CPUs frequency governor to performance (exit code {result.returncode})",
                file=stderr,
            )
            exit(1)


def revert_variance_reductions(options):
    if "isolate-cpus" in options:
        run("cset shield --reset", shell=True)
    if "disable-aslr" in options and options["disable-aslr"]:
        try:
            aslr_file = open("/proc/sys/kernel/randomize_va_space", "w")
        except FileNotFoundError:
            print("ERROR: Failed to enable ASLR.")
        else:
            with aslr_file:
                aslr_file.write(str(2))
                aslr_file.close()
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
