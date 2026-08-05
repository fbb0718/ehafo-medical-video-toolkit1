# 易哈佛医学题视频快速生成规范

## 适用范围

快速模式负责把“结构化题目 JSON + 已审核配音”生成 `1080x1920`、30 fps、H.264/AAC 成片，并完成自动重点、解码和逐秒音频检查。

第 5 题高质量版对齐渲染器 v5.3 支持 `white` 与 `green`。五分钟目标不包含首次阅读教材、医学内容定稿和克隆配音生成；这些步骤会受材料篇幅、模型和人工审核影响。

## 两种生成模式

- 快速模式：Pillow 生成静态场景和重点状态，FFmpeg 完成重点擦除式揭示、场景转场、音频和编码。默认用于批量题目。
- 高质量模式：HyperFrames + GSAP 逐帧渲染。用于需要复杂运动、精细镜头或特别版式的题目。

快速模式命令：

```bash
python3 scripts/run_fast_question_project.py --variant <新版本名> --questions <起始题号>-<结束题号> --fps 30 --background <white或green>
```

高质量模式命令：

```bash
python3 scripts/run_question_project.py --skip-voice --quality high --background <white或green>
```

## 新题复用流程

1. 从题目原文和教材整理 `data/questions.json`。
2. 用 `--voice yhn` 或 `--voice mcy` 生成并人工审核分段配音；两种音色使用独立目录。
3. 不需要手写重点文件。快速管线会生成自动重点并调用现有规则校验。
4. 修改 `config/project.json` 的题号范围、版本号和展示文案；音色用命令参数选择。
5. 使用新的 `--variant` 运行快速命令，禁止覆盖旧成片。
6. 查看 `checks/fast-<variant>/pipeline-report.json`，必须满足 `underFiveMinutes: true`、解码通过且没有连续两秒静音。

其他电脑首次使用前先运行 `首次安装快速版.command`，再运行 `环境检查.command`。完整迁移要求见 `PORTABLE_SETUP.md`。

## 题目数据规则

每题必须提供：

- `number`、`displayNumber`、`type`、`stem`、`options`、`answer`。
- `coverHook` 和 `topic`。
- `marks`：题干中最多四个关键条件，必须是题干原文的连续子串。
- `knowledge`：建议三条，每条为 `[标题, 正文]`。
- `optionNotes`：每个选项一条辨析，正确选项在答案揭晓前不得标记。
- `answerReason`：包含决定性推导和最终结论。
- `takeawayLines`：当前固定四句，一句一行，每句不超过 16 个汉字为佳。
- `segments`：当前固定 14 段，顺序见下表。

| 索引 | 场景 |
|---:|---|
| 0 | 封面 |
| 1 | 读题 |
| 2 | 审题 |
| 3-5 | 知识点 |
| 6 | 品牌提醒 |
| 7-8 | 逐项解析 |
| 9 | 答案推导 |
| 10 | 公布答案 |
| 11 | 答案说明 |
| 12 | 考点口诀 |
| 13 | 关注片尾 |

每个段落格式为 `[场景名称, 完整口播, 段后停顿秒数]`。口播必须和最终审核音频一致。

## 自动重点规则

自动重点由 `scripts/auto_focus_cues.py` 生成，输出兼容原有 `focus-cues.json`。

- 题干优先标记否定词、数值、单位、限制条件和关键医学指标。
- 知识点优先标记“等于、减去、扣除、按”等关系后的核心术语。
- 教研提醒优先标记步骤、单位检查和“不要、必须、以……为准”等防错短语。
- 逐项辨析跳过正确答案，标记“近似参考值、低于、高于、不符合、误加、误减”等错误依据。
- 答案只在“公布答案”段标记最终结论。
- 口诀逐句标记，保持原行序。
- `phrase` 必须存在于屏幕原文，`anchor` 必须存在于对应口播。
- 普通重点不超过 16 字；不得整段着色；同一行重点不得重叠。

动作类型：普通条件使用下划线，短术语使用圈选，否定或结论使用浅红色块。动画时间根据锚点在口播中的字符位置确定；需要更高精度时可增加本地强制对齐，但不阻塞快速模式。

