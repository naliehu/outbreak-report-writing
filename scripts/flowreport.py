#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flowreport — 传染病流调报告撰写流水线（skill: outbreak-report-writing）

把「有限信息 → 报告」拆成可反复执行的六条命令；任何完成度都能出 md/docx/pdf。

    python3 flowreport.py doctor
    python3 flowreport.py init   --id FI-2026-0031 --title "…" --out work/report.json
    python3 flowreport.py status work/report.json
    python3 flowreport.py ask    work/report.json --write
    python3 flowreport.py build  work/report.json --out exports --snapshot
    python3 flowreport.py fields --level L1

设计约束：分级、排序、编号、状态机全部来自 vendor/spec/derive.py，本脚本零判断，
只做「把 derive 的结果说人话」和「串起 组装→出图→导出」。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
VENDOR = SKILL_ROOT / "vendor"
SPEC_DIR = VENDOR / "spec"
TEMPLATE = SKILL_ROOT / "templates" / "report-skeleton.json"

if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

LEVEL_ORDER = ("L1", "L2", "L3")


# ---------------------------------------------------------------- 基础设施
class Fail(RuntimeError):
    """可读的失败（不打印 traceback）。"""


def _color_enabled() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None and not os.environ.get("FLOWREPORT_NO_COLOR")


def _encodable(text: str) -> bool:
    """当前 stdout 编码能否表示该文本：中文 Windows 控制台默认 GBK，码表里没有 ✓ / ✗。"""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(enc, "strict")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _mark(ok: bool) -> str:
    """通过 / 失败标记；编码不支持时退化为 ASCII，避免 doctor 在 GBK 控制台抛 UnicodeEncodeError。"""
    fancy, plain = ("✓", "[OK]") if ok else ("✗", "[NO]")
    return fancy if _encodable(fancy) else plain


