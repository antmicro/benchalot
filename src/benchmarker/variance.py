from atexit import register, unregister
from subprocess import run
from multiprocessing import cpu_count
from logging import getLogger

logger = getLogger(f"benchmarker.{__name__}")


def get_and_set(filename: str, value: str) -> str:
    """First read value from the file, the set it to the new one.

    Args:
        filename: Name of the file to be modified.
        value: String to be written.

    Returns:
        str: Value read from the file.
    """
    try:
        file = open(filename, "r")
        ret = file.read()
        file.close()
        set(filename, value)
    except FileNotFoundError as e:
        logger.critical(f"Failed to read {filename} {e.strerror}")
        exit(1)
    return ret


def set(filename: str, value: str) -> None:
    """Write value to file.

    Args:
        filename: Name of the file.
        value: Value to be written.
    """
    try:
        file = open(filename, "w")
        file.write(value)
        file.close()
    except FileNotFoundError as e:
        logger.critical(f"Failed to set {value} to {filename} {e.strerror}")
        exit(1)
    value_str = value.strip()
    logger.debug(f"Wrote  '{value_str}' to '{filename}'.")


system_state: dict[str, str] = {}


def modify_system_state(system_options: dict) -> None:
    """Apply modifications to the operating system

    Args:
        system_options: Configuration file's system section.
    """
    logger.info("Modifying system state...")
    register(restore_system_state, system_options)
    if system_options.get("disable-aslr"):
        logger.debug("Disabling ASLR...")
        system_state["aslr"] = get_and_set(
            "/proc/sys/kernel/randomize_va_space", str(0)
        )
        logger.debug("Disabled ASLR.")
    if system_options["isolate-cpus"]:
        cpu_str = ""
        for cpu in system_options["isolate-cpus"]:
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
    if system_options.get("governor-performance"):
        cpus = (
            system_options["isolate-cpus"]
            if system_options["isolate-cpus"]
            else range(cpu_count())
        )
        logger.debug(f"Setting CPU governor for CPUs {cpus}...")
        for cpu in cpus:
            system_state[f"governor{cpu}"] = get_and_set(
                f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor",
                "performance",
            )
        logger.debug(f"Set CPU governor for CPUs {cpu_str}.")


def restore_system_state(system_options: dict) -> None:
    """Restore operating system's state.

    Args:
        system_options: Configuration file's system section.
    """
    logger.info("Restoring system state...")
    logger.debug(f"Saved system state: {system_options}")
    if system_state.get("isolate-cpus"):
        run("cset shield --reset", shell=True, capture_output=True)
        logger.debug("Removed CPU shield.")
    if system_options.get("governor-performance"):
        logger.debug("Restoring CPU governors...")
        for cpu in range(cpu_count()):
            key = f"governor{cpu}"
            if key in system_state:
                set(
                    f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor",
                    system_state[key],
                )
        logger.debug("Restored CPU governors.")
    logger.debug("Restoring ASLR...")
    if system_options.get("disable-aslr"):
        set("/proc/sys/kernel/randomize_va_space", system_state["aslr"])
    logger.debug("Restored ASLR.")
    unregister(restore_system_state)
    logger.info("Finished restoring system state.")
