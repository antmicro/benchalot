from pydantic import (
    BaseModel,
    ValidationError,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    computed_field,
)
from typing import Literal
from re import findall
from logging import getLogger
from os import getcwd
from os.path import isdir
from benchmarker.preparation import VAR_REGEX

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
        governor_performance: Option to change CPU governor to performance.
    """

    isolate_cpus: list[int] = Field(default=None, alias="isolate-cpus")
    disable_aslr: bool = Field(default=False, alias="disable-aslr")
    governor_performance: bool = Field(default=False, alias="governor-performance")
    model_config = ConfigDict(extra="forbid")

    @computed_field  # type: ignore
    @property
    def modify(self) -> bool:
        """ "Whether the system will need to be modified."""
        isolate_cpus_empty = not self.isolate_cpus
        return self.disable_aslr or self.governor_performance or not isolate_cpus_empty


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
    save_output: str = Field(default=None, alias="save-output")
    before_all: list[str] = Field(default=[], alias="before-all")
    before: list[str] = []
    benchmark: list[str] | dict[str, list]
    after: list[str] = []
    after_all: list[str] = Field(default=[], alias="after-all")
    cwd: str = getcwd()
    metrics: list[str | dict] = ["time"]
    env: dict[str, str] = {}
    model_config = ConfigDict(extra="forbid")

    @field_validator("cwd")
    @classmethod
    def path_exists(cls, value: str):
        if not isdir(value):
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


class OutputField(BaseModel):
    """Parent class for output formats.

    Attributes:
        filename: Name of the output file.
        format: Name of the output format.
    """

    filename: str
    format: str

    def apply_default_values(self, matrix, metrics):
        """Apply default values to missing fields.

        Args:
            matrix: `matrix` section from the configuration file.
            metrics: `run.metrics` section from the configuration file.
        """
        pass

    def check_vars_exist(self, matrix):
        """Verify if variables used in the output are present in the `matrix` section.

        Args:
            matrix: `matrix` section from the configuration file.

        Raises:
            ValueError
        """
        pass

    def check_metric_exists(self, metric_name, metrics):
        """Check if metric is present in the `run.metrics` section.

        Args:
            metric_name: Name of the metric.
            metrics: `run.metrics` section.

        Raises:
            ValueError
        """
        metric_names = [
            name if type(name) is str else list(name.keys())[0] for name in metrics
        ]
        if metric_name not in metric_names:
            raise ValueError(f"metric '{metric_name}' not found")

    def check_metrics_exist(self, metrics):
        """Check if metrics used in the output are present in the `run.metrics` section.

        Args:
            metrics: `run.metrics` section.

        Raises:
            ValueError
        """
        pass


class CsvOutput(OutputField):
    """Schema of a csv output field.

    Attributes:
        format: Must be "csv".
    """

    format: Literal["csv"]
    model_config = ConfigDict(extra="forbid")


class BarChartOutput(OutputField):
    """Schema of a bar chart output field.

    Attributes:
        format: Must be "bar-chart".
        x_axis: Name of a variable which will used as x-axis of the chart.
        y_axis: Name of a metric which will used as y-axis of the chart.
        facet: Name of a variable which will be used to facet the chart.
        color: Name of a variable which will be used as color channel of the chart.
        width: Resulting plot image width in inches.
        height: Resulting plot image height in inches.
        dpi: Resulting plot image DPI.
        stat: What mathematical function should be used to determine bar-height.
    """

    format: Literal["bar-chart"]
    x_axis: str = Field(default=None, alias="x-axis")
    y_axis: str = Field(default=None, alias="y-axis")
    facet: str | None = None
    color: str | None = None
    width: int = Field(default=10, ge=1)
    height: int = Field(default=9, ge=1)
    dpi: int = Field(default=100, ge=50)
    stat: Literal["min", "mean", "median", "max"] = "median"
    model_config = ConfigDict(extra="forbid")

    def apply_default_values(self, matrix, metrics):
        """Apply default values to missing fields.
        Set y-axis (if missing) to the only metric specified in the config.

        Args:
            matrix: `matrix` section from the configuration file.
            metrics: `run.metrics` section from the configuration file.

        Raises:
            ValueError: If there are more than one metrics in `run.metrics` section and y-axis is `None`.
        """
        if self.y_axis is None:
            if len(metrics) != 1:
                raise ValueError("'y-axis' not specified")
            self.y_axis = (
                metrics[0] if type(metrics[0]) is str else list(metrics[0].keys())[0]
            )

    def check_vars_exist(self, matrix):
        """Check if facet, x-axis and color are present in the matrix section

        Args:
            matrix: `matrix` section from the configuration file.
        """
        check_var_exists(self.facet, matrix)
        check_var_exists(self.x_axis, matrix)
        check_var_exists(self.color, matrix)

    def check_metrics_exist(self, metrics):
        super().check_metric_exists(self.y_axis, metrics)


