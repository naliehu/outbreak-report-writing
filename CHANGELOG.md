# 变更记录

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
