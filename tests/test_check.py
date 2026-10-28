"""原创工具测试数据；不代表正式 HSK 命题、难度鉴定或合格试卷。

在候选包目录运行：python3 -B -m unittest discover -s tests -v
仅使用 Python 标准库，不读取题库、词表或其他项目资料。
"""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE_ROOT / "scripts" / "check_cloze.py"
SPEC = importlib.util.spec_from_file_location("check_cloze", SCRIPT)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def sample():
    """Small invented fixture, used only to exercise the checker."""
    return {
        "metadata": {"purpose": "原创工具测试，非正式试题"},
        "options": [
            {"id": "A", "text": "继续"},
            {"id": "B", "text": "改变"},
            {"id": "C", "text": "暂时"},
        ],
        "items": [
            {"id": "Q1", "text": "雨停了，我们____走吧。", "answer_id": "A"},
            {"id": "Q2", "text": "我____住在这里。", "answer_id": "C"},
        ],
    }


class CheckClozeTests(unittest.TestCase):
    def assert_review_contract(self, result):
        self.assertEqual(result["semantic_review"], "NOT_PERFORMED")
        self.assertIs(result["human_review_required"], True)
        self.assertIsInstance(result["findings"], list)
        self.assertIn("item_summaries", result)
        for finding in result["findings"]:
            for field in ("code", "location", "message"):
                self.assertIsInstance(finding[field], str)
                self.assertTrue(finding[field])

    def assert_clear(self, result):
        self.assert_review_contract(result)
        self.assertEqual(result["status"], "CHECKS_CLEAR_REVIEW_REQUIRED")
        self.assertEqual(result["findings"], [])

    def assert_issue(self, result, code=None):
        self.assert_review_contract(result)
        self.assertEqual(result["status"], "ISSUES_FOUND_REVIEW_REQUIRED")
        self.assertTrue(result["findings"])
        if code is not None:
            self.assertIn(code, {finding["code"] for finding in result["findings"]})

    def test_01_valid_input_and_optional_rules_disabled(self):
        data = sample()
        data["options"][0]["text"] = "长度不同的测试选项"
        data["items"][1]["answer_id"] = "A"
        self.assert_clear(CHECKER.validate(data))
        self.assert_clear(CHECKER.validate(data, {}))

    def test_02_missing_fields_wrong_types_and_minimum_sizes(self):
        cases = [None, [], "text", {}, {"options": [], "items": []}]
        for key, value in (("options", None), ("options", {}),
                           ("items", "text"), ("items", [None])):
            data = sample()
            data[key] = value
            cases.append(data)
        for key, value in (("options", [{"id": "A", "text": "甲"}]),
                           ("items", [])):
            data = sample()
            data[key] = value
            cases.append(data)
        for group, field, value in (("options", "text", " \n\t"),
                                    ("options", "text", 7),
                                    ("items", "text", ""),
                                    ("items", "text", [])):
            data = sample()
            data[group][0][field] = value
            cases.append(data)
        for index, data in enumerate(cases):
            with self.subTest(case=index):
                self.assert_issue(CHECKER.validate(data), "INPUT_SCHEMA")

    def test_03_metadata_is_optional_and_must_be_object(self):
        data = sample()
        del data["metadata"]
        self.assert_clear(CHECKER.validate(data))
        data["metadata"] = {"local_note": "工具测试"}
        self.assert_clear(CHECKER.validate(data))
        data["metadata"] = "工具测试"
        self.assert_issue(CHECKER.validate(data), "INPUT_SCHEMA")

    def test_04_unknown_fields_are_reported_at_each_supported_level(self):
        for level in ("root", "options", "items"):
            with self.subTest(level=level):
                data = sample()
                target = data if level == "root" else data[level][0]
                target["unexpected"] = "工具测试"
                self.assert_issue(CHECKER.validate(data), "UNSUPPORTED_FIELD")

    def test_05_identifiers_must_be_nonempty_trimmed_strings(self):
        for group in ("options", "items"):
            for value in ("", " ", " A", "A\n", 1, None):
                with self.subTest(group=group, value=value):
                    data = sample()
                    data[group][0]["id"] = value
                    self.assert_issue(CHECKER.validate(data), "INPUT_SCHEMA")

    def test_06_duplicate_option_and_item_identifiers(self):
        for group, code in (("options", "DUPLICATE_OPTION_ID"),
                            ("items", "DUPLICATE_ITEM_ID")):
            with self.subTest(group=group):
                data = sample()
                data[group][1]["id"] = data[group][0]["id"]
                self.assert_issue(CHECKER.validate(data), code)

    def test_07_duplicate_option_text_ignores_whitespace_and_normalizes_nfc(self):
        for left, right in (("甲 乙", "\t甲\n乙\u3000"),
                            ("caf\u00e9", "cafe\u0301")):
            with self.subTest(left=left, right=right):
                data = sample()
                data["options"][0]["text"] = left
                data["options"][1]["text"] = right
                self.assert_issue(CHECKER.validate(data), "DUPLICATE_OPTION_TEXT")

    def test_08_exactly_one_default_blank_is_required(self):
        for text in ("这里没有标记。", "____和____都是测试。"):
            with self.subTest(text=text):
                data = sample()
                data["items"][0]["text"] = text
                self.assert_issue(CHECKER.validate(data))

    def test_09_answer_missing_is_distinguished_from_unknown(self):
        data = sample()
        del data["items"][0]["answer_id"]
        result = CHECKER.validate(data)
        self.assert_issue(result, "ANSWER_MISSING")
        self.assertNotIn("ANSWER_UNKNOWN", {f["code"] for f in result["findings"]})

    def test_10_answer_must_reference_this_option_group(self):
        data = sample()
        data["items"][0]["answer_id"] = "NOT_IN_THIS_GROUP"
        self.assert_issue(CHECKER.validate(data), "ANSWER_UNKNOWN")

    def test_11_configured_counts_and_nullable_limits(self):
        self.assert_clear(CHECKER.validate(sample(), {
            "expected_options": 3, "expected_items": 2,
            "min_context_chars": None, "max_context_chars": None,
        }))
        self.assert_clear(CHECKER.validate(sample(), {
            "expected_options": None, "expected_items": None,
        }))
        for config, code in (({"expected_options": 2}, "OPTION_COUNT"),
                             ({"expected_items": 1}, "ITEM_COUNT")):
            with self.subTest(config=config):
                self.assert_issue(CHECKER.validate(sample(), config), code)

    def test_12_answer_reuse_is_checked_only_when_requested(self):
        data = sample()
        data["items"][1]["answer_id"] = "A"
        self.assert_clear(CHECKER.validate(data, {"require_distinct_answers": False}))
        self.assert_issue(CHECKER.validate(data, {"require_distinct_answers": True}),
                          "ANSWER_REUSED")

    def test_13_context_length_counts_punctuation_and_roles_but_not_blank_or_spaces(self):
        data = sample()
        data["items"] = [{"id": "Q1", "text": "甲： ____ ，\n乙。", "answer_id": "A"}]
        self.assert_clear(CHECKER.validate(data, {"min_context_chars": 5,
                                                 "max_context_chars": 5}))
        self.assert_issue(CHECKER.validate(data, {"min_context_chars": 6}),
                          "CONTEXT_TOO_SHORT")
        self.assert_issue(CHECKER.validate(data, {"max_context_chars": 4}),
                          "CONTEXT_TOO_LONG")

    def test_14_length_sort_uses_whitespace_stripped_option_text(self):
        data = sample()
        for option, text in zip(data["options"], ("甲 乙", "丙", "丁戊己")):
            option["text"] = text
        self.assert_clear(CHECKER.validate(data, {"sort_options_by_length": False}))
        self.assert_issue(CHECKER.validate(data, {"sort_options_by_length": True}),
                          "OPTIONS_NOT_LENGTH_SORTED")
        data["options"] = [data["options"][1], data["options"][0], data["options"][2]]
        self.assert_clear(CHECKER.validate(data, {"sort_options_by_length": True}))

    def test_15_custom_blank_marker_is_literal_and_counted_once(self):
        data = sample()
        for item in data["items"]:
            item["text"] = item["text"].replace("____", "[.*]")
        self.assert_clear(CHECKER.validate(data, {"blank_marker": "[.*]"}))
        self.assert_issue(CHECKER.validate(data))
        data["items"][0]["text"] += "[.*]"
        self.assert_issue(CHECKER.validate(data, {"blank_marker": "[.*]"}))

    def test_16_invalid_configuration_stops_input_checks(self):
        cases = [[], "bad", {"unknown_rule": True},
                 {"blank_marker": ""}, {"blank_marker": " \t"},
                 {"blank_marker": None}, {"require_distinct_answers": 1},
                 {"sort_options_by_length": "true"},
                 {"min_context_chars": 10, "max_context_chars": 5}]
        for key, values in (("expected_options", (True, False, 1, 2.5, "3")),
                            ("expected_items", (True, 0, -1)),
                            ("min_context_chars", (True, -1, 1.5)),
                            ("max_context_chars", (False, -1, "5"))):
            cases.extend({key: value} for value in values)
        for config in cases:
            with self.subTest(config=config):
                result = CHECKER.validate({}, config)
                self.assert_issue(result, "CONFIG_INVALID")
                self.assertEqual({f["code"] for f in result["findings"]},
                                 {"CONFIG_INVALID"})

    def test_17_validation_does_not_mutate_input_or_configuration(self):
        data = sample()
        data["options"][0]["text"] = " 继 续 "
        config = {"expected_options": 3, "min_context_chars": 0}
        before_data, before_config = copy.deepcopy(data), copy.deepcopy(config)
        self.assert_clear(CHECKER.validate(data, config))
        self.assertEqual(data, before_data)
        self.assertEqual(config, before_config)

    def run_cli(self, input_text, config_text=None, missing_input=False):
        with tempfile.TemporaryDirectory(prefix="cloze-test-") as directory:
            root = Path(directory)
            input_path = root / "input.json"
            if not missing_input:
                input_path.write_text(input_text, encoding="utf-8")
            command = [sys.executable, "-B", str(SCRIPT), str(input_path)]
            if config_text is not None:
                config_path = root / "config.json"
                config_path.write_text(config_text, encoding="utf-8")
                command.extend(["--config", str(config_path)])
            completed = subprocess.run(command, capture_output=True, text=True,
                                       encoding="utf-8", timeout=15, check=False)
            self.assertNotIn(str(root), completed.stdout + completed.stderr)
            self.assertNotIn("Traceback", completed.stdout + completed.stderr)
            return completed.returncode, json.loads(completed.stdout)

    def test_18_cli_returns_json_and_expected_exit_status_for_validation(self):
        code, result = self.run_cli(json.dumps(sample(), ensure_ascii=False))
        self.assertEqual(code, 0)
        self.assert_clear(result)
        data = sample()
        data["items"][0]["answer_id"] = "unknown"
        code, result = self.run_cli(json.dumps(data, ensure_ascii=False))
        self.assertEqual(code, 2)
        self.assert_issue(result, "ANSWER_UNKNOWN")

    def test_19_cli_rejects_unreadable_bad_json_and_duplicate_json_keys(self):
        cases = [('{"options":', False), ("", True),
                 ('{"options": [], "options": [], "items": []}', False),
                 ('{"options": [{"id": "A", "id": "B", "text": "甲"}], "items": []}', False)]
        for text, missing in cases:
            with self.subTest(text=text, missing=missing):
                code, result = self.run_cli(text, missing_input=missing)
                self.assertEqual(code, 1)
                self.assertEqual(result["status"], "INPUT_ERROR")

    def test_20_cli_applies_config_and_handles_invalid_config_files(self):
        source = json.dumps(sample(), ensure_ascii=False)
        code, result = self.run_cli(source, '{"expected_options": 2}')
        self.assertEqual(code, 2)
        self.assert_issue(result, "OPTION_COUNT")
        for config in ('{"expected_options":',
                       '{"expected_options": 2, "expected_options": 3}'):
            with self.subTest(config=config):
                code, result = self.run_cli(source, config)
                self.assertEqual(code, 1)
                self.assertEqual(result["status"], "INPUT_ERROR")


if __name__ == "__main__":
    unittest.main()
