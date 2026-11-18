#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2pdf_fallback — 不依赖 LibreOffice 的 PDF 兜底导出

为什么需要它：主链路是 md → docx → soffice → pdf，版式与 Word 完全一致，但要求本机装
LibreOffice（macOS 的 .app 795 MB、Windows 安装包 350 MB，装不进发行包）。本模块用
PyMuPDF 的 Story（HTML/CSS 排版引擎，MuPDF 自带）直接把 markdown 排成 PDF，只需一个
纯 Python 依赖 pymupdf，因此**开箱可用**；代价是版式是独立的一套，与 docx 版不完全一致，
表格列宽与图片缩放由 CSS 决定。

用法：
    from md2pdf_fallback import md_to_pdf
    md_to_pdf("报告.md", "报告.pdf")

没有 pymupdf 时抛 RuntimeError，调用方应捕获后降级为「仅 md/docx」。
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

# 单文件 CJK 字体候选（.ttc 集合需要用 fontTools 拆，见 _resolve_font）
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",   # macOS，含中文
    "/System/Library/Fonts/Supplemental/Songti.ttc",          # macOS，集合
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    r"C:\Windows\Fonts\msyh.ttc",                             # Windows，集合
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
)

CSS = """
@font-face { font-family: cjk; src: url('cjk.ttf'); }
body { font-family: cjk; font-size: 11pt; line-height: 1.55; color: #111; }
h1 { font-family: cjk; font-size: 17pt; text-align: center; margin: 0 0 14pt 0; }
h2 { font-family: cjk; font-size: 13pt; margin: 12pt 0 5pt 0; }
h3 { font-family: cjk; font-size: 11.5pt; margin: 9pt 0 4pt 0; }
p { font-family: cjk; font-size: 11pt; margin: 0 0 5pt 0; text-indent: 22pt; }
p.plain { text-indent: 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt 0; font-size: 9pt; }
td, th { font-family: cjk; border: 0.6pt solid #888; padding: 3pt 4pt; font-size: 9pt; }
th { background-color: #f0f0f0; }
figure { text-align: center; margin: 8pt 0; }
figcaption { font-family: cjk; font-size: 9pt; color: #444; text-indent: 0; }
li { font-family: cjk; font-size: 11pt; }
"""


def _resolve_font():
    """返回可被 MuPDF 使用的单字体字节 + 文件名；找不到返回 None。"""
    for cand in FONT_CANDIDATES:
        p = Path(cand)
        if not p.exists():
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if not cand.lower().endswith(".ttc"):
            return data, "cjk.ttf"
        # .ttc 是字体集合，MuPDF 不支持，用 fontTools 取第一个字体重新打包成 ttf
        try:
            from fontTools.ttLib import TTCollection

            coll = TTCollection(str(p))
            buf = tempfile.SpooledTemporaryFile()
            coll.fonts[0].save(buf)
            buf.seek(0)
            return buf.read(), "cjk.ttf"
        except Exception:
            continue
    return None


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _inline(text: str) -> str:
    """处理 **粗体** 与行内 `code`。"""
    text = _esc(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<span>\1</span>", text)
    return text


def md_to_html(md_text: str, base_dir: str, asset_names: dict | None = None) -> str:
    """把本项目产出的 markdown（标题/段落/表格/图片/列表/分页）转成 HTML 片段。

    asset_names: {磁盘绝对路径: archive 内文件名}，用于图片。
    """
    asset_names = asset_names or {}
    out: list[str] = []
    lines = md_text.splitlines()
    i = 0
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        # 表格
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:|-]+$", "|".join(cells)):
                    rows.append(cells)
                i += 1
            if rows:
                close_list()
                out.append("<table>")
                head, body = rows[0], rows[1:]
                out.append("<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>")
                for r in body:
                    out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
                out.append("</table>")
            continue

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            close_list()
            out.append('<p style="page-break-after: always;"></p>')
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            close_list()
            lvl = min(len(m.group(1)), 3)
            out.append(f"<h{lvl}>{_inline(m.group(2).strip())}</h{lvl}>")
            i += 1
            continue

        # 图片：![caption](path)
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", stripped)
        if m:
            close_list()
            cap, raw_path = m.group(1), m.group(2)
            path = raw_path if os.path.isabs(raw_path) else os.path.join(base_dir, raw_path)
            name = asset_names.get(os.path.abspath(path))
            if name:
                out.append(f'<figure><img src="{name}" style="width:100%;"></img>'
                           f'<figcaption>{_inline(cap)}</figcaption></figure>')
            else:
                out.append(f'<p class="plain">〔图片缺失：{_esc(raw_path)}〕</p>')
            i += 1
            continue

        # 列表
        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        # 有序列表按普通段落处理即可（报告里少见）
        close_list()
        out.append(f"<p>{_inline(stripped)}</p>")
        i += 1

    close_list()
    return "\n".join(out)


