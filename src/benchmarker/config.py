from pydantic import (
    BaseModel,
    ValidationError,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    computed_field,
)
from typing import Any, Literal
from logging import getLogger
from os.path import isdir
from benchmarker.output_constants import (
    DEFAULT_STAGE_NAME,
    METRIC_COLUMN,
    STAGE_COLUMN,
    CONSTANT_COLUMNS,
)
from enum import StrEnum

logger = getLogger(f"benchmarker.{__name__}")


def error_and_exit(error):
    logger.critical("Config validation failed.")
    logger.critical(f"Encountered {error.error_count()} errors")
    for e in error.errors():
        location = ".".join(e["loc"])
        logger.critical(f"{location}: {e['msg']}, input: '{e['input']}'")
    exit(1)


class SystemSection(BaseModel):
    """Schema for `system` section of the configuration file.

    Attributes:
        isolate_cpus: CPU cores which will be shielded by `cpuset`.
        disable_aslr: Option to disable address space layout randomization.
        disable_smt: Option to disable simultaneous multi-threading (hyper-threading on Intel CPUs).
        disable_core_boost: Option to disable core boosting (Turbo Boost on Intel/Turbo-Core on AMD).
        governor_performance: Option to change CPU governor to performance.
    """

    isolate_cpus: list[int] | None = Field(default=None, alias="isolate-cpus")
    disable_aslr: bool = Field(default=False, alias="disable-aslr")
    disable_smt: bool = Field(default=False, alias="disable-smt")
    disable_core_boost: bool = Field(default=False, alias="disable-core-boost")
    governor_performance: bool = Field(default=False, alias="governor-performance")
    model_config = ConfigDict(extra="forbid")

    @computed_field  # type: ignore
    @property
    def modify(self) -> bool:
        """ "Whether the system will need to be modified."""
        isolate_cpus_empty = not self.isolate_cpus
        return (
            self.disable_aslr
            or self.governor_performance
            or not isolate_cpus_empty
            or self.disable_smt
            or self.disable_core_boost
        )


class BuiltInMetrics(StrEnum):
    TIME = "time"
    STDOUT = "stdout"
    STDERR = "stderr"
    STIME = "stime"
    UTIME = "utime"
    MEM = "rss"




class OutputFormat(StrEnum):
    CSV = "csv"
    MD = "md"
    HTML = "html"
    SCATTER = "scatter"
    BAR = "bar"
    VIOLIN = "violin"
    BOX = "box"


class OutputField(BaseModel):
    """Parent class for output formats.

    Attributes:
        filename: Name of the output file.
        format: Name of the output format.
        metric: Name of the metric shown in the output.
    """

    filename: str
    format: str


class CsvOutput(OutputField):
    """Schema of a csv output field.

    Attributes:
        format: Must be "csv".
    """

    format: Literal[OutputFormat.CSV]
    overwrite: bool = False
    model_config = ConfigDict(extra="forbid")


class BasePlotOutput(OutputField):
    """Parent class for different kinds of plots.

    Attributes:
        format: Must be "bar-chart".
        x_axis: Name of a variable which will used as x-axis of the chart.
        metric: Name of a metric which will used as y-axis of the chart.
        facet: Name of a variable which will be used to facet the chart.
        color: Name of a variable which will be used as color channel of the chart.
        width: Resulting plot image width in inches.
        height: Resulting plot image height in inches.
        dpi: Resulting plot image DPI.
    """

    format: str
    x_axis: str | None = Field(default=None, alias="x-axis")
    y_axis: str | None = Field(default=None, alias="y-axis")
    facet: str | None = None
    color: str | None = None
    width: int = Field(default=10, ge=1)
    height: int = Field(default=9, ge=1)
    dpi: int = Field(default=100, ge=50)


class BarChartOutput(BasePlotOutput):
    """Schema of a bar chart output field.

    Attributes:
        stat: What mathematical function should be used to determine bar-height.
    """

    format: Literal[OutputFormat.BAR]
    stat: Literal["max", "min", "mean", "median", "max"] = "median"
    model_config = ConfigDict(extra="forbid")


class BoxPlotOutput(BasePlotOutput):
    format: Literal[OutputFormat.BOX]
    model_config = ConfigDict(extra="forbid")


class ScatterPlotOutput(BasePlotOutput):
    format: Literal[OutputFormat.SCATTER]
    model_config = ConfigDict(extra="forbid")


class ViolinPlotOutput(BasePlotOutput):
    format: Literal[OutputFormat.VIOLIN]
    model_config = ConfigDict(extra="forbid")


