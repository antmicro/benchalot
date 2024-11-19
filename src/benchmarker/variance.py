from atexit import register, unregister
from subprocess import run
from multiprocessing import cpu_count
from logging import getLogger
from benchmarker.validation import SystemSection
from os.path import isfile

logger = getLogger(f"benchmarker.{__name__}")


def get_and_set(filename: str, value: str) -> str:
    """First read the file, then overwrite with value.
    The function will crash the Benchmarker if the `filename` is not found.

    Args:
        filename: Name of the file.
        value: String to be written.

    Returns:
        str: Contents of the file.
    """
    try:
        file = open(filename, "r")
    except (FileNotFoundError, PermissionError) as e:
        logger.critical(f"Failed to read {filename} {e.strerror}")
        exit(1)
    else:
        with file:
            ret = file.read()
    set_contents(filename, value)
    return ret


def set_contents(filename: str, value: str) -> None:
    """Write value to a file.

    Args:
        filename: Name of the file.
        value: Value to be written.
    """
    try:
        file = open(filename, "w")
    except FileNotFoundError as e:
        logger.critical(f"Failed to set {value} to {filename} {e.strerror}")
        exit(1)
    else:
        with file:
            file.write(value)
    value_str = value.strip()
    logger.debug(f"Wrote  '{value_str}' to '{filename}'.")


system_state: dict = {}


def modify_system_state(system_options: SystemSection) -> None:
    """Apply variance reducing measures to the operating system.

    Args:
        system_options: Configuration file's system section.
    """
    logger.info("Modifying system state...")
    register(restore_system_state)
    if system_options.disable_aslr:
        logger.debug("Disabling ASLR...")
        system_state["aslr"] = get_and_set(
            "/proc/sys/kernel/randomize_va_space", str(0)
        )
        logger.debug("Disabled ASLR.")
    if system_options.isolate_cpus:
        cpu_str = ""
        for cpu in system_options.isolate_cpus:
            cpu_str += str(cpu) + ","
        cpu_str = cpu_str[:-1]
        logger.debug(f"Shielding CPUs {cpu_str}...")
        result = run(
            f"cset shield --cpu={cpu_str} --kthread=on", shell=True, capture_output=True
        )
        if result.returncode != 0:
            logger.critical(
                f"ERROR: Failed to isolate CPUs {cpu_str} (exit code {result.returncode})"
            )
            logger.critical(str(result.stderr))
            logger.critical(str(result.stdout))
            exit(1)
        system_state["isolate-cpus"] = "yes"
    if system_options.governor_performance:
        cpus = (
            system_options.isolate_cpus
            if system_options.isolate_cpus
            else range(cpu_count())
        )
        logger.debug(f"Setting CPU governor for CPUs {cpus}...")
        for cpu in cpus:
            system_state[f"governor{cpu}"] = get_and_set(
                f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor",
                "performance",
            )
        system_state["governor-performance"] = "yes"
        logger.debug(f"Set CPU governor for CPUs {cpu_str}.")
    if system_options.disable_smt:
        cpus = (
            system_options.isolate_cpus
            if system_options.isolate_cpus
            else range(cpu_count())
        )
        disabled_pairs = set()
        previous_settings = {}
        for cpu in cpus:
            sibling_str = (
                f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list"
            )
            if isfile(sibling_str):
                with open(sibling_str, "r") as file:
                    pair_str = file.read().strip()
                pair = tuple(pair_str.split(","))
                if len(pair) == 2:
                    if pair not in disabled_pairs:
                        previous_settings[
                            f"/sys/devices/system/cpu/cpu{pair[1]}/online"
                        ] = get_and_set(
                            f"/sys/devices/system/cpu/cpu{pair[1]}/online", str(0)
                        )
                    disabled_pairs.add(pair)
        system_state["disable-smt"] = previous_settings
    if system_options.disable_core_boost:
        # https://wiki.archlinux.org/title/CPU_frequency_scaling#Configuring_frequency_boosting
        if isfile("/sys/devices/system/cpu/cpufreq/boost"):
            system_state["disable_core_boost"] = (
                "/sys/devices/system/cpu/cpufreq/boost",
                get_and_set("/sys/devices/system/cpu/cpufreq/boost", str(0)),
            )
        elif isfile("/sys/devices/system/cpu/intel_pstate/no_turbo"):
            system_state["disable_core_boost"] = (
                "/sys/devices/system/cpu/intel_pstate/no_turbo",
                get_and_set("/sys/devices/system/cpu/intel_pstate/no_turbo", str(1)),
            )
        else:
            logger.error("Failed to disable core boosting.")


def restore_system_state() -> None:
    """Restore operating system's state from before Benchmarker's modifications.

    Args:
        system_options: Configuration file's system section.
    """
    logger.info("Restoring system state...")
    logger.debug(system_state)
    if system_state.get("isolate-cpus"):
        run("cset shield --reset", shell=True, capture_output=True)
        logger.debug("Removed CPU shield.")
    if system_state.get("governor-performance"):
        logger.debug("Restoring CPU governors...")
        for cpu in range(cpu_count()):
            key = f"governor{cpu}"
            if key in system_state:
                set_contents(
                    f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor",
                    system_state[key],
                )
        logger.debug("Restored CPU governors.")
    logger.debug("Restoring ASLR...")
    if system_state.get("disable-aslr"):
        set_contents("/proc/sys/kernel/randomize_va_space", system_state["aslr"])
    logger.debug("Restored ASLR.")
    logger.debug("Restoring boost...")
    if system_state.get("disable_core_boost"):
        file, setting = system_state["disable_core_boost"]
        set_contents(file, setting)
    logger.debug("Restoring smt...")
    if system_state.get("disable-smt"):
        for cpu, value in system_state["disable-smt"].items():
            set_contents(cpu, value)  # type: ignore
    logger.debug("Restored smt.")
    unregister(restore_system_state)
    logger.info("Finished restoring system state.")
