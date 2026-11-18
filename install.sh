#!/usr/bin/env bash
# 传染病流调报告撰写技能 —— macOS / Linux 环境安装脚本
# 用法：bash install.sh
#
# 作用：用系统 python3 建 vendor/venv、装齐依赖、跑一次 doctor 自检。
# 何时需要：发布的 macOS 包已带 arm64 的 vendor/venv；若本机是 Intel Mac 或 Linux，
#           或 venv 被系统更新弄坏，跑本脚本重建即可。

set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/4 查找 python3 =="
PY=$(command -v python3 || true)
[ -n "$PY" ] || { echo "未找到 python3，请先安装 Python 3.10+"; exit 1; }
"$PY" - <<'CHK'
import sys
if sys.version_info < (3, 10):
    sys.exit("需要 Python 3.10 及以上，当前为 %s" % sys.version.split()[0])
print("   Python", sys.version.split()[0], sys.executable)
CHK

echo "== 2/4 创建 vendor/venv =="
if [ -x vendor/venv/bin/python ]; then
  echo "   已存在，跳过创建（如需重建：rm -rf vendor/venv 后重跑）"
else
  "$PY" -m venv vendor/venv
fi

echo "== 3/4 安装依赖 =="
env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python -m pip install --upgrade pip --quiet
env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python -m pip install -r requirements.txt

echo "== 4/4 自检 =="
env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python scripts/flowreport.py doctor || {
  echo "自检有项目未通过；md/docx 仍可导出，PDF 需先安装 LibreOffice（brew install --cask libreoffice）"
}
