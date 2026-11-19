"""PDF 兜底导出回归：字体子集化（顺手把几十 MB 压回几百 KB）+ 替换句柄重试。

Windows 上 os.replace 会撞上未释放的写句柄（WinError 5），如果这里静默失败，
PDF 就会停在整包嵌入的体积。本测试用 monkeypatch 模拟该失败，验证重试与兜底。
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

try:
    import pymupdf  # noqa: F401
except ImportError:
    print("SKIP: 未安装 pymupdf，跳过 PDF 兜底测试")
    raise SystemExit(0)

import md2pdf_fallback as fb  # noqa: E402

fail = 0


def check(cond, label, extra=""):
    global fail
    print(f"{'✓' if cond else '✗'} {label}{(' — ' + str(extra)) if extra else ''}")
    fail += 0 if cond else 1


MD = """# 关于xx小学一起水痘暴发疫情的初步调查报告

本次疫情自2026年11月8日首例发病，共12例。

## 一、基本情况

xx市xx区xx小学，共480名学生。

## 二、疫情概况

| 项目 | 例数 | 占比 |
|---|---|---|
| 男 | 6 | 50.0% |
| 女 | 6 | 50.0% |
"""

tmpdir = Path(tempfile.mkdtemp(prefix="pdftest_", dir=os.path.expanduser("~/.hermes/cache/scratch")))
md_path = tmpdir / "报告.md"
md_path.write_text(MD, encoding="utf-8")

# --- 1. 正常路径：出 PDF 且字体已子集化
pdf_path = tmpdir / "报告.pdf"
fb.md_to_pdf(md_path, pdf_path)
size_mb = pdf_path.stat().st_size / 1024 / 1024
check(pdf_path.exists() and pdf_path.stat().st_size > 10_000, "生成 PDF", f"{size_mb:.2f} MB")
check(size_mb < 5, "体积在子集化后的合理范围（<5 MB）", f"{size_mb:.2f} MB")

doc = pymupdf.open(str(pdf_path))
fonts = [f[3] for f in doc[0].get_fonts()] if doc.page_count else []
doc.close()
check(any("+" in name for name in fonts), "字体已子集化（名字带 XXXXXX+ 前缀）", fonts)

# --- 2. 模拟 Windows 句柄占用：os.replace 前两次抛 PermissionError
real_replace = os.replace
state = {"n": 0}


def flaky_replace(src, dst, *a, **kw):
    state["n"] += 1
    if state["n"] <= 2:
        raise PermissionError(13, "拒绝访问。", str(dst))
    return real_replace(src, dst, *a, **kw)


os.replace = flaky_replace
try:
    pdf2 = tmpdir / "报告-重试.pdf"
    fb.md_to_pdf(md_path, pdf2)
    ok2 = pdf2.exists() and pdf2.stat().st_size > 10_000
finally:
    os.replace = real_replace
check(ok2, "替换被占用两次后仍能落盘（重试生效）", f"重试次数 {state['n']}")

# --- 3. 替换始终失败：必须走兜底拷贝，绝不能没有 PDF
state2 = {"n": 0}


def always_fail(src, dst, *a, **kw):
    state2["n"] += 1
    raise PermissionError(13, "拒绝访问。", str(dst))


os.replace = always_fail
try:
    pdf3 = tmpdir / "报告-兜底.pdf"
    fb.md_to_pdf(md_path, pdf3)
    ok3 = pdf3.exists() and pdf3.stat().st_size > 10_000
finally:
    os.replace = real_replace
check(ok3, "替换彻底失败时兜底拷贝出 PDF（不静默丢稿）", f"尝试 {state2['n']} 次")

# --- 4. 不留下临时文件
leftovers = [p.name for p in tmpdir.iterdir() if p.suffix in (".tmp",) or p.name.startswith("tmp")]
check(not leftovers, "不残留临时文件", leftovers)

print("\n" + ("全部通过" if fail == 0 else f"{fail} 项失败"))
sys.exit(1 if fail else 0)
