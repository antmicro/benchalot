from time import monotonic_ns
from subprocess import run
from yaspin import yaspin


def run_multiple_commands(commands: list):
    for c in commands:
        result = run(c, shell=True)
        if result.returncode != 0:
            print(
                f"Subprocess `{c}` exited abnormally (exit code: {result.returncode})"
            )
            exit(1)


def benchmark_commands(commands: list) -> float:
    with yaspin(text=f"Benchmarking {commands}...", timer=True):
        start = monotonic_ns()
        run_multiple_commands(commands)
        return (monotonic_ns() - start) / 1e9  # convert to seconds


def perform_benchmarks(benchmarks: list, repeat: int) -> list:
    results = []
    for benchmark in benchmarks:
        for i in range(0, repeat):
            if "before" in benchmark:
                run_multiple_commands(benchmark["before"])
            result = benchmark_commands(benchmark["benchmark"])
            if "after" in benchmark:
                run_multiple_commands(benchmark["after"])
            results.append(
                [benchmark["matrix"][key] for key in benchmark["matrix"]] + [result]
            )
    return results
