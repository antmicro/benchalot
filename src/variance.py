from atexit import register, unregister
from subprocess import run
from sys import stderr
from multiprocessing import cpu_count


def get_and_set(filename: str, value: str):
    try:
        file = open(filename, "r")
        ret = file.read()
        file.close()
        set(filename, value)
    except FileNotFoundError as e:
        print(f"ERROR: Failed to read {filename} {e.strerror}")
        exit(1)
    return ret


def set(filename: str, value: str):
    try:
        file = open(filename, "w")
        file.write(value)
        file.close()
    except FileNotFoundError as e:
        print(f"ERROR: Failed to set {filename} to {value} {e.strerror}")
        exit(1)


system_state = {}


def modify_system_state(system_options):
    register(restore_system_state, system_options)
    if system_options.get("disable-aslr"):
        system_state["aslr"] = get_and_set(
            "/proc/sys/kernel/randomize_va_space", str(0)
        )
    if "isolate-cpus" in system_options:
        cpu_str = ""
        for cpu in system_options["isolate-cpus"]:
            cpu_str += str(cpu) + ","
        cpu_str = cpu_str[:-1]
        result = run(f"cset shield --cpu={cpu_str} --kthread=on", shell=True)
        if result.returncode != 0:
            print(
                f"ERROR: Failed to isolate CPUs {cpu_str} (exit code {result.returncode})",
                file=stderr,
            )
            exit(1)
        if system_options.get("governor-performance"):
            for cpu in system_options["isolate-cpus"]:
                system_state[f"governor{cpu}"] = get_and_set(
                    f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor",
                    "performance",
                )
    elif system_options.get("governor-performance"):
        for cpu in range(cpu_count()):
            system_state[f"governor{cpu}"] = get_and_set(
                f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor",
                "performance",
            )


def restore_system_state(system_options):
    if "isolate-cpus" in system_options:
        run("cset shield --reset", shell=True)
        if system_options.get("governor-performance"):
            for cpu in system_options["isolate-cpus"]:
                set(
                    f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor",
                    system_state[f"governor{cpu}"],
                )
    elif system_options.get("governor-performance"):
        for cpu in range(cpu_count()):
            set(
                f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor",
                system_state[f"governor{cpu}"],
            )

    if system_options.get("disable-aslr"):
        try:
            aslr_file = open("/proc/sys/kernel/randomize_va_space", "w")
            aslr_file.write(system_state["aslr"])
            aslr_file.close()
        except FileNotFoundError:
            print("ERROR: Failed to restore state of ASLR.")

    unregister(restore_system_state)
