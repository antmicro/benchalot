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
from benchmarker.structs import (
    DISPLAYABLE_COLUMNS,
    DEFAULT_STAGE_NAME,
    METRIC_COLUMN,
    STAGE_COLUMN,
    CONSTANT_COLUMNS,
)
from re import findall
from benchmarker.interpolate import VAR_REGEX
from collections.abc import Sequence

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


class RunSection(BaseModel):
    """Schema for `run` section of the configuration file.

    Attributes:
        samples: How many times each benchmark should be repeated.
        save_output: Name of a file where `stdout` and `stderr` of executed commands will be saved.
        before_all: Commands to be executed before all the benchmarks.
        before:  Commands to be executed before each benchmark.
        benchmark: Commands to be benchmarked.
        after:  Commands to be executed after each benchmark.
        after-all:  Commands to be executed after all the benchmarks.
        cwd:  Working directory of the commands.
        metrics:  Metrics to be gathered during benchmarking.
        env: Enviromental variables used when running commands.
    """

    samples: int = 1
    save_output: str | None = Field(default=None, alias="save-output")
    before_all: list[str] = Field(default=[], alias="before-all")
    before: list[str] = []
    benchmark: dict[str, list]
    after: list[str] = []
    after_all: list[str] = Field(default=[], alias="after-all")
    cwd: str | None = None
    metrics: list[str | dict] = ["time"]
    env: dict[str, str] = {}
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    def name_stages(self):
        """Transform list of commands to dictionary of lists of commands."""
        if type(self["benchmark"]) is list:
            self["benchmark"] = {DEFAULT_STAGE_NAME: self["benchmark"]}
            return self
        return self

    @field_validator("cwd")
    @classmethod
    def path_exists(cls, value: str):
        if value and not isdir(value):
            raise ValueError(f"directory '{value}' not found")
        return value

    @field_validator("metrics")
    @classmethod
    def valid_metric(cls, metrics: list[str | dict]):
        if metrics is None:
            return metrics
        for metric in metrics:
            if type(metric) is str and metric not in ["time", "stdout", "stderr"]:
                raise ValueError(f"invalid metric '{metric}'")
        return metrics

    @field_validator("env", mode="before")
    @classmethod
    def env_values_to_str(cls, env_vars: dict[str, Any]) -> dict[str, Any]:
        for key in env_vars:
            if isinstance(env_vars[key], (int, float)):
                env_vars[key] = str(env_vars[key])
        return env_vars


class OutputField(BaseModel):
    """Parent class for output formats.

    Attributes:
        filename: Name of the output file.
        format: Name of the output format.
        metric: Name of the metric shown in the output.
    """

    filename: str
    format: str
    metric: str | None = None

    def apply_default_values(self, matrix, metrics):
        """Apply default values to missing fields.

        Args:
            matrix: `matrix` section from the configuration file.
            metrics: `run.metrics` section from the configuration file.
        """
        if self.metric is None:
            if len(metrics) != 1:
                raise ValueError(f"Metric for '{self.filename}' not specified")
            self.metric = (
                metrics[0] if type(metrics[0]) is str else list(metrics[0].keys())[0]
            )

    def check_options_exist(self, matrix):
        """Verify if options used in the output are present in the `matrix` section or are part of `DISPLAYABLE_COLUMNS`.

        Args:
            matrix: `matrix` section from the configuration file.

        Raises:
            ValueError
        """
        options = findall(VAR_REGEX, self.filename)
        for option in options:
            check_column_will_exist(option, matrix)

    def check_metric_exists(self, metrics):
        """Check if metric is present in the `run.metrics` section.

        Args:
            metric_name: Name of the metric.
            metrics: `run.metrics` section.
        """
        pass


class CsvOutput(OutputField):
    """Schema of a csv output field.

    Attributes:
        format: Must be "csv".
    """

    format: Literal["csv"]
    model_config = ConfigDict(extra="forbid")

    def check_metric_exists(self, metrics):
        pass

    def apply_default_values(self, matrix, metrics):
        pass


def check_metric(metric, metrics):
    metric_names = set()
    for m in metrics:
        if type(m) is dict:
            metric_names.add(list(m.keys())[0])
        else:
            metric_names.add(m)
    if metric not in metric_names:
        raise ValueError(f"metric '{metric}' not found")


