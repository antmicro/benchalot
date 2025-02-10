import unittest
import pandas as pd
from benchmarker.interpolate import interpolate_variables, create_variable_combinations
from benchmarker.output import get_combination_filtered_dfs


class TestInterpoleVariables(unittest.TestCase):
    def test_single_var(self):
        command = "echo {{name}}"
        interpolated_command = interpolate_variables(command, {"name": "value"})
        self.assertEqual("echo value", interpolated_command)

    def test_multiple_vars(self):
        command = "echo {{name1}} {{name2}}"
        interpolated_command = interpolate_variables(
            command, {"name1": "value1", "name2": "value2"}
        )
        self.assertEqual("echo value1 value2", interpolated_command)

    def test_compund_var(self):
        command = "echo {{name.field1}} {{name.field2}}"
        matrix = {"name": {"field1": "value1", "field2": "value2"}}
        interpolated_command = interpolate_variables(command, matrix)
        self.assertEqual("echo value1 value2", interpolated_command)

    def test_compund_var_complex(self):
        command = "echo {{name.field.field}} {{name2}}"
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


class TestCreateVariableCombinations(unittest.TestCase):

    def test_combination_simple(self):
        matrix = {"a": [1, 2, 3], "b": [1, 2, 3]}
        comb = list(create_variable_combinations(**matrix))
        self.assertEqual(len(comb), 9)
        target_comb = [
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
        self.assertEqual(target_comb, list(comb))

    def test_combination_compound(self):
        matrix = {
            "v1": [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
            "v2": [{"c": 1, "d": 2}, {"c": 3, "d": 4}],
        }
        comb = list(create_variable_combinations(**matrix))
        self.assertEqual(len(comb), 4)
        target_comb = [
            {"v1": {"a": 1, "b": 2}, "v2": {"c": 1, "d": 2}},
            {"v1": {"a": 1, "b": 2}, "v2": {"c": 3, "d": 4}},
            {"v1": {"a": 3, "b": 4}, "v2": {"c": 1, "d": 2}},
            {"v1": {"a": 3, "b": 4}, "v2": {"c": 3, "d": 4}},
        ]
        self.assertEqual(target_comb, list(comb))


class TestCombinationFilteredDf(unittest.TestCase):
    def test_simple_comb(self):
        data = pd.DataFrame({"a": [1, 2, 3], "b": [3, 2, 1]})
        comb = []
        for c, row in get_combination_filtered_dfs(data, ["a", "b"]):
            self.assertEqual(c["a"], row["a"].iloc[0])
            self.assertEqual(c["b"], row["b"].iloc[0])
            comb.append(c)
        self.assertEqual(len(comb), 3)
        target_comb = [
            {"a": 1, "b": 3},
            {"a": 2, "b": 2},
            {"a": 3, "b": 1},
        ]
        self.assertEqual(target_comb, list(comb))

    def test_compound_comb(self):
        data = pd.DataFrame(
            {
                "v1.a": [1, 2, 3],
                "v1.b": [4, 5, 6],
                "v2.c": [7, 8, 9],
                "v2.d": [10, 11, 12],
            }
        )
        comb = []
        for c, row in get_combination_filtered_dfs(
            data, ["v1.a", "v1.b", "v2.c", "v2.d"]
        ):
            self.assertEqual(c["v1"]["a"], row["v1.a"].iloc[0])
            self.assertEqual(c["v1"]["b"], row["v1.b"].iloc[0])
            self.assertEqual(c["v2"]["c"], row["v2.c"].iloc[0])
            self.assertEqual(c["v2"]["d"], row["v2.d"].iloc[0])
            comb.append(c)
        self.assertEqual(len(comb), 3)
        target_comb = [
            {"v1": {"a": 1, "b": 4}, "v2": {"c": 7, "d": 10}},
            {"v1": {"a": 2, "b": 5}, "v2": {"c": 8, "d": 11}},
            {"v1": {"a": 3, "b": 6}, "v2": {"c": 9, "d": 12}},
        ]
        self.assertEqual(target_comb, list(comb))
