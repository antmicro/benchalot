from dataclasses import dataclass
from typing import Literal


@dataclass
class PreparedBenchmark:
    """Structure representing a single benchmark.

    Attributes:
        matrix: Combination of variable values used for this benchmark.
        before: Commands to be executed before the measurement.
        benchmark: Commands to be measured.
        after: Commands to be executed after the measurement.
        builtin_metrics: List of selected built-in metrics to be gathered during execution.
        custom_metrics: List of custom_metrics (names and commands) to be gathered during execution.
    """

    matrix: dict[str, str]
    before: list[str]
    benchmark: dict[str, list[str]]
    after: list[str]
    builtin_metrics: list[Literal["time", "stdout", "stderr"]]
    custom_metrics: list[dict[str, str]]