class BarChartOutput(OutputField):
    """Schema of a bar chart output field.

    Attributes:
        format: Must be "bar-chart".
        x_axis: Name of a variable which will used as x-axis of the chart.
        metric: Name of a metric which will used as y-axis of the chart.
        facet: Name of a variable which will be used to facet the chart.
        color: Name of a variable which will be used as color channel of the chart.
        width: Resulting plot image width in inches.
        height: Resulting plot image height in inches.
        dpi: Resulting plot image DPI.
        stat: What mathematical function should be used to determine bar-height.
    """

    format: Literal["bar-chart"]
    x_axis: str | None = Field(default=None, alias="x-axis")
    metric: str | None = Field(default=None, alias="y-axis")
    facet: str | None = None
    color: str | None = None
    width: int = Field(default=10, ge=1)
    height: int = Field(default=9, ge=1)
    dpi: int = Field(default=100, ge=50)
    stat: Literal["max", "min", "mean", "median", "max"] = "median"
    model_config = ConfigDict(extra="forbid")

    def check_options_exist(self, matrix):
        """Check if facet, x-axis and color are present in the matrix section

        Args:
            matrix: `matrix` section from the configuration file.
        """
        super().check_options_exist(matrix)
        check_column_will_exist(self.facet, matrix)
        check_column_will_exist(self.x_axis, matrix)
        check_column_will_exist(self.color, matrix)

    def check_metric_exists(self, metrics):
        check_metric(self.metric, metrics)


class TableMdOutput(OutputField):
    """Schema of a markdown table output field.

    Attributes:
        format: Must be "table-md".
        columns: List of variables which will be included in the output table.
        stats: What mathematical functions should be used to determine values in result columns.
        pivot: String containing variable names determining names and contents of result columns.
        metrics: List of metrics to be included in the table.
    """

    format: Literal["table-md"]
    columns: list[str] | None = None
    stats: Sequence[Literal["min", "median", "mean", "relative", "std", "max"]] = [
        "min",
        "median",
        "max",
    ]
    pivot: str | None = "{{" + STAGE_COLUMN + "}} {{" + METRIC_COLUMN + "}}"
    metrics: list[str] | None = None
    model_config = ConfigDict(extra="forbid")

    def apply_default_values(self, matrix, metrics):
        """Apply default values.
        If `None`, set `columns` to contain all variables from `matrix` section.

        Raises:
            ValueError: If there are more than one metrics in `run.metrics` section and `result_column` is `None`.

        """
        if self.columns is None:
            self.columns = list(matrix.keys())

    def check_options_exist(self, matrix):
        """Check if columns contain valid variables' names."""
        super().check_options_exist(matrix)
        for column in self.columns:
            check_column_will_exist(column, matrix)
        if self.pivot:
            for column in findall(VAR_REGEX, self.pivot):
                check_column_will_exist(column, matrix)

    def check_metric_exists(self, metrics):
        if self.metrics is not None:
            for metric in self.metrics:
                check_metric(metric, metrics)


def check_column_will_exist(option, matrix):
    """Check if option specified will be present in results.

    Args:
        option: Is valid if it is variable name or one of the `DISPLAYABLE_COLUMNS`.
        matrix: `matrix` section from the configuration file.
    """
    if (
        option is not None
        and option not in matrix
        and option not in DISPLAYABLE_COLUMNS
    ):
        raise ValueError(f"'{option}' not found")


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
    run: RunSection
    output: dict[str, CsvOutput | BarChartOutput | TableMdOutput]
    model_config = ConfigDict(extra="forbid")

    @field_validator("matrix")
    @classmethod
    def not_resevered_keyword(cls, matrix: dict[str, list]):
        """Check if one of matrix variable names is reserved keyword (one of the built-in column names)."""
        for var_name in matrix:
            if var_name in CONSTANT_COLUMNS:
                raise ValueError(f"'{var_name}' is a reserved keyword")
        return matrix

    @field_validator("output")
    @classmethod
    def at_least_one_csv(
        cls, outputs: dict[str, CsvOutput | BarChartOutput | TableMdOutput]
    ):
        """Check if output section contains at least one csv output

        Raises:
            ValueError: When no csv is found.
        """
        for output_key in outputs:
            output = outputs[output_key]
            if type(output) is CsvOutput:
                return outputs
        raise ValueError("at least one 'csv' output is required")

    @model_validator(mode="after")
    def apply_default_values(self):
        """Apply default values for the output fields."""
        for output_key in self.output:
            output = self.output[output_key]
            output.apply_default_values(self.matrix, self.run.metrics)
        return self

    @model_validator(mode="after")
    def check_output_vars(self):
        """Check whether variables used in outputs are present in the `matrix` section."""
        for output_key in self.output:
            output = self.output[output_key]
            output.check_options_exist(self.matrix)
        return self

    @model_validator(mode="after")
    def check_output_metrics(self):
        """Check whether metrics used in outputs are present in the `run.metrics` section."""
        for output_key in self.output:
            output = self.output[output_key]
            output.check_metric_exists(self.run.metrics)
        return self


def validate_config(config) -> ConfigFile:
    logger.info("Validating config...")
    try:
        config_validator = ConfigFile(**config)
    except ValidationError as e:
        error_and_exit(e)
    normalized_config = config_validator
    logger.info("Successfully validated config.")
    logger.debug(normalized_config)
    return normalized_config
