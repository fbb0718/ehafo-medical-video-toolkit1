# 数据接口

背景不写入逐题 JSON。使用 `--background white` 或 `--background green` 选择，或设置 `config/project.json` 的 `background`；这样同一套题目数据可以生成两种背景且互不覆盖。

`questions.json` 顶层必须包含 `questions` 数组。每题至少包含：

- `number`、`displayNumber`、`type`、`stem`、`options`、`answer`
- `coverHook`、`topic`、`marks`
- `knowledge`、`optionNotes`、`answerReason`、`takeawayLines`
- `segments`：固定 14 个配音段，依次覆盖封面、读题、审题、知识点、教研提醒、逐项辨析、答案和片尾

每个 `segments` 项格式为：

```json
["场景名称", "完整口播句子", 0.55]
```

`focus-cues.json` 顶层包含 `questions` 对象，以题号字符串为键。每题包含：

- `stem`
- `knowledge`
- `reminder`
- `analysis`
- `answer`
- `takeaway`

每个重点项至少包含 `phrase`、`caption`、`anchor`、`at` 和 `duration`；需要定位到具体行时增加 `row`，需要指定动作时增加 `mode`。
