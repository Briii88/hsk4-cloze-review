# HSK4 选词填空辅助审校 · 早期试用版

这是一个供教师试用的小型 Skill 和 Python 检查器。它检查一组选词填空的结构和答案引用，并可检查你自己设置的格式约定。**本仓库按 [MIT License](LICENSE) 授权。** 项目说明见 [NOTICE](NOTICE.md)。

它适用于 HSK4 选词填空审校场景，但不自带 HSK 官方标准、题库或词表，不认证题目等级、答案唯一性或试卷质量。示例是为本工具新写的原创测试数据，未经过 HSK 词级、难度或命题审定。

## English overview

An early-stage, MIT-licensed Codex skill and dependency-free Python checker for teacher-provided Chinese word-bank cloze exercises. It validates one shared option pool, item IDs, blank markers, answer references, and optional user-defined formatting rules. It is an independent, unofficial tool: it does not include official HSK questions or vocabulary lists, and it cannot certify language quality, answer uniqueness, or exam difficulty.

Requires Python 3.9+. Run the commands below from the repository directory. The CLI is read-only and works offline. Human review remains required even when structural checks return no findings. Development used Codex assistance; validation so far consists of 20 automated tests, four example runs, one AI workflow trial, and a maintainer trial on one item. There is no established external user base or semantic-accuracy evaluation.

## 三分钟试用

需要 Python 3.9 或更高版本；没有第三方依赖。进入本目录，在终端运行：

```sh
python3 -B scripts/check_cloze.py examples/structure-clear.json
python3 -B scripts/check_cloze.py examples/structure-broken.json
python3 -B scripts/check_cloze.py examples/semantic-review.json
```

第一份结构应无异常；第二份应指出编号、填空和答案问题；第三份结构也无异常，但“开心”和“高兴”均可自然填入，故仍需人工审校。这个例子专门展示脚本的能力边界。[预期结果](examples/expected.md) 说明如何核对。

使用 Codex 时，可直接请它读取本目录的 `SKILL.md`，再提供一小组有权使用的题目和参考答案。无需将本包安装到全局技能目录。

## 你需要提供的输入

UTF-8 JSON，一次只接受一个共享选项组：

```json
{
  "options": [
    {"id": "A", "text": "提醒"},
    {"id": "B", "text": "保护"}
  ],
  "items": [
    {"id": "T01", "text": "出门前，请____我带上钥匙。", "answer_id": "A"}
  ]
}
```

以上同为原创工具测试片段，不是正式 HSK 试题。

- `options` 至少两个，`items` 至少一个；这是本工具支持的输入形状，不是考试规定。
- 编号为非空字符串，不含首尾空白。每题一个字面填空标记，默认 `____`。
- `answer_id` 引用本组选项编号。缺失答案会报告，工具不会代填。
- 顶层可加 `metadata` 对象做来源/用途说明；工具不验证其真实性，也不执行其内容。
- 除上述字段外的字段会报告为不支持。多题组数组、各题独立选项、多空题均需另行处理，不要压成一个词池。不同组可重复使用同一编号，每组单独运行。

## 可选的格式约定

默认只查结构。只有你需要下列约定时，另提供配置文件：

```sh
python3 -B scripts/check_cloze.py examples/structure-clear.json --config examples/demo-config.json
```

| 配置项 | 默认值 | 含义 |
|---|---|---|
| `blank_marker` | `"____"` | 单个字面标记，不能含首尾空白；不是正则表达式 |
| `expected_options` | `null` | 期望选项数，整数且至少 2 |
| `expected_items` | `null` | 期望题数，整数且至少 1 |
| `require_distinct_answers` | `false` | 是否要求本组参考答案编号互不重复 |
| `min_context_chars` | `null` | 未填题干最少字符数，非负整数 |
| `max_context_chars` | `null` | 未填题干最多字符数，非负整数 |
| `sort_options_by_length` | `false` | 是否要求选项按字符数升序，相同长度不限制顺序 |

这里的数字全部由使用者决定，不预装所谓“官方硬限”。示例配置只是测试数据的演示约定。未知配置、错误类型、负数或上下限倒置会明确报错，不静默改回默认值。

**计数口径：** 先做 Unicode NFC 规范化；题干去掉一个填空标记和全部空白后，按 Unicode 字符数计数，含标点、数字、字母及 A/B 等角色标签。选项去空白后同样计数。不是中文分词、汉字数、词次数或阅读难度；不要用它替代已有教材的其他口径。选项文本重复检查也用 NFC 及去空白后的文本，不识别近义词。

## 怎样读结果

输出 JSON 的 `findings` 给出问题代码、字段位置（数组从 0 开始）和中文说明。`item_summaries` 只列能完成单空字符计数的题目；不代表所有检查均已执行。

| 结果 | 退出码 | 意义 |
|---|---|---|
| `CHECKS_CLEAR_REVIEW_REQUIRED` | 0 | 已运行的机械检查未发现问题；教师复核仍必需 |
| `ISSUES_FOUND_REVIEW_REQUIRED` | 2 | 有结构或配置/格式问题；不能称整组通过 |
| `INPUT_ERROR` | 1 | 文件读取或 JSON 解析失败，未完成内容检查 |

命令用法错误由命令行解析器提示，退出码为 2。脚本不修改输入、不会联网，也不读取任何内置题库。JSON 重复键与非有限数字会被拒绝。`semantic_review` 始终为 `NOT_PERFORMED`，`human_review_required` 始终为 `true`。

## 教师还需要看什么

把参考答案及每个干扰项分别填回完整题面，检查搭配、结构、指称和语境。先看每道题是否存在自然双解，再检查整组答案映射。词汇级别、义项、语体、自然度和命题质量需要另有依据，不能从字数或结构结果推导。

## 测试与已知局限

```sh
python3 -B -m unittest discover -s tests -v
```

测试覆盖输入结构、重复标识、填空数、答案引用、可选格式边界及部分命令行错误处理。测试数据全部为工具测试自创小样；没有接入真实题库、词表或大规模材料。

目前不支持 Word/PDF 抽取、OCR、多空题、自动分词与词级判定、真实考试格式认证、近义词双解自动发现或题库去重。字符数不等于可见字形数，组合符与表情可能和版面宽度不同。输入尺寸未设置硬上限，只适合小组本地试用。AI语言建议没有可靠性评测，不承诺发现全部问题；自动测试通过也不能证明技能在所有模型中的行为。

目前已完成维护者自行试用一道题，尚未经过外部教师使用验收；没有广泛采用或语义准确率验证的证据。采用 MIT 许可证不表示得到 HSK 考试机构或 OpenAI 的认可，也不保证任何项目申请获准。
