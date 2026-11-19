# 变更记录

## 1.2.4 — 2026-11-19

### 新增：Windows 免安装包（自带解释器与依赖）

- `outbreak-report-writing-1.2.4-windows-x64-embedded.zip`：`vendor/python` 里是一整只 python-build-standalone CPython 3.12.13 加七个依赖（pyyaml / jinja2 / matplotlib / python-docx / jsonschema / pypdf / pymupdf），解压即用——本机不用装 Python，也不用联网 pip。解压后 222 MB，其中解释器与依赖 221.6 MB。
- 真机实测（Windows 11 + PowerShell 5.1）：四个单测全过（`test_core` 38 项 / `test_deident` 10 项 / `test_fmt` 14 项 / `test_pdf_fallback` 6 项）；端到端出稿 md 5.3 KB、docx 106.6 KB、pdf 299.2 KB（5 页，字体已子集化），三格式 + 脱敏版齐全；解压到全新目录后同样全过，`sys.prefix` 落在包内 `vendor\python`（可整体搬目录）。

### 修复：`dsh plugin add` 会静默丢掉自带解释器（Windows 关键）

- `package.json` 的 `files` 白名单只列了 `scripts` / `templates` / `tests` 等，`vendor` 不在里面。pnpm 安装 `file:` 依赖时按 `files` 打包，于是 `vendor/python` 不进 `node_modules`，插件退回系统 `python`；没装 Python 的机器上首跑就是 `生成失败（exit ENOENT）`。
- 现在 `files` 补上 `vendor`：`dsh plugin add <解压目录>` 之后 `node_modules/outbreak-report-writing/vendor/python/python.exe` 存在，`resolvePython()` 首选它。已用「PATH 里没有 python」的干净环境复验：零配置出稿 `ok=true`，6 个文件齐全。

### 修复：`flowreport.py doctor` 在中文 Windows 控制台直接崩溃

- 控制台默认 CP936，`print("✓")` 抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2713' in position 1`，doctor 在第 6 项后中断；`install.ps1` 的第 4/4 步因此看起来像装坏了。
- 新增 `_mark()`：先问 `sys.stdout.encoding` 能不能表示 ✓ / ✗，不能就退化成 `[OK]` / `[NO]`；`doctor`、`build`、`gate` 四处标记都改用它。macOS / Linux（UTF-8）行为不变。

### 修复：`install.ps1` 在免安装包里第一步就报错

