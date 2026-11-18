#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
epi_viz.py —— 流调报告图集生成器

统一规范（与《传染病流调报告撰写技能》一致）：
- 流行曲线用柱状（不给折线），柱宽=时间间隔，间隔默认取最长潜伏期的 1/4~1/3
- 无网格线、无渐变、无阴影；坐标轴只留左、下；字号 ≥8pt，标题 11pt 加粗
- 300 dpi PNG，物理宽度 16cm，可直接插入 A4 文档
- 关键时点（停课、消毒、应急接种、末例隔离）以竖虚线+文字标注
"""
from __future__ import annotations

import datetime as dt
import os
import re
from collections import Counter, OrderedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyArrowPatch
import numpy as np

# ------------------------------------------------------------------ 样式

CJK_CANDIDATES = ["Songti SC", "Heiti SC", "STSong", "Hiragino Sans GB",
                  "Arial Unicode MS", "PingFang SC", "Noto Sans CJK SC", "SimHei"]
_FONT = None


def _font():
    global _FONT
    if _FONT:
        return _FONT
    import matplotlib.font_manager as fm
    names = {f.name for f in fm.fontManager.ttflist}
    for c in CJK_CANDIDATES:
        if c in names:
            _FONT = c
            break
    _FONT = _FONT or "sans-serif"
    return _FONT


INK = "#1a1a1a"
BAR = "#3f6f8f"
BAR2 = "#8fa9bb"
ACCENT = "#b03a2e"
GRAY = "#7f7f7f"

# 图内是否画标题：报告里由「图N　题注」统一说明，图内不重复
SHOW_TITLE = False


def _apply_rc():
    """模块导入时即设定字体与字号——Text 对象在创建时固化字体，事后改了不生效。"""
    f = _font()
    plt.rcParams.update({
        "font.family": f, "axes.unicode_minus": False,
        "font.size": 9, "axes.linewidth": 0.8,
        "axes.edgecolor": INK, "axes.labelcolor": INK,
        "xtick.color": INK, "ytick.color": INK,
        "figure.dpi": 300, "savefig.dpi": 300,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.06,
    })


def style(ax, title=None, xlabel=None, ylabel=None, width_cm=16):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(False)
    ax.tick_params(direction="out", length=3, width=0.7, labelsize=8)
    if title and SHOW_TITLE:
        ax.set_title(title, fontsize=11, fontweight="bold", color=INK, pad=8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9)
    return ax


_apply_rc()


def _save(fig, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=300, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


# ------------------------------------------------------------ 1 流行曲线

def epicurve(bins, bin_hours, path, title="病例发病时间分布",
             events=None, first_dt=None, last_dt=None, note=None):
    """bins: [(datetime, count)]；events: [(datetime, '文字')] 关键干预时点。

    横轴刻点由程序显式指定（不交给 AutoDateLocator），避免出现只标年月的
    稀疏刻度；右侧零值柱自动裁掉，避免尾部空白。
    """
    if not bins:
        return None
    # 裁掉末尾连续零值柱（保留 1 个）
    last_nz = max([i for i, b in enumerate(bins) if b[1] > 0] or [0])
    bins = bins[: min(len(bins), last_nz + 2)]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    xs = [b[0] for b in bins]
    ys = [b[1] for b in bins]
    step = dt.timedelta(hours=bin_hours)
    ax.bar(xs, ys, width=step * 0.85, color=BAR, edgecolor="white", linewidth=0.6, align="edge")
    ymax = max(ys) or 1
    ax.set_ylim(0, ymax * 1.22)
    for x, y in zip(xs, ys):
        if y > 0:
            ax.text(x + step * 0.42, y + ymax * 0.02, str(int(y)), ha="center",
                    va="bottom", fontsize=7.5, color=INK)
    style(ax, title, "发病时间", "病例数")

    # 显式刻点
    span_days = max(1, (xs[-1] - xs[0]).days + 1)
    k = max(1, int(np.ceil(len(xs) / 9.0)))
    tick_idx = list(range(0, len(xs), k))
    if (len(xs) - 1) not in tick_idx:
        tick_idx.append(len(xs) - 1)
    span_all = (bins[-1][0] - bins[0][0]).days
    fmt = "%Y-%m" if span_all > 400 else ("%m-%d %H时" if bin_hours < 24 else "%m-%d")
    ax.set_xticks([xs[i] + step * 0.5 for i in tick_idx])
    ax.set_xticklabels([xs[i].strftime(fmt) for i in tick_idx],
                       rotation=45, ha="right", fontsize=7.5)
    ax.set_xlim(xs[0], xs[-1] + step)

    # 首末例标记：贴在所属柱子的顶端
    def _mark(d, text):
        if not isinstance(d, dt.datetime):
            return
        idx = int((d - xs[0]).total_seconds() // (bin_hours * 3600))
        if idx < 0 or idx >= len(xs):
            return
        ax.text(xs[idx] + step * 0.42, ys[idx] + ymax * 0.10, text,
                ha="center", va="bottom", fontsize=7, color=GRAY)
    if first_dt:
        _mark(first_dt, "首例")
    if last_dt:
        _mark(last_dt, "末例")

    if events:
        for i, (d, txt) in enumerate(events):
            if not isinstance(d, dt.datetime):
                continue
            ax.axvline(d, color=ACCENT, ls=(0, (4, 3)), lw=0.9, alpha=0.85, zorder=1)
            ax.text(d, ax.get_ylim()[1] * (0.90 - 0.10 * i), " " + txt, color=ACCENT,
                    fontsize=7, va="top", ha="left")
    if note:
        fig.text(0.01, -0.02, note, fontsize=7, color=GRAY)
    return _save(fig, path)


# -------------------------------------------------- 2 班级/单位分布 + 罹患率

def group_bar(rows, path, title="班级分布", xlabel="班级", ylabel="病例数"):
    rows = [r for r in rows if r["group"] != "不详"]
    if not rows:
        return None
    rows = rows[:30]
    labels = [r["group"] for r in rows]
    vals = [r["cases"] for r in rows]
    has_rate = any(r.get("rate") for r in rows)
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    x = np.arange(len(rows))
    ax.bar(x, vals, color=BAR, edgecolor="white", linewidth=0.6, width=0.68)
    for i, v in enumerate(vals):
        ax.text(i, v + max(vals) * 0.02, str(v), ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=7.5)
    ax.set_ylim(0, max(vals) * 1.25 + 0.5)
    style(ax, title, xlabel, ylabel)
    if has_rate:
        ax2 = ax.twinx()
        rates = [r.get("rate") or 0 for r in rows]
        ax2.plot(x, rates, color=ACCENT, marker="o", ms=3.2, lw=1.0, zorder=5)
        ax2.set_ylabel("罹患率（%）", fontsize=8.5, color=ACCENT)
        ax2.tick_params(axis="y", labelcolor=ACCENT, labelsize=8)
        ax2.spines["top"].set_visible(False)
        ax2.grid(False)
        ax2.set_ylim(0, max(rates) * 1.35 + 1)
        ax2.legend(["罹患率"], loc="upper left", fontsize=7.5, frameon=False)
    return _save(fig, path)


# -------------------------------------------------------- 3 年龄性别分布

def age_sex(age_map, path, title="病例年龄性别分布"):
    if not age_map:
        return None
    bands = list(age_map.keys())
    male = [age_map[b]["男"] for b in bands]
    female = [age_map[b]["女"] for b in bands]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    y = np.arange(len(bands))
    ax.barh(y, [-m for m in male], color=BAR, height=0.62, label="男")
    ax.barh(y, female, color=BAR2, height=0.62, label="女")
    ax.set_yticks(y)
    ax.set_yticklabels(bands, fontsize=8)
    for i, (m, f) in enumerate(zip(male, female)):
        if m:
            ax.text(-m, i, f" {m}", ha="right", va="center", fontsize=7.5)
        if f:
            ax.text(f, i, f" {f}", ha="left", va="center", fontsize=7.5)
    ax.axvline(0, color=INK, lw=0.8)
    lim = max(max(male or [0]), max(female or [0])) * 1.35 + 0.5
    ax.set_xlim(-lim, lim)
    import matplotlib.ticker as mt
    ax.xaxis.set_major_formatter(mt.FuncFormatter(lambda t, _p: f"{abs(int(t))}"))
    style(ax, title, "病例数", "年龄（岁）")
    ax.legend(fontsize=8, frameon=False, loc="lower right")
    return _save(fig, path)


# ------------------------------------------------------------ 4 传播链

def transmission_chain(nodes, edges, path, title="病例传播链示意"):
    """
    nodes: [{"id","name","onset","gen","type"(确诊/临床/疑似),"isolated"}]
    edges: [{"from","to","certain":bool,"label"}]
    实线=流行病学与时间关系均支持；虚线=可能/待核实。
    """
    if not nodes:
        return None
    by_gen = OrderedDict()
    for n in nodes:
        by_gen.setdefault(n.get("gen", 1), []).append(n)
    fig, ax = plt.subplots(figsize=(6.6, max(2.6, 0.95 * len(by_gen) + 1.3)))
    pos = {}
    xmax = max([n["onset"] for n in nodes if n.get("onset")] or [dt.datetime.now()])
    xmin = min([n["onset"] for n in nodes if n.get("onset")] or [dt.datetime.now()])
    for g, ns in by_gen.items():
        ns.sort(key=lambda n: n.get("onset") or xmin)
        for i, n in enumerate(ns):
            pos[n["id"]] = (n.get("onset") or xmin, g)
    for n in nodes:
        x, y = pos[n["id"]]
        col = {"确诊": ACCENT, "实验室确诊": ACCENT, "临床诊断": BAR, "疑似": GRAY}.get(n.get("type", ""), BAR)
        ax.scatter([x], [y], s=110, color=col, edgecolor="white", linewidth=1.1, zorder=4)
        lab = f"{n.get('name','')}"
        ax.annotate(lab, (x, y), xytext=(0, 11), textcoords="offset points",
                    ha="center", fontsize=7.5, color=INK)
    for e in edges:
        a, b = pos.get(e["from"]), pos.get(e["to"])
        if not a or not b:
            continue
        ls = "-" if e.get("certain", True) else (0, (3, 2.5))
        arr = FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=9,
                              color=INK if e.get("certain", True) else GRAY,
                              lw=1.0, linestyle=ls,
                              shrinkA=9, shrinkB=9, connectionstyle="arc3,rad=0.12", zorder=3)
        ax.add_patch(arr)
        if e.get("label"):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.16
            ax.text(mx, my, e["label"], fontsize=6.5, color=GRAY, ha="center")
    ax.set_yticks(list(by_gen.keys()))
    ax.set_yticklabels([f"第{g}代" for g in by_gen.keys()], fontsize=8.5)
    ax.set_ylim(0.5, len(by_gen) + 0.55)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right", fontsize=7.5)
    style(ax, title, "发病日期", "传播代际")
    ax.text(0.995, -0.26, "实线：时间与接触史均支持；虚线：可能或待核实",
            transform=ax.transAxes, ha="right", fontsize=6.8, color=GRAY)
    return _save(fig, path)


# ------------------------------------------------------------ 5 代际图

def generation_steps(cases, latent_common_days, path, title="病例代际分布"):
    """按发病时间阶梯化的代际示意（无需接触史，仅时间结构）。"""
    pts = sorted([(c["onset_dt"], i, c) for i, c in enumerate(cases) if c.get("onset_dt")],
                 key=lambda x: (x[0], x[1]))
    if len(pts) < 4 or not latent_common_days:
        return None
    gap = latent_common_days * 0.6
    gens, gen, last = [], 1, pts[0][0]
    for o, _i, c in pts:
        if (o - last).total_seconds() / 86400 >= gap:
            gen += 1
            last = o
        gens.append((o, gen))
    if gen < 2 or gen > 8:
        return None
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    for o, g in gens:
        ax.scatter([o], [g], s=42, color=BAR, alpha=0.85, edgecolor="white", linewidth=0.6)
    ax.set_yticks(range(1, gen + 1))
    ax.set_yticklabels([f"第{g}代" for g in range(1, gen + 1)], fontsize=8.5)
    ax.set_ylim(0.4, gen + 0.6)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right", fontsize=7.5)
    style(ax, title, "发病日期", "代际")
    ax.text(0.99, 0.02, f"分代阈值：相邻代间隔≥{gap:.1f}天（约0.6×常见潜伏期）",
            transform=ax.transAxes, ha="right", fontsize=6.8, color=GRAY)
    return _save(fig, path)


# -------------------------------------------------------- 6 地理分布示意

def geo_dist(rows, path, title="病例地理分布", xlabel="村/社区/单位", ylabel="病例数",
             points=None):
    """rows=[(地名, 例数)]；points=[(lat, lon, n)] 有经纬度时画标点示意图。"""
    if points:
        fig, ax = plt.subplots(figsize=(5.4, 4.2))
        for lat, lon, n in points:
            ax.scatter([lon], [lat], s=40 + 60 * (n or 1), color=ACCENT, alpha=0.65,
                       edgecolor="white", linewidth=0.8)
            ax.annotate(str(n), (lon, lat), fontsize=7.5, ha="center", va="center", color="white")
        ax.set_xlabel("经度", fontsize=8.5)
        ax.set_ylabel("纬度", fontsize=8.5)
        ax.tick_params(labelsize=7.5)
        style(ax, title)
        ax.text(0.01, 0.01, "气泡大小=病例数（示意，非实际边界底图）",
                transform=ax.transAxes, fontsize=6.8, color=GRAY)
        return _save(fig, path)
    rows = [(k, v) for k, v in rows if k and k != "不详"][:15]
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(6.4, max(2.2, 0.32 * len(rows) + 1.2)))
    labels = [r[0] for r in rows][::-1]
    vals = [r[1] for r in rows][::-1]
    y = np.arange(len(rows))
    ax.hlines(y, 0, vals, color=BAR2, lw=1.2)
    ax.scatter(vals, y, s=52, color=BAR, zorder=3, edgecolor="white", linewidth=0.8)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.02, i, str(v), va="center", fontsize=7.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0, max(vals) * 1.22 + 0.5)
    style(ax, title, ylabel, xlabel)
    return _save(fig, path)


# -------------------------------------------------------- 7 潜伏期分布

def latent_hist(values, path, title="病例潜伏期分布"):
    if not values:
        return None
    fig, ax = plt.subplots(figsize=(6.0, 2.9))
    v = np.array(values, dtype=float)
    bins = min(14, max(5, int(len(v) ** 0.5 * 2)))
    ax.hist(v, bins=bins, color=BAR, edgecolor="white", linewidth=0.7)
    for q, lab, col in [(np.median(v), "中位数", ACCENT), (v.mean(), "均数", GRAY)]:
        ax.axvline(q, color=col, ls="--", lw=1.0)
        ax.text(q, ax.get_ylim()[1] * 0.92, f" {lab}{q:.1f}h", color=col, fontsize=7.5,
                rotation=90, va="top")
    style(ax, title, "进食至发病时间（小时）", "病例数")
    ax.text(0.99, 0.02, f"n={len(v)}，范围 {v.min():.1f}–{v.max():.1f} h",
            transform=ax.transAxes, ha="right", fontsize=7, color=GRAY)
    return _save(fig, path)


# -------------------------------------------------------- 8 症状构成

def symptom_bar(rows, n, path, title="病例症状构成"):
    if not rows:
        return None
    rows = rows[:12][::-1]
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    rates = [round(100 * r[1] / n, 1) if n else 0 for r in rows]
    fig, ax = plt.subplots(figsize=(6.0, max(2.2, 0.34 * len(rows) + 1.0)))
    y = np.arange(len(rows))
    ax.barh(y, vals, color=BAR, height=0.6)
    for i, (v, r) in enumerate(zip(vals, rates)):
        ax.text(v + max(vals) * 0.015, i, f"{v}（{r}%）", va="center", fontsize=7.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlim(0, max(vals) * 1.3)
    style(ax, title, "病例数", "")
    return _save(fig, path)


# ------------------------------------------------- 9 单例病例时间轴

def case_timeline(marks, path, title="病例关键时间节点"):
    """marks=[(datetime, 事件)] 按时间排序绘制横向时间轴。"""
    marks = [(d, t) for d, t in marks if isinstance(d, dt.datetime)]
    if len(marks) < 2:
        return None
    marks.sort()
    fig, ax = plt.subplots(figsize=(6.6, 2.3))
    xs = [m[0] for m in marks]
    ax.plot([min(xs), max(xs)], [0, 0], color=INK, lw=1.2, zorder=2)
    for i, (d, t) in enumerate(marks):
        ax.scatter([d], [0], s=70, color=ACCENT if i in (0, len(marks) - 1) else BAR,
                   edgecolor="white", linewidth=1.0, zorder=4)
        up = i % 2 == 0
        ax.annotate(t, (d, 0), xytext=(0, 26 if up else -26), textcoords="offset points",
                    ha="center", fontsize=7.5,
                    arrowprops=dict(arrowstyle="-", color=GRAY, lw=0.6))
        ax.annotate(d.strftime("%m-%d"), (d, 0), xytext=(0, 8 if up else -12),
                    textcoords="offset points", ha="center", fontsize=6.8, color=GRAY)
    ax.set_ylim(-0.6, 0.6)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7.5)
    style(ax, title)
    return _save(fig, path)


# ------------------------------------------- 10 病例-对照 OR 森林图

def case_control_forest(rows, path, title="危险因素病例对照分析（OR）"):
    """rows=[(因素, OR, lo, hi, p)]"""
    rows = [r for r in rows if r[1] is not None][:12][::-1]
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(6.4, max(2.4, 0.38 * len(rows) + 1.1)))
    for i, (name, orv, lo, hi, p) in enumerate(rows):
        col = ACCENT if (lo and lo > 1) else (BAR if not hi or hi > 1 else GRAY)
        ax.plot([lo or orv, hi or orv], [i, i], color=col, lw=1.3)
        ax.scatter([orv], [i], color=col, s=42, zorder=3)
        ax.text(hi or orv, i, f"  {orv:.2f}" + (f"（P={p}）" if p else ""), va="center", fontsize=7.4)
    ax.axvline(1, color=INK, ls="--", lw=0.9)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8.2)
    lo_all = min([r[2] or r[1] for r in rows] + [0.2])
    hi_all = max([r[3] or r[1] for r in rows] + [2])
    ax.set_xlim(lo_all * 0.8, hi_all * 1.5)
    ax.set_xscale("log")
    style(ax, title, "OR（对数刻度，虚线=1）", "")
    return _save(fig, path)


# ------------------------------------------- 11 环境/食品/水源采样

def env_sampling(rows, path, title="采样与检测结果"):
    """rows=[(类别, 份数, 阳性数)]"""
    rows = [r for r in rows if r[1]][:10]
    if not rows:
        return None
    labels = [r[0] for r in rows]
    tot = [r[1] for r in rows]
    pos = [r[2] or 0 for r in rows]
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    x = np.arange(len(rows))
    ax.bar(x, tot, color=BAR2, width=0.62, label="采样份数")
    ax.bar(x, pos, color=ACCENT, width=0.62, label="阳性份数")
    for i, (t, p) in enumerate(zip(tot, pos)):
        ax.text(i, t + max(tot) * 0.02, f"{p}/{t}", ha="center", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_ylim(0, max(tot) * 1.25)
    style(ax, title, "", "份数")
    ax.legend(fontsize=7.8, frameon=False)
    return _save(fig, path)


# ------------------------------------------- 12 应急接种进度

def vax_curve(rows, path, title="应急接种进度"):
    """rows=[(date, 累计实种)]"""
    rows = [(dt.datetime.combine(d, dt.time()) if isinstance(d, dt.date) and not isinstance(d, dt.datetime) else d, n)
            for d, n in rows if d]
    if len(rows) < 2:
        return None
    rows.sort()
    fig, ax = plt.subplots(figsize=(6.2, 2.7))
    ax.step([r[0] for r in rows], [r[1] for r in rows], where="post", color=BAR, lw=1.6)
    ax.scatter([r[0] for r in rows], [r[1] for r in rows], s=22, color=BAR, zorder=3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7.5)
    style(ax, title, "日期", "累计接种人数")
    return _save(fig, path)


# ------------------------------------------- 13 机构平面/楼层示意

def floor_map(rows, path, title="病例楼层/区域分布"):
    """rows=[(楼层或区域, 病例数, 总人数)]"""
    rows = [r for r in rows if r[0]][:14]
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(6.2, max(2.0, 0.4 * len(rows) + 1.0)))
    labels = [r[0] for r in rows][::-1]
    n = [r[1] for r in rows][::-1]
    d = [r[2] if len(r) > 2 else None for r in rows][::-1]
    y = np.arange(len(rows))
    ax.barh(y, n, color=BAR, height=0.55)
    for i, (a, b) in enumerate(zip(n, d)):
        txt = f"{a}" + (f"/{b}（{round(100*a/b,1)}%）" if b else "")
        ax.text(a + max(n) * 0.02, i, txt, va="center", fontsize=7.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0, max(n) * 1.35)
    style(ax, title, "病例数", "楼层/区域")
    return _save(fig, path)


FIGS = {
    "epicurve": epicurve, "group_bar": group_bar, "age_sex": age_sex,
    "transmission_chain": transmission_chain, "generation": generation_steps,
    "geo": geo_dist, "latent": latent_hist, "symptom": symptom_bar,
    "timeline": case_timeline, "case_control": case_control_forest,
    "env": env_sampling, "vax": vax_curve, "floor": floor_map,
}
