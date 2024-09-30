import yaml
from sys import stderr, argv
from validation import validate_config
from preparation import prepare_benchmarks
from execution import perform_benchmarks
from output import output_results
from subprocess import run
from os import geteuid

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
if geteuid() != 0:
    print("ERROR: You need root privileges to run.", file=stderr)
    exit(1)

# Disable address space randomization:
# Shield CPU0


config = validate_config(config)
print(config)

benchmarks = prepare_benchmarks(config)

f = open("/proc/sys/kernel/randomize_va_space", "w")
f.write(str(0))
f.close()

cpu_str = ""
for cpu in config["options"]["isolate-cpus"]:
    cpu_str += str(cpu) + ","
    f = open(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor", "w")
    f.write("performance")
    f.close()
cpu_str = cpu_str[:-1]

run(f"cset shield --cpu={cpu_str} --kthread=on", shell=True)
results = perform_benchmarks(benchmarks, config["run"]["samples"])

run("cset shield --reset", shell=True)
f = open("/proc/sys/kernel/randomize_va_space", "w")
f.write(str(2))
f.close()
output_results(results, config)