- 自带解释器模式第一句是 `pip install -r requirements.txt`，而 python-build-standalone 带 PEP 668 的 `Lib\EXTERNALLY-MANAGED`，直接 `error: externally-managed-environment`（exit 1）——用户看到的第一屏就是红字。
- 改为：先 `--break-system-packages --no-index` 做离线校验（依赖已烘进包内，1 秒通过、不联网）；确实缺才联网补装。
- 脚本开头统一 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`、`[Console]::OutputEncoding = UTF8`，doctor 的 ✓ 在 PowerShell 里正常显示。

### 修复：三个单测在 GBK 控制台「误报崩溃」

- `test_deident.py` / `test_fmt.py` / `test_pdf_fallback.py` 每条结果都打印 `✓` / `✗`，在中文 Windows 控制台（CP936）里同样抛 `UnicodeEncodeError` —— 明明断言全过，脚本却 exit 1。
- 三个文件各加一个 `_mark()`：编码装不下 ✓/✗ 时打印 `[OK]` / `[NO]`。现在 `python tests\test_xxx.py` 在 cmd / PowerShell 里直接跑即可，不再需要先设 `PYTHONIOENCODING`。

### 修复：失败提示不再只说 python3

- 插件失败时的 hint 原来固定写「确认 python3 已装 … 四项依赖」——Windows 上该是 `python`，而且实际要七项。改为按平台取 `python` / `python3`、补全七项，并分平台提示：Windows 免安装包自带 `vendor\python` 无需另装，从 git 装则先在本目录跑一次 `install.ps1`。

### 文档

- README 平台包表补 `-windows-x64-embedded.zip` 一行，原 `-windows-x64.zip` 注明是轻量包（需 Python 3.10+）；DSH 插件一节加 Windows 免安装包的 `dsh plugin --profile desktop add …` 用法与解释器挑选顺序；「一次性装齐」改成 `pip install -r requirements.txt`（七个依赖列全）。

## 1.2.1 — 2026-11-18

### 新增：Intel 芯片的 Mac 也能解压即用

- 第三个分发包 `outbreak-report-writing-1.2.1-macos-x86_64.tar.gz`：`vendor/venv` 里放的是独立的 x86_64 解释器（python-build-standalone 3.12.16），不依赖目标机的 python、也不怕 venv 里的解释器指向打包机器的绝对路径。Intel Mac 解压改路径即可跑全量引擎，不用 pip。
- 该包已在本机用 `arch -x86_64` 逐项复验：`doctor` 8 项全绿、全量出稿（docx 内嵌图 4 / 表 17、pdf 16 页、三格式一致性全 1.0）、轻量出稿（完成度 38.9%、4 图、三格式 + 脱敏版）、`tests/test_core.py` 38 项全过。

### 修复：arm64 包不再依赖本机 Python

- 1.2.0 的 `macos-arm64` 包里，`vendor/venv` 是由 python.org 的 framework 版 Python 建的 venv，`bin/python` 只是个 152 KB 的壳，`sys.base_prefix` 指向 `/Library/Frameworks/Python.framework/Versions/3.12`——目标机没装过 python.org 3.12 就起不来。
- 1.2.1 把 arm64 包也换成 python-build-standalone 3.12.16（arm64），`sys.base_prefix` 落在包内 `vendor/venv`，与 Intel 包、Windows 包的自包含程度一致。已解压到新路径复验：doctor 8/8、全量出稿全绿、轻量出稿 + 兜底 PDF、38 项测试全过。
- 代价：包体从 59 MB 涨到 96 MB（多出的是完整解释器与 stdlib）。

### 新增：没装 LibreOffice 也能出 PDF

- 原来 PDF 只有一条路：md → docx → `soffice --headless --convert-to pdf`。LibreOffice 在 macOS 上是 795 MB 的 .app，装不进发行包。
- 现在有兜底：新增 `scripts/md2pdf_fallback.py`，用 PyMuPDF 的 Story 排版引擎（MuPDF 自带）直接把 markdown 排成 A4 PDF，只依赖 `pymupdf`。无 `soffice` 时自动启用，内容、图表、分页齐全；版式是独立一套（表格列宽、图片缩放由 CSS 决定），与 docx 版略有差别。
- 有 LibreOffice 时行为不变：仍走 docx→pdf，版式与 Word 完全一致。
- 中文字体从系统里挑可用单字体（macOS `Arial Unicode.ttf`、Windows `msyh.ttc`/`simsun.ttc`、Linux Noto/WQY）；`.ttc` 集合字体用 fontTools 拆出单字重再用。
- 体积：Story 排版会把整个字体文件塞进 PDF（Arial Unicode 约 23 MB），4 页报告能到 42 MB。`md_to_pdf()` 末尾加了 `_compress_pdf()`，重开文档做字体子集化 + 流压缩，42 MB → 0.36 MB，页数、图数、汉字全部不变。老版本 pymupdf 没有 `subset_fonts` 时自动跳过。

### 修复

- `requirements.txt` 补 `PyYAML>=6.0`（轻量引擎读事件 YAML、`tests/test_core.py` 都依赖它，缺了会直接报「需要 PyYAML」）；`pymupdf` 加 `<2` 上限（2026 年 2.x 会连带拉 onnxruntime 等 200 MB+ 依赖，venv 从 238 MB 涨到 376 MB）。

## 1.2.0 — 2026-11-18

### 新增：两个平台的分发包

- `outbreak-report-writing-1.2.0-macos-arm64.tar.gz`：含 `vendor/`（含 arm64 版 `vendor/venv`），解压即用，无需 pip 联网。
- `outbreak-report-writing-1.2.0-windows-x64.zip`：含 `vendor/` 代码但不含 venv，首次运行 `install.ps1` 现场建环境（需 Python 3.10+）。
- 任意平台仍可 `git clone` 走轻量引擎；全量引擎需自备 `vendor/`。

### 新增：安装说明

五份 README（中/英/繁/德/日）各加「安装（两条路，选一条）」：A 轻量 clone 即用、B 全量带 `vendor/`，并附平台包对照表与「装完能干 / 干不了什么」的大白话差异。

### 新增：环境脚本

- `requirements.txt`：轻量引擎只需 `jinja2` / `matplotlib` / `python-docx`；全量另需 `jsonschema`、`pypdf`；PDF 回读自检另需 `pymupdf`（缺它时退化为只报页数）。
- `install.sh`（macOS / Linux）、`install.ps1`（Windows）：建 `vendor/venv`、装依赖、跑 `doctor` 自检。

### 修复：跨平台

- `index.js` `resolvePython()`：按平台选 `vendor/venv/bin/python`（macOS/Linux）或 `vendor/venv/Scripts/python.exe`（Windows）；系统解释器回退为 `python3` / `python`。
- `scripts/epi_viz.py`：中文字体候选补 `Microsoft YaHei`、`SimSun`。
- `scripts/build_report.py`：新增 `_find_soffice()`，按 `SOFFICE_BIN` 环境变量 → `PATH` → 各平台默认安装位置顺序找 LibreOffice；原来的候选里 `"soffice"` 会被无条件当作可用，Windows 上未装 PATH 时直接抛 `FileNotFoundError`，现在找不到就返回提示「md/docx 已生成，PDF 需要它」而不中断出稿。
- `scripts/flowreport.py`：`doctor` 的 `_soffice()` 同样改为环境变量 + `PATH` + 三平台路径，Windows 装了 LibreOffice 也能自检通过。
- `vendor/report_export/docx_writer.py`：正文/标题中文字体按 `sys.platform` 选择 —— Windows 宋体/黑体、macOS Songti SC/Heiti SC、其他 Noto CJK。
- `vendor/report_export/pdf_writer.py`：`SOFFICE_CANDIDATES` 补 `C:\Program Files\LibreOffice\program\soffice.exe` 等两个 Windows 路径；未找到时的提示补 Windows 说明。

> 后两项位于 `vendor/`，该目录被 `.gitignore` 排除、不随仓库发布；本版本的两个平台包已包含这两处修复。自行维护 `vendor/` 的，请按上面的行为同步（`docx_writer.py` 顶部字体常量改为按平台判断；`pdf_writer.py` 的候选元组补两个 Windows 路径）。

### 修复：插件依赖约束

- `package.json`：`@deepseek-ai/dsh-tools` 由写死的 `0.2.2-rc.1` 放宽为 `>=0.2.2-rc.1`，避免 DSH 升级到 `0.2.2-rc.3` 等版本时 peer 校验失配。

## 1.1.0 — 2026-11-18

- 模板缺陷修复（见 issue #1）：`scripts/build_report.py` 新增 `_fill_case_def()`，用事件日期与机构名回填病例定义里的 `<起止>`/`<机构>` 占位符；`templates/report_initial.md.j2` 补 `fig_age_sex` 引用（此前年龄性别图白算）；`templates/disease_profiles.yaml` 诺如条去掉多余的「起」字。
- 五份 README 顶部加 `vendor/` 缺失提示。
