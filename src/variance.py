from atexit import register, unregister
from subprocess import run
from sys import stderr


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
