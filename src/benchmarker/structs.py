from collections.abc import Callable
from dataclasses import dataclass
from typing import Mapping


@dataclass
class BenchmarkResult:
    metric_name: str
    has_failed: bool
    measurements: Mapping[str, float | str]


@dataclass
class PreparedBenchmark:
    """Structure representing a single benchmark.

    Attributes:
        matrix: Combination of variable values used for this benchmark.
        before: Commands to be executed before the measurement.
        benchmark: Commands to be measured.
        after: Commands to be executed after the measurement.
        metric: Functions used to execute and gather results of the benchmark.
    """

    matrix: dict[str, str]
    before: list[str]
    benchmark: dict[str, list[str]]
    after: list[str]
    metrics: list[Callable[[dict], BenchmarkResult]]