def md_to_pdf(md_path, pdf_path=None, title: str | None = None) -> Path:
    """markdown → PDF（PyMuPDF Story，中文走内嵌 CJK 字体）。返回 pdf 路径。"""
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("需要 pymupdf：pip install 'pymupdf<2'") from exc

    md_path = Path(md_path).resolve()
    if not md_path.is_file():
        raise RuntimeError(f"待转换的 md 不存在：{md_path}")
    pdf_path = Path(pdf_path or md_path.with_suffix(".pdf")).resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    md_text = md_path.read_text(encoding="utf-8")
    base_dir = str(md_path.parent)

    # 图片：把报告引用的图塞进 MuPDF 的 Archive
    archive = pymupdf.Archive()
    asset_names: dict[str, str] = {}
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md_text):
        raw_path = m.group(1)
        path = raw_path if os.path.isabs(raw_path) else os.path.join(base_dir, raw_path)
        if os.path.isfile(path):
            name = f"img{len(asset_names)}{os.path.splitext(path)[1].lower()}"
            archive.add(Path(path).read_bytes(), name)
            asset_names[os.path.abspath(path)] = name

    font = _resolve_font()
    css = CSS
    if font:
        data, fname = font
        archive.add(data, fname)
        css = CSS.replace("'cjk.ttf'", f"'{fname}'")

    html = md_to_html(md_text, base_dir, asset_names)
    if title:
        html = f"<h1>{_esc(title)}</h1>\n{html}"

    story = pymupdf.Story(html=html, user_css=css, archive=archive)
    writer = pymupdf.DocumentWriter(str(pdf_path))
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (56, 54, -56, -54)   # 约 2 cm 页边距
    more = 1
    guard = 0
    while more and guard < 500:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
        guard += 1
    writer.close()
    _compress_pdf(pdf_path)
    return pdf_path


def _compress_pdf(pdf_path) -> None:
    """字体整包嵌入会让 4 页报告涨到 40 MB+；子集化后回到几百 KB。

    Story 排版把整个 .ttf 塞进 PDF（Arial Unicode 约 23 MB），这里重开文档做字体子集化
    并用杂项对象回收 + 流压缩重写一遍。失败（老版本 pymupdf 无 subset_fonts）就原样保留。
    """
    import pymupdf  # 与 md_to_pdf 一样按需导入，避免模块级硬依赖

    try:
        doc = pymupdf.open(str(pdf_path))
        try:
            if not hasattr(doc, "subset_fonts"):
                doc.close()
                return
            doc.subset_fonts()
            tmp = str(pdf_path) + ".tmp"
            doc.save(tmp, garbage=4, deflate=True)
        finally:
            doc.close()
        os.replace(tmp, str(pdf_path))
    except Exception:
        # 压缩是优化项，失败不影响出稿
        for leftover in (str(pdf_path) + ".tmp",):
            if os.path.exists(leftover):
                try:
                    os.remove(leftover)
                except OSError:
                    pass


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python md2pdf_fallback.py 报告.md [输出.pdf]")
        raise SystemExit(2)
    print(md_to_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
