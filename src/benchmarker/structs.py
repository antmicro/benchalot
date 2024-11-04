from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Benchmark:
    matrix: dict[str, str]
    before: list[str]
    benchmark: dict[str, list[str]]
    after: list[str]
    metrics: list[Callable[[dict], dict]]
