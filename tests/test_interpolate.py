import unittest
from benchmarker.interpolate import interpolate_variables


def format_name(var_name: str):
    return "{{" + var_name + "}}"


class TestInterpolation(unittest.TestCase):
    def test_single_var(self):
        var_name = format_name("name")
        command = f"echo {var_name}"
        interpolated_command = interpolate_variables(command, {"name": "value"})
        self.assertEqual("echo value", interpolated_command)

    def test_multiple_vars(self):
        var_name1 = format_name("name1")
        var_name2 = format_name("name2")
        command = f"echo {var_name1} {var_name2}"
        interpolated_command = interpolate_variables(
            command, {"name1": "value1", "name2": "value2"}
        )
        self.assertEqual("echo value1 value2", interpolated_command)

    def test_compund_var(self):
        var_name1 = format_name("name.field1")
        var_name2 = format_name("name.field2")
        command = f"echo {var_name1} {var_name2}"
        matrix = {"name": {"field1": "value1", "field2": "value2"}}
        interpolated_command = interpolate_variables(command, matrix)
        self.assertEqual("echo value1 value2", interpolated_command)

    def test_compund_var_complex(self):
        var_name1 = format_name("name.field.field")
        var_name2 = format_name("name2")
        command = f"echo {var_name1} {var_name2}"
        matrix = {
            "name": {
                "field": {"field": "value1"},
            },
            "name2": "value2",
        }
        interpolated_command = interpolate_variables(command, matrix)
        self.assertEqual("echo value1 value2", interpolated_command)

    def test_existence_simple(self):
        with self.assertRaises(SystemExit) as cm:
            interpolate_variables("command {{test}}", {})
        self.assertEqual(cm.exception.code, 1)

    def test_existence_complex(self):
        with self.assertRaises(SystemExit) as cm:
            interpolate_variables("command {{test.field.v}}", {"test": {"field": "v"}})
        self.assertEqual(cm.exception.code, 1)