class TableMdOutput(OutputField):
    """Schema of a markdown table output field.

    Attributes:
        format: Must be "table-md".
        columns: List of variables which will be included in the output table.
        result_column: Metric which will be included in the table.
    """

    format: Literal["table-md"]
    columns: list[str] | None = None
    result_column: str = Field(default=None, alias="result-column")
    model_config = ConfigDict(extra="forbid")

    def apply_default_values(self, matrix, metrics):
        """Apply default values.
        If `None`, set `columns` to contain all variables from `matrix` section.
        If `None`, set `result_column` to the only metric in `run.metrics` section.

        Raises:
            ValueError: If there are more than one metrics in `run.metrics` section and `result_column` is `None`.

        """
        if self.columns is None:
            self.columns = list(matrix.keys())
        if self.result_column is None:
            if len(metrics) != 1:
                raise ValueError("'result-column' not specified")
            self.result_column = (
                metrics[0] if type(metrics[0]) is str else list(metrics[0].keys())[0]
            )

    def check_vars_exist(self, matrix):
        """Check if columns contain valid variables' names."""
        for column in self.columns:
            check_var_exists(column, matrix)

    def check_metrics_exist(self, metrics):
        super().check_metric_exists(self.result_column, metrics)


def check_var_exists(var_key, matrix):
    if var_key is not None and var_key not in matrix:
        raise ValueError(f"variable '{var_key}' not found")


def check_command_variables(commands, matrix):
    """Check if variables used in commands are present in `matrix` section.

    Args:
        commands: List of commands to be validated.
        matrix: `matrix` section from the configuration file.

    Raises:
        ValueError
    """
    for command in commands:
        variables = findall(VAR_REGEX, command)
        for var in variables:
            var_key = var.removeprefix("{{").removesuffix("}}")
            check_var_exists(var_key, matrix)


class ConfigFile(BaseModel):
    """Schema of the configuration file.

    Attributes:
        matrix: Section containing variables and their values.
        system: Section containing variance reducing, system modifying options.
        run: Section containing commands.
        output: Section containing desired outputs.
    """

    matrix: dict[str, list] = {}
    system: SystemSection = SystemSection()
    run: RunSection
    output: dict[str, CsvOutput | BarChartOutput | TableMdOutput]

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
    def check_command_vars(self):
        """Check whether variables used in commands are present in the `matrix` section."""
        if self.matrix == {}:
            return self
        check_command_variables(self.run.before, self.matrix)
        if type(self.run.benchmark) is dict:
            for name in self.run.benchmark:
                check_command_variables(self.run.benchmark[name], self.matrix)
        else:
            check_command_variables(self.run.benchmark, self.matrix)
        check_command_variables(self.run.after, self.matrix)
        return self

    @model_validator(mode="after")
    def check_output_vars(self):
        """Check whether variables used in outputs are present in the `matrix` section."""
        for output_key in self.output:
            output = self.output[output_key]
            output.check_vars_exist(self.matrix)
        return self

    @model_validator(mode="after")
    def check_output_metrics(self):
        """Check whether metrics used in outputs are present in the `run.metrics` section."""
        for output_key in self.output:
            output = self.output[output_key]
            output.check_metrics_exist(self.run.metrics)
        return self


def validate_config(config) -> dict:
    logger.info("Validating config...")
    try:
        config_validator = ConfigFile(**config)
    except ValidationError as e:
        error_and_exit(e)
    normalized_config = config_validator.model_dump(by_alias=True)
    logger.info("Successfully validated config.")
    logger.debug(normalized_config)
    return normalized_config
