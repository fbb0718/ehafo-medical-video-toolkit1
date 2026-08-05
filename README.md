# 易哈佛医学考试易错题视频生成工具包

当前版本为 v5.3，包含白色背景和绿色背景两套高质量正式主题。科目名称、账号名称、教研提醒、片尾文案、音色、背景和文件前缀由 `config/project.json` 或命令参数控制。

跨电脑使用先阅读 `PORTABLE_SETUP.md`。快速模式正式支持 macOS；首次安装后运行 `环境检查.command`，必须看到 `ENVIRONMENT_OK=true`。

## 需要准备的文件

- `data/questions.json`：已定稿的逐题讲稿。
- `data/focus-cues.json`：逐题划重点内容和时间锚点。
- `assets/voice/reviewed-smooth/qNN/manifest.json` 及其整题 WAV：已审核配音；没有配音时可用音色配置重新生成。
- `assets/voice/profiles/yhn/` 与 `assets/voice/profiles/mcy/`：两套完整音色配置和参考 WAV，已随包提供。

题目数据中的医学内容可以属于任意科目，但生成器代码和目录名保持通用。

## 一键生成

### 快速批量模式

已有审核配音时，优先执行：

```bash
python3 scripts/run_fast_question_project.py --variant 新版本名 --questions 5-5 --fps 30 --background white
python3 scripts/run_fast_question_project.py --variant 新版本名 --questions 5-5 --fps 30 --background green
```

该命令会自动识别重点、生成快速成片并完成解码和逐秒音频检查。完整规则见 `FAST_WORKFLOW.md`。

同一视觉场景内切换口播和重点时不会移动整页；只有真正切换场景才使用页面转场。该规则由 `tests/test_fast_transitions.py` 验证。

### HyperFrames 高质量模式

1. 修改 `config/project.json`。
2. 放入讲稿、重点 JSON 和配音文件。
3. 双击 `生成视频.command`。

已有审核配音时，终端可执行：

```bash
python3 scripts/run_question_project.py --skip-voice --quality high --background white
python3 scripts/run_question_project.py --skip-voice --quality high --background green
```

需要重新生成克隆配音时：

```bash
python3 scripts/run_question_project.py --voice yhn --quality high --background green
python3 scripts/run_question_project.py --voice mcy --quality high --background green
```

不需要打开 JSON；将题目和教材交给 Codex 后，在要求中写明“使用 v5.3 工具包、高质量正式版、音色 yhn（或 mcy）、绿色背景（或白色背景）”。Codex 应同时传入对应的 `--voice` 和 `--background` 参数。两种音色分别保存配音，固定片尾也会自动匹配，不会交叉复用。

未传 `--background` 时读取 `config/project.json` 的 `background`，默认值为 `white`。输出文件名固定包含 `white` 或 `green`，两种背景不得共用同一个输出文件。

生成结果位于 `renders/`，构建后的 HTML 位于 `generated/compositions/`，检查结果位于 `checks/`。

高质量模式需要 Node.js 22+。本地克隆配音需要 Apple Silicon 和额外模型下载，模型权重不包含在工具包内。

## 更换科目

只修改以下内容，不需要重新打包生成器：

- `config/project.json` 的展示文案和文件前缀。
- `data/questions.json` 和 `data/focus-cues.json`。
- 需要更换声音时，使用 `--voice yhn` 或 `--voice mcy`；两套资源已经内置。

若修改了生成器脚本、HTML 结构、字体、品牌素材、依赖版本或质检规则，才需要重新导出生成包。

## 固定讲解顺序

封面、读题、审题、知识点、教研提醒、逐项辨析、答案推导、答案揭晓、答案边界、考点口诀、关注片尾。单题通常 1 至 2 分钟，复杂题可自然延长。

## 考试级共享片尾

同一考试、同一音色使用 `config/project.json` 中对应的 `sharedOutros`。共享片尾音频只生成并审核一次，后续每题直接引用同一个 WAV；共享资源存在时不会重新生成片尾。

只有需要主动更新该考试的统一片尾时，才执行：

```bash
python3 scripts/run_question_project.py --overwrite-shared-outro --skip-render
```

正常生成题目不要传入 `--overwrite-shared-outro`。