class TableOutput(OutputField):
    """Schema of a markdown table output field.

    Attributes:
        columns: List of variables which will be included in the output table.
        stats: What mathematical functions should be used to determine values in result columns.
        pivot: String containing variable names determining names and contents of result columns.
        metrics: List of metrics to be included in the table.
    """

    columns: list[str] | None = None
    stats: list[Literal["min", "median", "mean", "relative", "std", "max"]] = [
        "min",
        "median",
        "max",
    ]
    pivot: str | None = "{{" + STAGE_COLUMN + "}} {{" + METRIC_COLUMN + "}}"
    metrics: list[str] | None = None
    model_config = ConfigDict(extra="forbid")


class TableMdOutput(TableOutput):
    format: Literal[OutputFormat.MD]


class TableHTMLOutput(TableOutput):
    format: Literal[OutputFormat.HTML]


OutputSection = dict[
    str,
    TableHTMLOutput
    | CsvOutput
    | BarChartOutput
    | BoxPlotOutput
    | ScatterPlotOutput
    | ViolinPlotOutput
    | TableMdOutput,
]


class ConfigFile(BaseModel):
    """Schema of the configuration file.

    Attributes:
        matrix: Section containing variables and their values.
        exclude_matrix: Section containing combinations of variable values for which no benchmarks will be created.
        system: Section containing variance reducing, system modifying options.
        run: Section containing commands.
        output: Section containing desired outputs.
    """

    matrix: dict[str, list] = {}
    exclusions: list[dict[str, str | int | float]] = []
    system: SystemSection = SystemSection()
    output: OutputSection | None = None
    samples: int = 1
    save_output: str | None = Field(default=None, alias="save-output")
    init: list[str] = []
    pre_bench: list[str] = Field(default=[], alias="pre-bench")
    bench: dict[str, list]
    post_bench: list[str] = Field(default=[], alias="pre-bench")
    cleanup: list[str] = []
    cwd: str | None = None
    metrics: set[BuiltInMetrics] = set()
    custom_metrics: list[dict[str, str]] = Field(default=[], alias="custom-metrics")
    env: dict[str, str] = {}
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    def name_stages(self):
        """Transform list of commands to dictionary of lists of commands."""
        if type(self["bench"]) is list:
            self["bench"] = {DEFAULT_STAGE_NAME: self["bench"]}
            return self
        return self

    @field_validator("cwd")
    @classmethod
    def path_exists(cls, value: str):
        if value and not isdir(value):
            raise ValueError(f"directory '{value}' not found")
        return value

    @field_validator("env", mode="before")
    @classmethod
    def env_values_to_str(cls, env_vars: dict[str, Any]) -> dict[str, Any]:
        for key in env_vars:
            if isinstance(env_vars[key], (int, float)):
                env_vars[key] = str(env_vars[key])
        return env_vars

    @model_validator(mode="after")
    def set_time_as_default(self):
        if len(self.metrics) == 0 and len(self.custom_metrics) == 0:
            self.metrics = {BuiltInMetrics.TIME}
        return self

    @field_validator("matrix")
    @classmethod
    def not_resevered_keyword(cls, matrix: dict[str, list]):
        """Check if one of matrix variable names is reserved keyword (one of the built-in column names)."""
        for var_name in matrix:
            if var_name in CONSTANT_COLUMNS:
                raise ValueError(f"'{var_name}' is a reserved keyword")
        return matrix

    @model_validator(mode="after")
    def at_least_one_csv(self):
        """Check if output section contains at least one csv output, if not create a default `result.csv` output config."""
        if not self.output:
            self.output = {}
        for output_key in self.output:
            output = self.output[output_key]
            if output.format == OutputFormat.CSV:
                return self
        self.output["default-csv"] = CsvOutput(
            format=OutputFormat.CSV, filename="result.csv"
        )
        return self


class OutputConfig(BaseModel):
    """Schema of the configuration file used for generating output without running benchmarks.

    Attributes:
        output: Section containing desired outputs.
    """

    output: OutputSection


def validate_config(config) -> ConfigFile:
    logger.info("Validating config...")
    try:
        config_validator = ConfigFile(**config)
    except ValidationError as e:
        error_and_exit(e)
    normalized_config = config_validator
    logger.debug(normalized_config)
    return normalized_config


def validate_output_config(config) -> OutputConfig:
    logger.info("Validating output config...")
    try:
        config_validator = OutputConfig(**config)
    except ValidationError as e:
        error_and_exit(e)
    normalized_config = config_validator
    logger.debug(normalized_config)
    return config_validator
