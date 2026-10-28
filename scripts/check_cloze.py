#!/usr/bin/env python3
"""单组选词填空的只读结构检查；不进行语义、词级或命题质量认证。"""
import argparse
import json
from pathlib import Path
import sys
import unicodedata


DEFAULTS = {
    "blank_marker": "____",
    "expected_options": None,
    "expected_items": None,
    "require_distinct_answers": False,
    "min_context_chars": None,
    "max_context_chars": None,
    "sort_options_by_length": False,
}


def compact(text):
    return "".join(c for c in unicodedata.normalize("NFC", text) if not c.isspace())


def validate(data, config=None):
    findings = []
    summaries = []

    def add(code, location, message):
        findings.append(dict(code=code, location=location, message=message))

    def result():
        return {
            "status": "ISSUES_FOUND_REVIEW_REQUIRED" if findings else "CHECKS_CLEAR_REVIEW_REQUIRED",
            "findings": findings,
            "item_summaries": summaries,
            "semantic_review": "NOT_PERFORMED",
            "human_review_required": True,
            "note": "本结果仅覆盖结构及已启用的使用者格式约定；答案唯一性、语言自然度与词级未检查。",
        }

    rules = dict(DEFAULTS)
    if config is not None:
        if not isinstance(config, dict):
            add("CONFIG_INVALID", "config", "配置必须是对象。")
            return result()
        for key, value in config.items():
            if key not in DEFAULTS:
                add("CONFIG_INVALID", "config." + str(key), "未知配置项。")
                continue
            rules[key] = value
    marker = rules["blank_marker"]
    if not isinstance(marker, str) or not marker.strip() or marker != marker.strip():
        add("CONFIG_INVALID", "config.blank_marker", "标记须为非空字符串，不能含首尾空白。")
    for key in ("require_distinct_answers", "sort_options_by_length"):
        if type(rules[key]) is not bool:
            add("CONFIG_INVALID", "config." + key, "必须是布尔值。")
    for key, minimum in (("expected_options", 2), ("expected_items", 1),
                         ("min_context_chars", 0), ("max_context_chars", 0)):
        value = rules[key]
        if value is not None and (type(value) is not int or value < minimum):
            add("CONFIG_INVALID", "config." + key, "必须是 null 或不小于 %s 的整数。" % minimum)
    low, high = rules["min_context_chars"], rules["max_context_chars"]
    if type(low) is int and type(high) is int and low > high:
        add("CONFIG_INVALID", "config", "最小篇幅不能大于最大篇幅。")
    if findings:
        return result()

    def unknown_fields(obj, allowed, location):
        for key in obj:
            if key not in allowed:
                add("UNSUPPORTED_FIELD", location + "." + str(key), "此字段不受本版支持；没有据此进行检查。")

    def text_field(obj, key, location, identifier=False):
        value = obj.get(key)
        if not isinstance(value, str) or not value.strip() or (identifier and value != value.strip()):
            add("INPUT_SCHEMA", location + "." + key, "须为非空字符串；编号不得含首尾空白。")
            return None
        return value

    if not isinstance(data, dict):
        add("INPUT_SCHEMA", "input", "输入必须是一个共享选项组对象；不支持题组数组。")
        return result()
    unknown_fields(data, {"metadata", "options", "items"}, "input")
    if "metadata" in data and not isinstance(data["metadata"], dict):
        add("INPUT_SCHEMA", "metadata", "metadata 如提供，必须是对象；其内容不作真实性验证。")
    options, items = data.get("options"), data.get("items")
    if not isinstance(options, list) or len(options) < 2:
        add("INPUT_SCHEMA", "options", "本工具要求一个至少含两个选项的数组。")
    if not isinstance(items, list) or not items:
        add("INPUT_SCHEMA", "items", "本工具要求至少一道题的数组。")
    if not isinstance(options, list) or not isinstance(items, list):
        return result()
    for key, rows, code in (("expected_options", options, "OPTION_COUNT"),
                            ("expected_items", items, "ITEM_COUNT")):
        if rules[key] is not None and len(rows) != rules[key]:
            add(code, "options" if key == "expected_options" else "items",
                "数量 %s 与使用者配置 %s 不符。" % (len(rows), rules[key]))

    option_map, seen_text, lengths = {}, {}, []
    ambiguous_ids = set()
    for index, option in enumerate(options):
        loc = "options[%s]" % index
        if not isinstance(option, dict):
            add("INPUT_SCHEMA", loc, "每个选项须为对象。")
            continue
        unknown_fields(option, {"id", "text"}, loc)
        option_id = text_field(option, "id", loc, identifier=True)
        text = text_field(option, "text", loc)
        if option_id is not None:
            if option_id in option_map:
                add("DUPLICATE_OPTION_ID", loc + ".id", "选项编号重复。")
                ambiguous_ids.add(option_id)
            else:
                option_map[option_id] = text
        if text is not None:
            normalized = compact(text)
            lengths.append(len(normalized))
            if normalized in seen_text:
                add("DUPLICATE_OPTION_TEXT", loc + ".text", "去除空白并作 NFC 规范化后，选项文字与 %s 重复。" % seen_text[normalized])
            else:
                seen_text[normalized] = loc
    if rules["sort_options_by_length"] and len(lengths) == len(options) and lengths != sorted(lengths):
        add("OPTIONS_NOT_LENGTH_SORTED", "options", "选项未按使用者指定的字符数升序排列；不自动重排答案。")

    seen_items, used_answers = set(), set()
    for index, item in enumerate(items):
        loc = "items[%s]" % index
        if not isinstance(item, dict):
            add("INPUT_SCHEMA", loc, "每题须为对象。")
            continue
        unknown_fields(item, {"id", "text", "answer_id"}, loc)
        item_id = text_field(item, "id", loc, identifier=True)
        text = text_field(item, "text", loc)
        if item_id is not None:
            if item_id in seen_items:
                add("DUPLICATE_ITEM_ID", loc + ".id", "题号重复。")
            seen_items.add(item_id)
        answer = item.get("answer_id")
        if answer is None or (isinstance(answer, str) and not answer.strip()):
            add("ANSWER_MISSING", loc + ".answer_id", "未提供参考答案，无法核对答案引用。")
        elif not isinstance(answer, str) or answer != answer.strip():
            add("INPUT_SCHEMA", loc + ".answer_id", "参考答案须为无首尾空白的选项编号字符串。")
        elif answer not in option_map:
            add("ANSWER_UNKNOWN", loc + ".answer_id", "参考答案引用的选项不存在。")
        elif answer in ambiguous_ids or option_map[answer] is None:
            add("ANSWER_OPTION_INVALID", loc + ".answer_id", "答案指向重复编号或无效选项，无法可靠回填。")
        else:
            if rules["require_distinct_answers"] and answer in used_answers:
                add("ANSWER_REUSED", loc + ".answer_id", "与本组前题共用答案，违反使用者启用的答案不重复约定。")
            used_answers.add(answer)
        if text is not None:
            count = text.count(marker)
            if count != 1:
                add("BLANK_COUNT", loc + ".text", "本工具每题要求一个字面填空标记；实际找到 %s 个。" % count)
                continue
            # 此口径独立于任何教材：未填题干，去标记/空白，标点及角色标签照计。
            length = len(compact(text.replace(marker, "")))
            summaries.append({"location": loc, "item_id": item_id, "context_chars": length})
            if low is not None and length < low:
                add("CONTEXT_TOO_SHORT", loc + ".text", "未填题干字符数 %s 小于使用者配置 %s。" % (length, low))
            if high is not None and length > high:
                add("CONTEXT_TOO_LONG", loc + ".text", "未填题干字符数 %s 大于使用者配置 %s。" % (length, high))
    return result()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("重复的 JSON 字段")
        result[key] = value
    return result


def read_json(path):
    def reject_constant(_):
        raise ValueError("不支持非有限 JSON 数字")
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=unique_object, parse_constant=reject_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="UTF-8 JSON 单个题组文件")
    parser.add_argument("--config", help="可选格式配置 JSON")
    args = parser.parse_args(argv)
    stage = "input"
    try:
        data = read_json(args.input)
        stage = "config"
        config = read_json(args.config) if args.config else None
        # CLI 明确提供 null 文件不等于没有配置。
        if args.config and config is None:
            config = []
        report = validate(data, config)
        code = 2 if report["findings"] else 0
    except (OSError, UnicodeError, ValueError, RecursionError):
        report = {
            "status": "INPUT_ERROR",
            "findings": [{"code": "FILE_OR_JSON_ERROR", "location": stage,
                          "message": "文件无法读取，或不是有效 UTF-8 JSON（拒绝重复键及非有限数字）。"}],
            "item_summaries": [], "semantic_review": "NOT_PERFORMED",
            "human_review_required": True,
        }
        code = 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
