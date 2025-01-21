import datetime

TIME_STAMP_COLUMN = "datetime"
TIME_STAMP = datetime.datetime.now().strftime("%Y-%m-%d--%H-%M-%S")
BENCHMARK_ID_COLUMN = "benchmark"
HAS_FAILED_COLUMN = "failed"
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
DEFAULT_STAGE_NAME = ""
