# 变更记录

## 1.2.4 — 2026-11-19

- Windows 免安装包把 `vendor/` 一并装入，装成 DSH 插件时不再漏文件。
- 修 Windows GBK 控制台下 `doctor`、`install.ps1` 与两个单测的误报崩溃：输出统一按 UTF-8。
- 三个平台包同源于本版本代码。

## 1.2.3 — 2026-11-19

- 新增 Windows 免安装包 `windows-x64-embedded.zip`：自带解释器与依赖，解压即用，不再要求本机装 Python。
- 支持包内解释器目录 `vendor/python`：插件、`install.ps1`、`install.sh` 都优先用它，不碰系统 Python。

## 1.2.2 — 2026-11-19

- 修 Windows 出稿崩溃：`%-m` / `%-d` 是 POSIX 扩展，Windows 的 CRT 不认，改为跨平台 `_fmt()`。
- 修 PDF 体积异常：字体子集化被文件句柄占用打断且异常被吞，改为暂存文件 + 重试 + 失败告警。
- 修工具返回 JSON 中文乱码：子进程输出两侧统一 UTF-8。
- `@deepseek-ai/dsh-tools` 由 `>=0.2.2-rc.1` 收紧为 `^0.2.2-rc.5`。

## 1.2.1 — 2026-11-18

- 新增 Intel Mac 包，`vendor/venv` 带 x86_64 独立解释器。
- arm64 包改用 python-build-standalone，不再依赖打包机器的 python.org 安装。
- 没装 LibreOffice 也能出 PDF：内置 PyMuPDF 排版兜底，字体子集化后体积从 42 MB 降到 0.4 MB。
- `requirements.txt` 补 PyYAML，`pymupdf` 加上限 `<2`。

## 1.2.0 — 2026-11-18

- 新增 macOS / Windows 分发包与平台对照表。
- 新增 `requirements.txt`、`install.sh`、`install.ps1`。
- 跨平台：解释器查找、LibreOffice 查找、docx 中文字体按平台选择。
- 五份 README 补安装说明。

## 1.1.0 — 2026-11-18

- 修模板三处缺陷：病例定义占位符回填、年龄性别图未被引用、诺如病种档案多余字符。
- 输出未脱敏与脱敏两版。
- README 顶部补 `vendor/` 缺失提示。
