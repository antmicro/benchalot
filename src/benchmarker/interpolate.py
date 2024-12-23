from itertools import product
from re import sub
from logging import getLogger

logger = getLogger(f"benchmarker.{__name__}")
VAR_REGEX = r"{{([a-zA-Z0-9_\-.]+)}}"


def create_variable_combinations(**kwargs):
    """Create all possible variable values combinations

    Args:
        kwargs: Dictionary containing list of variable values.
    """
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


def interpolate_variables(string: str, variables: dict[str, str | int]) -> str:
    """Replace variable references with values.

    Args:
        string: String to be modified.
        variables: Variable names paired with values.

    Returns:
        str: String with all variable references replaced.
    """

    def replace_substring(match):
        variable_name = match.group(1)
        compound = variable_name.split(".")
        if len(compound) == 2:
            try:
                return str(variables[compound[0]][compound[1]])
            except KeyError:
                logger.critical(f"'{string}': Variable '{variable_name}' not found")
                exit(1)
        else:
            try:
                return str(variables[compound[0]])
            except KeyError:
                logger.critical(f"'{string}': Variable '{variable_name}' not found")
                exit(1)

    new_string = sub(VAR_REGEX, replace_substring, string)
    return new_string
