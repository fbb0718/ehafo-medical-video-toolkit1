# 易哈佛视频工具包跨电脑使用说明

发行包版本：v5.3；快速渲染器版本：高质量版对齐 v5.3.1，支持白色和绿色背景。

## 支持范围

- 高质量版对齐快速模式：macOS 13 或更高，支持 Apple Silicon 和 Intel Mac。
- 本地克隆配音：仅支持 Apple Silicon 和 Python 3.11/3.12；首次使用需要联网下载模型。
- HyperFrames 高质量模式：需要 Node.js 22 或更高版本，首次安装需要联网。
- Windows/Linux 当前不能直接使用本包的快速渲染器，因为字体文件和字体索引采用 macOS PingFang SC、Songti SC。

## 新电脑首次安装

1. 完整解压工具包，不要只复制其中几个脚本。
2. 若 `.command` 不能双击，在终端进入工具包后执行：

```bash
chmod +x *.command
```

3. 安装 Python 3.11+ 和包含 `libx264`、AAC 的 FFmpeg。使用 Homebrew 时：

```bash
brew install python@3.12 ffmpeg node@22
```

4. 双击 `首次安装快速版.command`。
5. 双击 `环境检查.command`，必须看到 `ENVIRONMENT_OK=true`。
6. 双击 `生成快速视频.command`，按提示输入 `white` 或 `green`；成片位于 `renders/`，质检报告位于 `checks/fast-<背景>-<版本名>/`。

首次安装需要网络下载 Pillow。完成安装且审核音频已经放入包内后，快速生成不需要网络。

## 完整性校验

在工具包根目录执行：

```bash
shasum -a 256 -c MANIFEST.sha256
```

所有文件都应显示 `OK`。压缩包同级的 `CHECKSUMS.sha256` 用于校验 `.zip` 和 `.tar.zst`。

## 当前示例可直接生成

包内已经包含第 5 题：

- 结构化题目和口播。
- yhn 已审核整题音频。
- yhn、mcy 两套完整 profile 和参考 WAV。
- yhn、mcy 已审核固定片尾，选择音色时自动匹配。
- 品牌图和项目配置。
- 自动重点和转场回归测试。
- 白底 v5 示例成片、代表帧、C 项转场检查片段和完整质检报告。
- 绿底 v5.3 示例成片、快速版代表帧、高质量版预览帧和完整质检报告。

## 添加新题

1. 将新题加入 `data/questions.json`。
2. 将审核音频放到 `assets/voice/reviewed-smooth/qNN/`，同时提供 `manifest.json` 和整题 WAV。
3. 修改 `config/project.json` 的题号范围、品牌文案、固定片尾和文件前缀。
4. 每次使用新的 `--variant`，不得覆盖已审核成片。
5. 自动重点不需要手写；最终仍需人工审核医学内容、配音和代表帧。

详细数据规则、重点规则和缓存规则见 `FAST_WORKFLOW.md`。

## 可选功能

HyperFrames 高质量模式使用 `首次安装.command` 和 `生成视频.command`。安装脚本只安装正式流程所需的快速渲染依赖；Apple Silicon 上还会自动安装 `requirements-voice-apple-silicon.txt`。模型权重不包含在压缩包内，首次生成克隆配音时自动联网下载。

命令行选择音色：

```bash
python3 scripts/run_question_project.py --voice yhn --quality high
python3 scripts/run_question_project.py --voice mcy --quality high
```

背景选择：

```bash
python3 scripts/run_question_project.py --voice yhn --quality high --background white
python3 scripts/run_question_project.py --voice yhn --quality high --background green
```

若使用 Codex，可直接在要求中写“白色背景”或“绿色背景”。未写时使用 `config/project.json` 中的 `background`，默认是 `white`。

第 5 题随包审核音频是 yhn。使用 mcy 生成新配音时会写入独立的 `assets/voice/reviewed-mcy/`，不会覆盖或误用 yhn 音频。
