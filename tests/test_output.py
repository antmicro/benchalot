import unittest
import pandas as pd
from benchmarker.output import get_combination_filtered_dfs


class TestOutput(unittest.TestCase):
    def test_combination_filtered_df_comb(self):
        data = pd.DataFrame({"a": [1, 2, 3], "b": [3, 2, 1]})
        comb = []
        for c, row in get_combination_filtered_dfs(data, ["a", "b"]):
            self.assertEqual(c["a"], row["a"].iloc[0])
            self.assertEqual(c["b"], row["b"].iloc[0])
            comb.append(c)
        self.assertEqual(len(comb), 3)
        man_comb = [
            {"a": 1, "b": 3},
            {"a": 2, "b": 2},
            {"a": 3, "b": 1},
        ]
        for mc in man_comb:
            self.assertTrue(any(mc == c for c in comb))

    def test_combination_filtered_df_compound(self):
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
        man_comb = [
            {"v1": {"a": 1, "b": 4}, "v2": {"c": 7, "d": 10}},
            {"v1": {"a": 2, "b": 5}, "v2": {"c": 8, "d": 11}},
            {"v1": {"a": 3, "b": 6}, "v2": {"c": 9, "d": 12}},
        ]
        for mc in man_comb:
            self.assertTrue(any(mc == c for c in comb))