class C:
    on = _color_enabled()

    @classmethod
    def wrap(cls, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if cls.on else text

    @classmethod
    def red(cls, t): return cls.wrap("1;31", t)

    @classmethod
    def orange(cls, t): return cls.wrap("1;33", t)

    @classmethod
    def blue(cls, t): return cls.wrap("1;34", t)

    @classmethod
    def green(cls, t): return cls.wrap("1;32", t)

    @classmethod
    def dim(cls, t): return cls.wrap("2", t)

    @classmethod
    def bold(cls, t): return cls.wrap("1", t)


LEVEL_STYLE = {"L1": (C.red, "⛔"), "L2": (C.orange, "⚠️"), "L3": (C.blue, "ℹ️")}


def load_json(path: Path) -> dict:
    if not path.exists():
        raise Fail(f"文件不存在：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Fail(f"JSON 解析失败（{path}）：第 {exc.lineno} 行第 {exc.colno} 列 — {exc.msg}") from exc


def load_spec():
    try:
        from report_engine.spec import SpecBundle, EngineError
    except ImportError as exc:  # pragma: no cover
        raise Fail(f"vendor 目录不完整，找不到 report_engine：{exc}") from exc
    try:
        return SpecBundle(SPEC_DIR)
    except EngineError as exc:
        raise Fail(f"规格装载失败：{exc}") from exc


def derive(report_path: Path, spec=None) -> tuple[dict, dict, dict]:
    """返回 (report, derive result, rules)。schema 不过直接抛 Fail。"""
    spec = spec or load_spec()
    report = load_json(Path(report_path))
    errors = spec.derive.validate(report)
    if errors:
        raise Fail("schema 校验失败（先修 JSON 再谈定级）：\n" + "\n".join(f"  - {e}" for e in errors[:15]))
    res = spec.derive.build(report, spec.registry, spec.skeleton, spec.rules)
    return report, res, spec.rules


def counts_of(comp: dict) -> dict:
    return comp["missingCounts"]


def headline(comp: dict, banner: str = "") -> str:
    c = counts_of(comp)
    state = comp["state"]
    tag = {"DRAFT": C.red, "PARTIAL": C.orange, "READY": C.green}.get(state, C.bold)(f"{state} {comp['stateLabel']}")
    cov = comp["fieldCoverage"]
    return (f"状态 {tag}　缺失 L1 {c['L1']} / L2 {c['L2']} / L3 {c['L3']}（合计 {c['total']}）"
            f"　字段覆盖 {cov['present']}/{cov['instances']} = {cov['percent']}%")


# ---------------------------------------------------------------- 子命令
def cmd_doctor(args) -> int:
    rows = []
    ok_all = True

    def check(name, fn, hint=""):
        nonlocal ok_all
        try:
            detail = fn() or ""
            rows.append((True, name, detail))
        except Exception as exc:  # noqa: BLE001
            ok_all = False
            rows.append((False, name, f"{exc} {hint}".strip()))

    check("python", lambda: f"{sys.version.split()[0]} @ {sys.executable}")

    def _ver(name):
        from importlib.metadata import version
        return version(name)

    check("jsonschema", lambda: _ver("jsonschema"))
    check("python-docx", lambda: _ver("python-docx"))
    check("matplotlib", lambda: _ver("matplotlib"))
    check("pypdf", lambda: _ver("pypdf"))

    def _soffice():
        exe = (os.environ.get("SOFFICE_BIN") or shutil.which("soffice")
               or shutil.which("libreoffice"))
        if not exe:
            for cand in ("/Applications/LibreOffice.app/Contents/MacOS/soffice",
                         r"C:\Program Files\LibreOffice\program\soffice.exe",
                         r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
                if Path(cand).exists():
                    exe = cand
                    break
        if not exe:
            raise RuntimeError("未安装 → 只能出 md/docx，PDF 需 LibreOffice")
        return exe

    check("LibreOffice(soffice)", _soffice, "（只影响 PDF）")

    def _spec():
        s = load_spec()
        return f"{len(s.fields)} 字段 / {len(s.sections)} 章 / schema {s.schema.get('$id', 'ok')}"

    check("规格包 vendor/spec", _spec)

    def _fonts():
        import matplotlib.font_manager as fm
        names = {f.name for f in fm.fontManager.ttflist}
        hit = sorted(n for n in ("Songti SC", "Heiti SC", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "SimHei") if n in names)
        if not hit:
            raise RuntimeError("未找到中文字体 → 图内汉字会变方框")
        return "、".join(hit[:3])

    check("matplotlib 中文字体", _fonts)

    for good, name, detail in rows:
        mark = C.green(_mark(True)) if good else C.red(_mark(False))
        print(f" {mark} {name:<22} {detail}")
    if not ok_all:
        print("\n" + C.orange("有检查项未通过：md/docx 仍可出；PDF 需 soffice，图需 matplotlib 中文字体。"))
    return 0 if ok_all else 1


def cmd_init(args) -> int:
    out = Path(args.out).expanduser()
    if out.exists() and not args.force:
        raise Fail(f"目标已存在：{out}（确实要覆盖加 --force）")
    raw = load_json(TEMPLATE)
    case = raw["cases"][0]
    raw["reportId"] = args.id
    raw["meta"]["title"] = args.title
    raw["meta"]["institution"] = args.institution
    raw["meta"]["reportDate"] = args.report_date
    raw["meta"]["reportVersion"] = args.version
    if args.disease:
        raw["outbreak"]["diseaseName"] = args.disease
    if args.case_key:
        case["key"] = args.case_key
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(C.green(f"已创建最小可用报告：{out}"))
    print(C.dim("  1 例 + 报告头即可起报；其余一律按缺失项显性标注，不猜值。"))
    print("下一步：")
    print(f"  python3 {_self()} ask {out}          # 看该问什么，按 L1 → L3")
    print(f"  python3 {_self()} build {out} --out exports   # 现在就导出草稿")
    return 0


def _self() -> str:
    return str(Path(__file__).resolve())


def _print_warnings(warnings) -> None:
    if not warnings:
        return
    groups: dict[str, list[str]] = {}
    for w in warnings:
        groups.setdefault(w.split(":", 1)[0], []).append(w)
    print("\n" + C.orange("告警："))
    for code, items in sorted(groups.items()):
        if code == "W-EMPTY-ARRAY":
            print(f"  · 空数组 {len(items)} 处：未申报 NONE 的按缺失计（已核实确为无 → 该对象 presence 写 NONE + presenceNote）")
            print(C.dim("    " + "、".join(x.split(":", 1)[1] for x in items[:6]) + ("…" if len(items) > 6 else "")))
        elif code == "W-STALE-PRESENCE":
            print(f"  · 状态过期 {len(items)} 处：值已填但 presence 还写着 MISSING/UNKNOWN → 删掉 presence 条目")
            print(C.dim("    " + "、".join(x.split(":", 1)[1] for x in items[:6]) + ("…" if len(items) > 6 else "")))
        else:
            for w in items:
                print(f"  · {w}")


def cmd_status(args) -> int:
    report, res, rules = derive(args.report)
    comp = res["completeness"]
    if args.json:
        print(json.dumps({"completeness": comp, "banner": res["banner"], "warnings": res["warnings"]},
                         ensure_ascii=False, indent=2))
        return 0
    print(C.bold(f"{report['reportId']} {report['meta']['title']}"))
    print(f"版本 {report['meta']['reportVersion']}　核对 {comp['computedAt']}")
    print(headline(comp))
    print(C.dim(res["banner"]))
    print(f"NA {res['naCount']}　已核实为无 {res['noneCount']}")
    if comp["readinessBlockers"]:
        print("\n" + C.red("定稿阻断项（readinessBlockers）："))
        for b in comp["readinessBlockers"]:
            print(f"  · {b}")
    missing = comp["missing"]
    if not missing:
        print("\n" + C.green("无缺失：L1/L2/L3 均为 0，可作确定性研判（READY）。"))
    for lvl in LEVEL_ORDER:
        items = [m for m in missing if m["level"] == lvl]
        if not items:
            continue
        style, icon = LEVEL_STYLE[lvl]
        lv_name = rules["levels"][lvl]["name"]
        target = rules["levels"][lvl]["responseTarget"]
        header = f"{icon} {lvl} {lv_name}　{len(items)} 项　时效：{target}"
        print("\n" + style(header))
        for m in items[: args.top]:
            print(f"  {m['id']} {m['path']}　{m['label']}　[{m['state']}]")
        if len(items) > args.top:
            print(C.dim(f"  … 其余 {len(items) - args.top} 项见 `ask`"))
    if missing:
        first = missing[0]
        print("\n" + C.bold("下一步：") + f"先补 {first['id']} {first['path']}（{first['label']}）—— "
              f"{(first['ask'] or '').split('。')[0]}。")
    if res["warnings"]:
        _print_warnings(res["warnings"])
    if args.write:
        out = Path(args.report).with_suffix(".computed.json")
        payload = dict(report)
        payload["completeness"] = comp
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(C.dim(f"已回写 completeness：{out}"))
    return 0


def _group_by_level_and_section(items, spec, lvl_filter, sec_filter):
    sec_title = {s["id"]: s["title"] for s in spec.sections}
    out = []
    for lvl in LEVEL_ORDER:
        if lvl_filter and lvl not in lvl_filter:
            continue
        bucket = [m for m in items if m["level"] == lvl]
        if sec_filter:
            bucket = [m for m in bucket if m["section"] in sec_filter]
        if not bucket:
            continue
        groups = []
        for sec in sorted({m["section"] for m in bucket}, key=lambda s: next(
                (x["order"] for x in spec.sections if x["id"] == s), 99)):
            rows = [m for m in bucket if m["section"] == sec]
            groups.append((sec, sec_title.get(sec, sec), rows))
        out.append((lvl, groups))
    return out


def _worklist_markdown(report, comp, res, rules, spec) -> str:
    c = counts_of(comp)
    state = comp["state"]
    L = []
    L.append(f"# 待补信息工单 — {report['reportId']} {report['meta']['title']}")
    L.append("")
    L.append(f"- 报告版本：{report['meta']['reportVersion']}　核对时间：{comp['computedAt']}")
    L.append(f"- 当前状态：**{state} {comp['stateLabel']}**　字段覆盖 {comp['fieldCoverage']['percent']}%")
    L.append(f"- 缺失：**L1 {c['L1']} 项 / L2 {c['L2']} 项 / L3 {c['L3']} 项**（合计 {c['total']} 项）")
    L.append("")
    L.append("> 级别含义：L1 缺则无法切断传播/确定管控范围；L2 缺则结论方向可能反转；L3 只影响文字完整性。"
             "同一级别内按章节顺序排列，编号 M-xxxx 与报告第十部分一一对应。")
    L.append("")
    for lvl, groups in _group_by_level_and_section(comp["missing"], spec, None, None):
        meta = rules["levels"][lvl]
        icon = meta["render"]["icon"]
        L.append(f"## {icon} {lvl} {meta['name']}（{sum(len(g[2]) for g in groups)} 项）— {meta['responseTarget']}")
        L.append("")
        L.append(f"判定口径：{meta['definition']}")
        L.append("")
        for sec, title, rows in groups:
            L.append(f"### {title}")
            L.append("")
            L.append("| 编号 | 字段 | 位置 | 状态 | 怎么补 | 不补的后果 |")
            L.append("| --- | --- | --- | --- | --- | --- |")
            for m in rows:
                note = f"（{m['stateNote']}）" if m.get("stateNote") else ""
                ask = (m.get("ask") or "").replace("|", "\\|")
                cons = (m.get("consequence") or "").replace("|", "\\|")
                esc = " ↑冲突升级" if m.get("escalated") else ""
                L.append(f"| {m['id']} | {m['label']} | `{m['path']}` | {m['state']}{esc}{note} | {ask} | {cons} |")
            L.append("")
    if comp["readinessBlockers"]:
        L.append("## 定稿阻断项")
        L.append("")
        for b in comp["readinessBlockers"]:
            L.append(f"- {b}")
        L.append("")
    L.append("---")
    L.append("")
    L.append("补齐办法：直接改报告 JSON 里对应路径的值（拿不到就写 `presence` 状态 + `presenceNote` 说明谁说的不知情），"
             "然后重跑 `flowreport status` 看级别是否下降；不要为了消掉提示而填占位值。")
    return "\n".join(L)


def cmd_ask(args) -> int:
    spec = load_spec()
    report, res, rules = derive(args.report, spec)
    comp = res["completeness"]
    lvl_filter = {x.strip().upper() for x in args.level.split(",")} if args.level else None
    sec_filter = {x.strip() for x in args.section.split(",")} if args.section else None
    grouped = _group_by_level_and_section(comp["missing"], spec, lvl_filter, sec_filter)

    if args.json:
        payload = {"reportId": report["reportId"], "state": comp["state"],
                   "missingCounts": counts_of(comp), "items": comp["missing"]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        c = counts_of(comp)
        print(C.bold(f"待补信息工单 {report['reportId']}　{c['L1']} 阻断 / {c['L2']} 研判 / {c['L3']} 叙述"))
        if not grouped:
            print(C.green("没有符合条件的缺失项。"))
        for lvl, groups in grouped:
            style, icon = LEVEL_STYLE[lvl]
            meta = rules["levels"][lvl]
            total = sum(len(g[2]) for g in groups)
            print("\n" + style(f"{'=' * 8} {icon} {lvl} {meta['name']} {total} 项　{meta['responseTarget']} {'=' * 8}"))
            for sec, title, rows in groups:
                print(C.bold(f"  [{title}]"))
                for m in rows[: args.limit] if args.limit else rows:
                    esc = C.red(" ↑冲突升级") if m.get("escalated") else ""
                    print(f"   {m['id']} {m['path']}　{m['label']}　[{m['state']}]{esc}")
                    note = f"　　现场记录：{m['stateNote']}" if m.get("stateNote") else ""
                    if note:
                        print(C.dim(note))
                    print(f"　　怎么补：{m.get('ask') or '—'}")
                    print(f"　　不补的后果：{m.get('consequence') or '—'}")
            if args.limit:
                hidden = sum(len(g[2]) for g in groups) - sum(min(len(g[2]), args.limit) for g in groups)
                if hidden > 0:
                    print(C.dim(f"  … 本级另有 {hidden} 项未展开（去掉 --limit 看全）"))

    if args.write:
        path = Path(args.write).expanduser() if isinstance(args.write, str) else \
            Path(args.report).with_name("待补信息工单.md")
        path = path if path.suffix else path.with_suffix(".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_worklist_markdown(report, comp, res, rules, spec), encoding="utf-8")
        print(C.green(f"\n已写出工单：{path}"))
    return 0


def cmd_fields(args) -> int:
    spec = load_spec()
    levels = {args.level} if args.level else None
    rows = [f for f in spec.registry["fields"]
            if (not levels or f["level"] in levels) and (not args.entity or f["entity"] == args.entity)]
    for f in rows:
        print(f"{f['level']}  {f['id']:<40} {f.get('label', '')}"
              + (f"　（{f['entity']}）" if not args.entity else ""))
    print(C.dim(f"\n共 {len(rows)} 个字段。完整台账见 vendor/spec/field-registry.json"))
    return 0


def _dedupe_placeholder_notices(doc: dict) -> list[str]:
    """删掉与章首占位说明重复的告警条（上游 compose 在章节不可渲染时会同时给出
    占位说明「…待补：X」与告警「X」，同一句话印两遍）。

    只在 renderable=False 的章节内、且告警正文被占位说明正文完整包含时才删；
    不含新信息的重复去掉，含新信息的（如「曲线不完全：1 例…」）保留。
    """
    dropped = []

    def _plain(t: str) -> str:
        return str(t or "").strip().strip("（）()").strip()

    for sec in doc.get("blocks") or []:
        if sec.get("type") != "section" or sec.get("renderable", True):
            continue
        blocks = sec.get("blocks") or []
        holders = [b for b in blocks if b.get("type") == "notice" and b.get("kind") == "placeholder"]
        if not holders:
            continue
        holder_text = "".join(_plain(b.get("text")) for b in holders)
        keep = []
        for b in blocks:
            if (b.get("type") == "notice" and b.get("kind") != "placeholder"
                    and b not in holders and _plain(b.get("text")) and _plain(b.get("text")) in holder_text):
                dropped.append(f"{sec.get('id')}：{_plain(b.get('text'))[:40]}")
                continue
            keep.append(b)
        sec["blocks"] = keep
    return dropped


def cmd_build(args) -> int:
    spec = load_spec()
    report_path = Path(args.report).expanduser().resolve()
    report, res, rules = derive(report_path, spec)
    comp = res["completeness"]

    from report_engine import ReportEngine
    from report_export import export_report, save_snapshot
    from report_export import astmodel

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = ReportEngine(spec_dir=SPEC_DIR)
    build = engine.build(str(report_path), formats=("md", "html", "ast"))
    doc = build.document

    # 录入卫生提示（空数组）不放在报告封面上：它说的是「还没填」，而同一件事在第十部分
    # 已经作为缺失项显性列出；留在封面只会让草稿页多一行机器话。终端仍照常打印。
    hidden_entry_hints = []
    if not args.keep_entry_warnings:
        warns = (doc.get("meta") or {}).get("warnings")
        if isinstance(warns, list):
            kept = []
            for w in warns:
                if str(w).startswith("W-EMPTY-ARRAY"):
                    hidden_entry_hints.append(w)
                else:
                    kept.append(w)
            doc["meta"]["warnings"] = kept
    if hidden_entry_hints and not args.json:
        print(C.dim("已从封面移除录入提示：" + "；".join(hidden_entry_hints) + "（内容仍见第十部分）"))

    deduped = _dedupe_placeholder_notices(doc)
    if deduped and not args.json:
        print(C.dim(f"已合并 {len(deduped)} 处与章首占位说明重复的告警行"))

    asset_info = {}
    if not args.no_figures:
        try:
            import flowfig
            from flowfig import integrate as flow_integrate
        except ImportError as exc:
            raise Fail(f"找不到 flowfig（vendor 不完整）：{exc}") from exc
        bundle = flowfig.generate_file(report_path, out_dir / "figures")
        build = flow_integrate.attach_build_result(build, bundle, rel_prefix="assets", img_format="png")
        doc = build.document
        slots = bundle.slots()
        asset_info = {"figures": len(slots), "dir": str(out_dir / "figures")}
        if not args.json:
            print(C.dim(f"四图：{bundle.summary_line()}"))
            for slot, s in slots.items():
                for g in s.get("gaps") or []:
                    print(C.orange(f"  {slot} 缺口 {g.get('level')}：{g.get('label') or g.get('note')}"))
                    if g.get("captionSuffix"):
                        print(C.dim(f"    图注已限定：{g['captionSuffix']}"))

    doc, _ = astmodel.resolve_assets(doc, [VENDOR, out_dir])
    formats = tuple(x.strip().lower() for x in args.formats.replace("，", ",").split(",") if x.strip())
    result = export_report(doc, out_dir, formats=formats, name=args.name,
                           base_dirs=[out_dir / "figures", VENDOR], verify=not args.no_verify,
                           section_page_break=args.section_page_break)

    if args.json:
        print(json.dumps({"state": comp["state"], "missingCounts": counts_of(comp),
                          "files": {k: str(v) for k, v in result.files.items()},
                          "checks": result.checks, "ok": result.ok}, ensure_ascii=False, indent=2))
    else:
        print()
        print(C.bold(f"{report['reportId']} {report['meta']['reportVersion']}　{report['meta']['title']}"))
        print(headline(comp))
        for fmt, path in result.files.items():
            print(f"  {fmt:<5} {path}")
        for name, check in result.checks.items():
            mark = C.green(_mark(True)) if check.get("pass") else C.red(_mark(False))
            extra = ""
            if name == "pdf":
                extra = f"　{check.get('pages')} 页 / 图 {check.get('images')} / 汉字 {check.get('cjk')}"
            elif name == "docx":
                extra = f"　内嵌图 {check.get('inlineImages')} / 表 {check.get('tables')}"
            elif name == "consistency":
                extra = "　" + " ".join(f"{k}={v.get('ratio')}" for k, v in (check.get("perFormat") or {}).items())
            print(f"  [{mark}] {name}{extra}")
        if not result.ok:
            print(C.red(f"  导出自检未全通过：见上方 {_mark(False)} 项与 warnings"))
        for w in result.warnings:
            print(C.orange(f"  ! {w}"))

    if args.snapshot:
        snap = save_snapshot(doc, out_dir, formats=formats, note=args.note, verify=False)
        print(C.dim(f"快照 {snap.id} → {snap.dir}"))

    if comp["state"] != "READY":
        c = counts_of(comp)
        print(C.dim(f"\n这是 {comp['state']} 版本，已可交付使用；剩余 L1 {c['L1']} / L2 {c['L2']} / L3 {c['L3']}，"
                    f"`ask` 看补采清单。"))
    return 0 if result.ok else 1


def cmd_gate(args) -> int:
    """签发门禁：状态机 READY 只代表「无 L1、无冲突、可渲染」，不等于可以签发。

    内部上报看 L1；对外签发/定稿看 L2（默认）。
    """
    report, res, rules = derive(args.report)
    comp = res["completeness"]
    c = counts_of(comp)
    require = args.require.upper()
    conflict = [m for m in comp["missing"] if m["state"] == "CONFLICT"]
    checks = []
    checks.append(("L1 阻断传播缺失 = 0", c["L1"], c["L1"] == 0))
    if require in ("L2", "L3"):
        checks.append(("L2 影响研判缺失 = 0", c["L2"], c["L2"] == 0))
    if require == "L3":
        checks.append(("L3 完善叙述缺失 = 0", c["L3"], c["L3"] == 0))
    checks.append(("CONFLICT 多源矛盾 = 0", len(conflict), not conflict))
    ok = all(x[2] for x in checks)

    print(C.bold(f"签发门禁 — {report['reportId']} {report['meta']['reportVersion']}　要求级别 {require}"))
    print(C.dim(f"报告状态 {comp['state']} {comp['stateLabel']}（状态机 READY ≠ 可签发，签发看本门禁）"))
    for label, value, passed in checks:
        mark = C.green(_mark(True)) if passed else C.red(_mark(False))
        print(f"  {mark} {label}　实际 {value}")
    if ok:
        print("\n" + C.green(f"通过：按 {require} 口径可签发。"))
        print(C.dim("建议声明：" + comp["declaration"]))
        return 0

    print("\n" + C.red("未通过，以下项必须先处理："))
    for lvl in LEVEL_ORDER:
        if require == "L1" and lvl != "L1":
            continue
        if require == "L2" and lvl == "L3":
            continue
        rows = [m for m in comp["missing"] if m["level"] == lvl and m["state"] != "CONFLICT"]
        for m in rows:
            print(f"  {m['id']} {lvl} {m['path']}　{m['label']}")
    for m in conflict:
        print(f"  {m['id']} L{m['level'][-1]} {m['path']}　{m['label']}　〔CONFLICT：{m.get('stateNote') or '多源不一致'}〕")
    print(C.dim("\n要么补齐，要么在报告第九/十部分写明未受控风险与替代核实结论；不要改状态字段绕过门禁。"))
    return 3


def cmd_snaps(args) -> int:
    from report_export import snapshot
    rows = snapshot.list_snapshots(args.out)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("没有快照。build 时加 --snapshot 即可留档。")
        return 0
    print(f"{'ID':<30}{'状态':<10}{'覆盖':>7}{'提示':>5}  说明")
    for r in rows:
        st = r.get("stats") or {}
        print(f"{r.get('id', ''):<30}{r.get('state', ''):<10}"
              f"{str(st.get('coverage', '-')):>7}{str(st.get('hintTotal', '-')):>5}  {r.get('note') or ''}")
    return 0


def cmd_diff(args) -> int:
    from report_export import snapshot
    d = snapshot.diff_snapshots(args.out, args.a, args.b)
    print(f"{d['from']}  →  {d['to']}")
    print(f"  状态   {d['state']['from']} → {d['state']['to']}")
    print(f"  缺失   {d['missingCounts']['from']} → {d['missingCounts']['to']}")
    print(f"  覆盖率 {d['coverage']['from']}% → {d['coverage']['to']}%")
    if d["hintsResolved"]:
        print("  已补齐 " + "；".join(d["hintsResolved"]))
    if d["hintsAdded"]:
        print("  新增缺失 " + "；".join(d["hintsAdded"]))
    return 0


# ---------------------------------------------------------------- 入口
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="flowreport", description="流调报告撰写流水线")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="依赖自检").set_defaults(func=cmd_doctor)

    i = sub.add_parser("init", help="建最小可用报告骨架（1 例即可起报）")
    i.add_argument("--out", required=True, help="输出 JSON 路径")
    i.add_argument("--id", required=True, help="报告编号，如 FI-2026-0031")
    i.add_argument("--title", required=True, help="报告标题")
    i.add_argument("--institution", default="某市疾病预防控制中心")
    i.add_argument("--report-date", default=None, help="默认今天")
    i.add_argument("--version", default="v0.1")
    i.add_argument("--disease", default=None, help="疾病名称（已知则填）")
    i.add_argument("--case-key", default="C-01")
    i.add_argument("--force", action="store_true")
    i.set_defaults(func=cmd_init)

    s = sub.add_parser("status", help="状态 / 覆盖率 / 缺失分级 / Top 待补")
    s.add_argument("report")
    s.add_argument("--top", type=int, default=3, help="每级展开几条（默认 3）")
    s.add_argument("--write", action="store_true", help="把 completeness 回写到 *.computed.json")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)

    a = sub.add_parser("ask", help="分级补采工单（含问法与不补的后果）")
    a.add_argument("report")
    a.add_argument("--level", default=None, help="L1,L2,L3 子集")
    a.add_argument("--section", default=None, help="章节 id 子集，如 case_discovery")
    a.add_argument("--limit", type=int, default=0, help="每组最多展开几条")
    a.add_argument("--write", nargs="?", const=True, default=None, metavar="PATH",
                   help="写出 Markdown 工单（不带路径则写到报告同目录）")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_ask)

    f = sub.add_parser("fields", help="字段台账速查")
    f.add_argument("--level", default=None)
    f.add_argument("--entity", default=None)
    f.set_defaults(func=cmd_fields)

    b = sub.add_parser("build", help="组装 + 出四图 + 导出 md/docx/pdf（任意完成度）")
    b.add_argument("report")
    b.add_argument("--out", required=True)
    b.add_argument("--formats", default="md,docx,pdf")
    b.add_argument("--name", default=None, help="输出文件名主干，默认 <reportId>-<version>")
    b.add_argument("--no-figures", action="store_true", help="只出文字，不出图")
    b.add_argument("--snapshot", action="store_true", help="存一份阶段快照")
    b.add_argument("--note", default=None)
    b.add_argument("--no-verify", action="store_true")
    b.add_argument("--section-page-break", action="store_true", help="每章另起一页")
    b.add_argument("--keep-entry-warnings", action="store_true",
                   help="保留封面上的 W-EMPTY-ARRAY 录入提示（默认移除，第十部分仍列出）")
    b.add_argument("--json", action="store_true")
    b.set_defaults(func=cmd_build)

    g = sub.add_parser("gate", help="签发门禁：按级别核对是否可签发（READY ≠ 可签发）")
    g.add_argument("report")
    g.add_argument("--require", default="L2", choices=["L1", "L2", "L3"],
                   help="内部上报用 L1，对外签发用 L2（默认），追求零缺用 L3")
    g.set_defaults(func=cmd_gate)

    sp = sub.add_parser("snaps", help="列出快照")
    sp.add_argument("--out", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_snaps)

    df = sub.add_parser("diff", help="对比两次快照（补齐了哪些）")
    df.add_argument("a")
    df.add_argument("b")
    df.add_argument("--out", required=True)
    df.set_defaults(func=cmd_diff)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.func is cmd_init and getattr(args, "report_date", None) is None:
        from datetime import date
        args.report_date = date.today().isoformat()
    try:
        return args.func(args)
    except Fail as exc:
        print(C.red(f"失败：{exc}"), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