重点视觉固定为：下划线和圈选使用教学红 `#B42318`；浅红高亮层使用 `rgba(180,35,24,.20)`。快速渲染器在白底上使用其精确合成色 `#F0D3D1`。

## 背景主题规则

- `--background white`：沿用 v5.2 白底正式版，不能因新增绿底而改变原版结构或颜色。
- `--background green`：画布 `#003A46`、题目区 `#00343D`、正文白 `#F7FAFA`、提示黄 `#F4D04F`、边框 `#6F898D`。
- 绿底只切换颜色与背景 Logo；页面结构、字体、字号、间距、重点动作和转场时机必须与 v5.2 一致。
- 绿底顶部 `0-200 px` 固定留空。低透明度完整 Logo 固定缩小放在右下侧空白栏，不得出现在顶部，也不得只露出部分文字。
- 绿底透明高亮仍等价于 `rgba(180,35,24,.20)`；快速渲染器在题目区上的精确合成色为 `#243136`。
- 背景类型必须进入 HTML 名称、composition id、PNG 缓存键、MP4 文件名和 QA 报告。

## 场景转场规则

- 封面、读题、知识点、教研提醒、逐项辨析、答案、口诀之间发生真正场景变化时，使用页面转场。
- 同一场景内切换口播段时，只淡化字幕，不移动页面。
- 同一逐项辨析页面从 A/B 讲到 C/D/E 时不得整页滑动。
- 划重点状态只淡入下划线、圈选或高亮，不移动整页。
- 片尾使用柔和淡入。
- `tests/test_fast_transitions.py` 锁定以上规则，正式打包前必须通过。

## 配音复用规则

- 同一段文本、同一音色和同一生成参数命中缓存时不得重生成。
- 同一考试、同一音色共用固定片尾。配置路径必须与实际文件名一致。
- `yhn固定片尾.wav` 和 `mcy固定片尾.wav` 是已审核资源；不要使用 `--overwrite-shared-outro`，除非明确要求更新片尾。
- `assets/voice/profiles/yhn/` 和 `assets/voice/profiles/mcy/` 分别包含完整 profile 与参考 WAV；不得交叉引用。
- 选择 `mcy` 时配音写入 `assets/voice/reviewed-mcy/`，选择 `yhn` 时写入 `assets/voice/reviewed-smooth/`。
- 修改任一段口播时，只重生成该段并重新组装整题 WAV。
- 快速渲染不包含 TTS 时间。首次生成克隆音频后必须人工听审。

## 缓存与版本规则

场景缓存键包含渲染器版本、题目、自动重点、音频 manifest 和展示配置。任一内容变化都会创建新缓存目录。

- 只改版本名：可复用 PNG 缓存，但会输出新的 MP4。
- 改题目、重点、字幕或展示配置：重新生成受影响的 PNG。
- 改音频：重新合成 MP4；若字幕时间改变，自动重点时间随 manifest 重算。
- 改渲染器视觉代码：必须提升 `RENDERER_VERSION`；新缓存会自动隔离，不需要删除旧缓存。
- 永远使用新 variant，不覆盖已审核成片。

## 时间与质量判定

`scripts/run_fast_question_project.py` 的报告覆盖：

- 自动重点生成和校验。
- PNG 场景生成或缓存命中。
- FFmpeg 合成和编码。
- H.264、1080x1920、AAC、48 kHz 和时长检查。
- 完整视频解码。
- 逐秒音频检查，禁止连续两秒静音。

正式交付前仍需人工查看封面、读题、知识点、辨析、答案、口诀和片尾代表帧，并试听新生成或修改过的口播。

## 环境要求

快速模式：

- Python 3.11 或更高版本。
- Pillow 12.2.0。
- FFmpeg/FFprobe，必须包含 `libx264` 和 AAC 编码器。
- macOS 使用系统 PingFang SC 和 Songti SC。其他系统需修改渲染器字体路径。
- 运行 `scripts/check_environment.py` 必须输出 `ENVIRONMENT_OK=true`。

高质量模式额外需要 Node.js 22 或更高版本和 HyperFrames 依赖。

Apple Silicon 本地克隆配音额外使用 `requirements-voice-apple-silicon.txt`，模型为 `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16`。
