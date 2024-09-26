from time import monotonic_ns
from subprocess import run


def run_multiple_commands(commands: list):
    for c in commands:
        run(c, shell=True)


def benchmark_commands(commands: list) -> float:
    start = monotonic_ns()
    run_multiple_commands(commands)
    return (monotonic_ns() - start) / 1e9  # convert to seconds


def perform_benchmarks(benchmarks: list) -> list:
    results = []
    for benchmark in benchmarks:
        if "before" in benchmark:
            run_multiple_commands(benchmark["before"])
        result = benchmark_commands(benchmark["benchmark"])
        if "after" in benchmark:
            run_multiple_commands(benchmark["after"])
        results.append(
            [benchmark["matrix"][key] for key in benchmark["matrix"]] + [result]
        )
    return results
