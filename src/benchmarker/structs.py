from dataclasses import dataclass
from typing import Literal

TIME_STAMP_COLUMN = "benchmark_date"
BENCHMARK_ID_COLUMN = "benchmark"
HAS_FAILED_COLUMN = "has_failed"
METRIC_COLUMN = "metric"
STAGE_COLUMN = "stage"
RESULT_COLUMN = "result"
CONSTANT_COLUMNS = [
    BENCHMARK_ID_COLUMN,
    TIME_STAMP_COLUMN,
    HAS_FAILED_COLUMN,
    METRIC_COLUMN,
    STAGE_COLUMN,
    RESULT_COLUMN,
]
DISPLAYABLE_COLUMNS = [
    BENCHMARK_ID_COLUMN,
    TIME_STAMP_COLUMN,
    HAS_FAILED_COLUMN,
    METRIC_COLUMN,
    STAGE_COLUMN,
]
DEFAULT_STAGE_NAME = ""


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
