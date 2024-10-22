from pydantic import BaseModel, ValidationError, ConfigDict, Field, field_validator
from typing import Literal

# from re import findall
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
    governor_performance: bool = Field(default=False, alias="governor-performance")
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

    @field_validator("cwd")
    @classmethod
    def path_exists(cls, value: str):
        if not isdir(value):
            raise ValueError(f"directory '{value}' not found")
        return value


class OutputField(BaseModel):
    filename: str
    format: str


class CsvOutput(OutputField):
    format: Literal["csv"]


class BarChartOutput(OutputField):
    format: Literal["bar-chart"]
    x_axis: str = Field(alias="x-axis")
    y_axis: str = Field(default="time", alias="y-axis")
    facet: str | None = None
    width: int = Field(default=10, ge=1)
    height: int = Field(default=9, ge=1)
    dpi: int = Field(default=100, ge=50)


class TableMdOutput(OutputField):
    format: Literal["table-md"]
    columns: list[str] = []


class ConfigFile(BaseModel):
    matrix: dict[str, list] | None = None
    system: SystemSection | None = None
    run: RunSection
    output: dict[str, CsvOutput | BarChartOutput | TableMdOutput]


def validate_config(config) -> dict:
    try:
        ConfigFile(**config)
    except ValidationError as e:
        error_and_exit(e)
    print("Validation succesful!")
    exit()
