import unittest
from benchmarker.interpolate import interpolate_variables, create_variable_combinations


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


class TestCombinations(unittest.TestCase):

    def test_combination_simple(self):
        matrix = {"a": [1, 2, 3], "b": [1, 2, 3]}
        comb = list(create_variable_combinations(**matrix))
        self.assertEqual(len(comb), 9)
        man_comb = [
            {"a": 1, "b": 1},
            {"a": 1, "b": 2},
            {"a": 1, "b": 3},
            {"a": 2, "b": 1},
            {"a": 2, "b": 2},
            {"a": 2, "b": 3},
            {"a": 3, "b": 1},
            {"a": 3, "b": 2},
            {"a": 3, "b": 3},
        ]
        for mc in man_comb:
            self.assertTrue(any(mc == c for c in comb))

    def test_combination_compound(self):
        matrix = {
            "v1": [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
            "v2": [{"c": 1, "d": 2}, {"c": 3, "d": 4}],
        }
        comb = list(create_variable_combinations(**matrix))
        self.assertEqual(len(comb), 4)
        man_comb = [
            {"v1": {"a": 1, "b": 2}, "v2": {"c": 1, "d": 2}},
            {"v1": {"a": 1, "b": 2}, "v2": {"c": 3, "d": 4}},
            {"v1": {"a": 3, "b": 4}, "v2": {"c": 1, "d": 2}},
            {"v1": {"a": 3, "b": 4}, "v2": {"c": 3, "d": 4}},
        ]
        for mc in man_comb:
            self.assertTrue(any(mc == c for c in comb))
