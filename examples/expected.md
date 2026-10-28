# 自创测试小样的预期结果

全部小样为本工具原创测试数据，仅验证检查行为；不代表正式 HSK 命题、难度鉴定或合格试卷。这里的“结构无异常”只针对本工具检查范围。

| 输入与条件 | 预期机械结果 | 退出码 |
|---|---|---|
| `structure-clear.json`，默认配置 | `CHECKS_CLEAR_REVIEW_REQUIRED`，无 findings；两题字符数依次为 11、10 | 0 |
| `structure-clear.json` + `demo-config.json` | 相同结果，全部演示格式约定满足 | 0 |
| `structure-broken.json`，默认配置 | 7 条发现，见下表 | 2 |
| `semantic-review.json`，默认配置 | `CHECKS_CLEAR_REVIEW_REQUIRED`，无 findings；题干字符数 11 | 0 |

错误小样的预期发现：

| 位置 | 代码 | 原因 |
|---|---|---|
| `options[1].id` | `DUPLICATE_OPTION_ID` | A 编号重复 |
| `options[2].text` | `DUPLICATE_OPTION_TEXT` | 去空白后与第一项均为“提醒” |
| `items[0].answer_id` | `ANSWER_UNKNOWN` | 没有选项 Z |
| `items[0].text` | `BLANK_COUNT` | 没有填空标记 |
| `items[1].id` | `DUPLICATE_ITEM_ID` | T01 题号重复 |
| `items[1].answer_id` | `ANSWER_MISSING` | 参考答案为空 |
| `items[1].text` | `BLANK_COUNT` | 有两个填空标记 |

语义边界小样：将“开心”或“高兴”填回，“收到朋友的来信，她很开心/高兴。”都自然。脚本预期不报语义错误；教师或受托做语言审校的 AI 应提出这两个候选，留待教师决定。此预期由样例设计给出，不代表已完成独立语义效果评测。

所有结果中 `semantic_review` 都应为 `NOT_PERFORMED`，`human_review_required` 都应为 `true`。脚本返回 0 不能写成“审核通过”或“答案唯一”。
