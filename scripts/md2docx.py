#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2docx.py —— 把报告 Markdown 转成符合中文公文/疾控报告排版习惯的 docx

支持的 Markdown 子集（够用且可控）：
  # / ## / ### 标题      段落
  | 表格 |                ![图N 题注](path)
  - 无序列表              1. 有序列表
  > 落款块                **加粗**
  〔待补N〕 自动标红加底纹（醒目提示待补充信息，是技能的核心约定）
  --- 分页
"""
from __future__ import annotations

import os
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

PROFILES = {
    # 疾控系统常用：正文宋体小四、1.5倍行距、标题黑体
    "default": dict(body="宋体", body_pt=12, h1="黑体", h1_pt=22, h2="黑体", h2_pt=16,
                    h3="黑体", h3_pt=14, line=1.5, first_indent=0.74),
    # 严格公文式：正文仿宋_GB2312 三号
    "gongwen": dict(body="仿宋_GB2312", body_pt=16, h1="方正小标宋简体", h1_pt=22, h2="黑体",
                    h2_pt=16, h3="楷体_GB2312", h3_pt=16, line=1.55, first_indent=0.74),
    # 紧凑：便于打印与快速审阅
    "compact": dict(body="宋体", body_pt=10.5, h1="黑体", h1_pt=18, h2="黑体", h2_pt=14,
                    h3="黑体", h3_pt=12, line=1.25, first_indent=0.6),
}
PENDING_RE = re.compile(r"〔待补[^〕]*〕")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _set_cjk(run, font_name):
    run.font.name = font_name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), font_name)


def _shade(run, color="FFF2CC"):
    rpr = run._element.get_or_add_rPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    rpr.append(shd)


def _add_runs(par, text, font, size, bold=False, color=None):
    """处理 **加粗** 与 〔待补N〕 高亮。"""
    text = LINK_RE.sub(r"\1", text)
    pos = 0
    tokens = []
    for m in BOLD_RE.finditer(text):
        if m.start() > pos:
            tokens.append((text[pos:m.start()], False))
        tokens.append((m.group(1), True))
        pos = m.end()
    if pos < len(text):
        tokens.append((text[pos:], False))
    if not tokens:
        tokens = [(text, bold)]
    for seg, is_bold in tokens:
        sub_pos = 0
        for pm in PENDING_RE.finditer(seg):
            if pm.start() > sub_pos:
                r = par.add_run(seg[sub_pos:pm.start()])
                _set_cjk(r, font); r.font.size = Pt(size)
                r.bold = bold or is_bold
                if color: r.font.color.rgb = color
            r = par.add_run(pm.group(0))
            _set_cjk(r, font); r.font.size = Pt(size)
            r.bold = True
            r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
            _shade(r)
            sub_pos = pm.end()
        if sub_pos < len(seg):
            r = par.add_run(seg[sub_pos:])
            _set_cjk(r, font); r.font.size = Pt(size)
            r.bold = bold or is_bold
            if color: r.font.color.rgb = color


def _pformat(par, cfg, indent=True, align=None, space_before=0, space_after=4):
    pf = par.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = cfg["line"]
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if indent:
        pf.first_line_indent = Cm(cfg["first_indent"])
    if align is not None:
        par.alignment = align


def _footer_page_number(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("第 ")
    _set_cjk(r, "宋体"); r.font.size = Pt(9)
    r2 = p.add_run()
    _set_cjk(r2, "宋体"); r2.font.size = Pt(9)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    r2._element.addnext(fld)
    r3 = p.add_run(" 页")
    _set_cjk(r3, "宋体"); r3.font.size = Pt(9)


def _table(doc, rows, cfg):
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    t = doc.add_table(rows=0, cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for ci in range(ncol):
            txt = row[ci] if ci < len(row) else ""
            cell = cells[ci]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf = p.paragraph_format
            pf.space_before = Pt(1); pf.space_after = Pt(1)
            pf.line_spacing = 1.0
            _add_runs(p, txt, cfg["body"], cfg["body_pt"] - 1.5, bold=(ri == 0))
    doc.add_paragraph()


def convert(md_path, docx_path, profile="default", title=None):
    cfg = PROFILES.get(profile, PROFILES["default"])
    base_dir = os.path.dirname(os.path.abspath(md_path))
    missing_imgs = []
    lines = open(md_path, encoding="utf-8").read().splitlines()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(2.54), Cm(2.54)
    sec.left_margin, sec.right_margin = Cm(2.8), Cm(2.6)
    _footer_page_number(sec)

    st = doc.styles["Normal"]
    st.font.size = Pt(cfg["body_pt"])
    rpr = st.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), cfg["body"])

    i = 0
    buf_table = []
    first_h1 = True
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        # 表格
        if line.strip().startswith("|"):
            buf_table.append([c.strip() for c in line.strip().strip("|").split("|")])
            # 跳过对齐分隔行
            if i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
                i += 1
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not nxt.strip().startswith("|"):
                _table(doc, buf_table, cfg)
                buf_table = []
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if line.strip() == "---":
            doc.add_page_break()
            i += 1
            continue
        # 标题
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            lvl, txt = len(m.group(1)), m.group(2).strip()
            p = doc.add_paragraph()
            if lvl == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _add_runs(p, txt, cfg["h1"], cfg["h1_pt"], bold=True)
                pf = p.paragraph_format
                pf.space_before = Pt(0 if first_h1 else 12)
                pf.space_after = Pt(14)
                pf.line_spacing = 1.3
                first_h1 = False
            elif lvl == 2:
                _add_runs(p, txt, cfg["h2"], cfg["h2_pt"], bold=True)
                _pformat(p, cfg, indent=False, space_before=10, space_after=4)
            else:
                _add_runs(p, txt, cfg["h3"], cfg["h3_pt"], bold=True)
                _pformat(p, cfg, indent=False, space_before=6, space_after=2)
            i += 1
            continue
        # 图片
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
        if m:
            cap, raw_path = m.group(1), m.group(2)
            path = raw_path if os.path.isabs(raw_path) else os.path.join(base_dir, raw_path)
            if not os.path.exists(path):
                missing_imgs.append(raw_path)
            if os.path.exists(path):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(2)
                run = p.add_run()
                try:
                    from PIL import Image  # 可选
                    w, h = Image.open(path).size
                    width_cm = 15.2
                    if h / w > 1.2:
                        width_cm = min(11.0, 15.2 * (w / h) * 1.2)
                    run.add_picture(path, width=Cm(width_cm))
                except Exception:
                    run.add_picture(path, width=Cm(15.2))
            if cap:
                pc = doc.add_paragraph()
                pc.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _add_runs(pc, cap, cfg["h2"], cfg["body_pt"] - 2.5, bold=True)
                pc.paragraph_format.space_after = Pt(10)
            i += 1
            continue
        # 引用（落款）
        if line.strip().startswith(">"):
            body = line.strip().lstrip(">").strip()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            _add_runs(p, body, cfg["body"], cfg["body_pt"] - 1)
            _pformat(p, cfg, indent=False, space_before=2, space_after=2)
            i += 1
            continue
        # 列表
        m = re.match(r"^(\s*)([-*]|\d+[.)])\s+(.*)$", line)
        if m:
            txt = m.group(3)
            p = doc.add_paragraph()
            _add_runs(p, txt, cfg["body"], cfg["body_pt"])
            _pformat(p, cfg, indent=False, space_after=2)
            p.paragraph_format.left_indent = Cm(0.9)
            p.paragraph_format.first_line_indent = Cm(-0.45)
            i += 1
            continue
        # 普通段落
        p = doc.add_paragraph()
        _add_runs(p, line.strip(), cfg["body"], cfg["body_pt"])
        _pformat(p, cfg, indent=True)
        i += 1

    doc.save(docx_path)
    if missing_imgs:
        print(f"[warn] {len(missing_imgs)} 张图未找到：{missing_imgs[:3]}", file=sys.stderr)
    return docx_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: md2docx.py input.md output.docx [default|gongwen|compact]")
        sys.exit(1)
    print(convert(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "default"))
