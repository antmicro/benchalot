from pydantic import BaseModel, ValidationError, ConfigDict, Field, field_validator, model_validator
from typing import Literal
from re import findall
from logging import getLogger
from os import getcwd
from os.path import isdir

logger = getLogger(f"benchmarker.{__name__}")


def error_and_exit(error):
    logger.critical("Config validation failed.")
    logger.critical(error)
    exit(1)


class SystemSection(BaseModel):
    isolate_cpus: list[int] = Field(default=None, alias="isolate-cpus")
    disable_aslr: bool = Field(default=False, alias="disable-aslr")
    governor_performance: bool = Field(
        default=False, alias="governor-performance")
    model_config = ConfigDict(extra="forbid")


class RunSection(BaseModel):
    samples: int = 1
    save_output: str = Field(default=None, alias="save-output")
    before_all: list[str] = Field(default=[], alias="before-all")
    before: list[str] = []
    benchmark: list[str]
    after: list[str] = []
    after_all: list[str] = Field(default=[], alias="after-all")
    cwd: str = getcwd()
    metrics: list[str | dict] = ["time"]
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
        return metric


class OutputField(BaseModel):
    filename: str
    format: str

    def apply_default_values(self, matrix, metrics):
        pass

    def check_vars_exist(self, matrix):
        pass

    def check_metric_exists(self, metric_name, metrics):
        metric_names = [name if type(name) is str else list(
            name.keys())[0] for name in metrics]
        if metric_name not in metric_names:
            raise ValueError(f"metric '{metric_name}' not found")

    def check_metrics_exist(self, metrics):
        pass


class CsvOutput(OutputField):
    format: Literal["csv"]
    model_config = ConfigDict(extra="forbid")


class BarChartOutput(OutputField):
    format: Literal["bar-chart"]
    x_axis: str = Field(alias="x-axis")
    y_axis: str = Field(default=None, alias="y-axis")
    facet: str | None = None
    color: str | None = None
    width: int = Field(default=10, ge=1)
    height: int = Field(default=9, ge=1)
    dpi: int = Field(default=100, ge=50)
    model_config = ConfigDict(extra="forbid")

    def apply_default_values(self, matrix, metrics):
        if self.y_axis is None:
            self.y_axis = metrics[0] if type(
                metrics[0]) is str else list(metrics[0].keys())[0]

    def check_vars_exist(self, matrix):
        check_var_exists(self.facet, matrix)
        check_var_exists(self.x_axis, matrix)
        check_var_exists(self.color, matrix)

    def check_metrics_exist(self, metrics):
        super().check_metric_exists(self.y_axis, metrics)


class TableMdOutput(OutputField):
    format: Literal["table-md"]
    columns: list[str] | None = None
    result_column: str = Field(default=None, alias="result-column")
    model_config = ConfigDict(extra="forbid")

    def apply_default_values(self, matrix, metrics):
        if self.columns is None:
            self.columns = list(matrix.keys())
        if self.result_column is None:
            self.result_column = metrics[0] if type(
                metrics[0]) is str else list(metrics[0].keys())[0]

    def check_vars_exist(self, matrix):
        for column in self.columns:
            check_var_exists(column, matrix)

    def check_metrics_exist(self, metrics):
        super().check_metric_exists(self.result_column, metrics)


def check_var_exists(var_key, matrix):
    if var_key is not None and var_key not in matrix:
        raise ValueError(f"variable '{var_key}' not found")


def check_command_variables(commands, matrix):
    for command in commands:
        variables = findall(r"\$matrix\.[a-zA-Z0-9]*", command)
        for var in variables:
            var_key = var.split(".")[1]
            check_var_exists(var_key, matrix)


class ConfigFile(BaseModel):
    matrix: dict[str, list] = {}
    system: SystemSection | None = None
    run: RunSection
    output: dict[str, CsvOutput | BarChartOutput | TableMdOutput]

    @model_validator(mode="after")
    def apply_default_values(self):
        for output_key in self.output:
            output = self.output[output_key]
            output.apply_default_values(self.matrix, self.run.metrics)
        return self

    @model_validator(mode='after')
    def check_command_vars(self):
        if self.matrix == {}:
            return self
        check_command_variables(self.run.before, self.matrix)
        check_command_variables(self.run.benchmark, self.matrix)
        check_command_variables(self.run.after, self.matrix)
        return self

    @model_validator(mode='after')
    def check_output_vars(self):
        for output_key in self.output:
            output = self.output[output_key]
            output.check_vars_exist(self.matrix)
        return self

    @model_validator(mode='after')
    def check_output_metrics(self):
        for output_key in self.output:
            output = self.output[output_key]
            output.check_metrics_exist(self.run.metrics)
        return self


def validate_config(config) -> dict:
    try:
        ConfigFile(**config)
    except ValidationError as e:
        error_and_exit(e)
    print("Validation succesful!")
    exit()
