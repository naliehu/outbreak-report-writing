#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_report.py —— 一条命令，从有限信息生成可用的流调报告

用法
  python build_report.py --event 事件.yaml --stage initial --out ./输出
  python build_report.py --event 事件.yaml --line-list 个案-已脱敏.csv --stage final --formats md,docx,pdf
  python build_report.py --event 事件.yaml --check          # 只体检：完成度 + 待补清单

设计要点
  1. 缺什么都能出稿：任何字段缺失 → 正文插入〔待补N〕红色标记 + 附录 A 排序清单
  2. 图先算再写：根据可用字段自动决定画哪几张图，正文编号与图注由程序生成
  3. 阶段自适应：initial / progress / final / closure / case 五套骨架
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import jinja2  # noqa: E402

import epi_core as core  # noqa: E402
import epi_viz as viz  # noqa: E402
import deident  # noqa: E402  脱敏层

TPL_DIR = os.path.join(os.path.dirname(HERE), "templates")
STAGE_TPL = {
    "initial": "report_initial.md.j2",
    "progress": "report_progress.md.j2",
    "final": "report_final.md.j2",
    "closure": "closure_application.md.j2",
    "case": "report_single_case.md.j2",
}
CN_NUM = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


# ------------------------------------------------------------------ 占位符
class Pending:
    """收集待补充信息。编号按等级分册：P0-1、P0-2、P1-1……附录按 P0→P1→P2 排序，
    同一等级内保持正文出现顺序（正文顺序即调查逻辑顺序）。"""

    def __init__(self, stage="initial"):
        self.stage = stage
        self.items = []
        self.by_field = {}
        self._counter = {"P0": 0, "P1": 0, "P2": 0}
        self.frozen = False

    def __call__(self, field, desc, grade="P1"):
        if field in self.by_field:
            return self.by_field[field]["mark"]
        self._counter[grade] = self._counter.get(grade, 0) + 1
        mark = f"〔待补{grade}-{self._counter[grade]}〕"
        item = {"field": field, "desc": desc, "grade": grade, "mark": mark,
                "seq": len(self.items),
                "due": {"P0": "24小时内", "P1": "48小时内", "P2": "结案前"}[grade]}
        self.items.append(item)
        self.by_field[field] = item
        return mark


def _d(v, fmt="%Y年%-m月%-d日"):
    dtv = core.parse_date(v) if not isinstance(v, (dt.date, dt.datetime)) else v
    if not dtv:
        return "—"
    if isinstance(dtv, dt.date) and not isinstance(dtv, dt.datetime):
        dtv = dt.datetime(dtv.year, dtv.month, dtv.day)
    return core._fmt(dtv, fmt)


# ------------------------------------------------------------------ 视图
def _fill_case_def(prof, ev, dates):
    """病种档案的病例定义里留了 <起止>/<机构> 占位符，按事件数据回填。
    宁可留占位符也不编造：真缺值就保留原样，让读者一眼看出没填。"""
    if not prof:
        return prof
    prof = dict(prof)
    txt = prof.get("case_def")
    if not isinstance(txt, str):
        return prof
    a, b = dates.get("first_onset"), dates.get("last_onset")
    fa, fb = _d(a), _d(b, "%Y年%-m月%-d日" if not a else "%-m月%-d日")
    span = ""
    if a and b:
        span = f"{fa}至{fb}"
    elif a or b:
        span = fa if a else fb
    inst = (ev.get("institution") or {}).get("name") or ev.get("place_short") or ""
    if span:
        txt = txt.replace("<起止>", span)
    if inst:
        txt = txt.replace("<机构>", inst)
    prof["case_def"] = txt
    return prof


class View(dict):
    """模板变量容器：dict 访问 + 计算文本属性。"""

    def __init__(self, ctx, pend: Pending, prof, figures, tables, stage):
        super().__init__()
        self.ctx = ctx
        self.pend = pend
        self.prof = prof
        self.figs = figures
        self.tabs = tables
        self.stage = stage
        self.update(ctx)
        self["event"] = dict(ctx.get("event") or {})
        self["institution"] = dict(ctx.get("institution") or {})
        self["counts"] = dict(ctx.get("counts") or {})
        self["dates"] = dict(ctx.get("dates") or {})
        self["reporting"] = dict((ctx.get("event") or {}).get("reporting")
                                 or ctx.get("reporting") or {})
        self["profile"] = _fill_case_def(
            prof, ctx.get("event") or {}, ctx.get("dates") or {})
        self["stats"] = ctx.get("stats") or {}
        self["completeness"] = ctx.get("completeness") or {}
        self["pass"] = 1

        ev = self["event"]
        ev["place_short"] = ev.get("place_short") or self._place_short()

    # --- 工具
    def _place_short(self):
        p = self["event"].get("place") or {}
        inst = (self["event"].get("institution") or {}).get("name") or ""
        if isinstance(p, dict):
            parts = [p.get("city"), p.get("district"), p.get("town")]
            s = "".join([b for b in parts if b])
            # 机构名里已经写明的层级（市/区/街道）不再重复；不写死任何城市名
            if inst:
                if parts[0] and parts[1] and parts[0] in inst and parts[1] in inst:
                    s = ""            # 机构名已含市+区，前缀不再叠加
                else:
                    for part in parts:
                        if part and part in inst:
                            s = s.replace(part, "", 1)
            return s
        return str(p or "")

    def _missing(self, field, desc, grade="P1"):
        return self.pend(field, desc, grade)

    # --- 时间与元信息
    @property
    def now_date(self):
        return core._fmt(self["event"].get("report_date") or dt.date.today(), "%Y年%-m月%-d日") \
            if not isinstance(self["event"].get("report_date"), str) else self["event"]["report_date"]

    @property
    def now_datetime(self):
        t = self["event"].get("report_time")
        return t if isinstance(t, str) and t else core._fmt(dt.datetime.now(), "%Y年%-m月%-d日%H时%M分")

    # --- 开篇段
    def _intro_base(self):
        ev, inst, d = self["event"], self["institution"], self["dates"]
        cond = ev.get("report_channel") or self._missing("dates.report_org", "接报时间、报告人与报告途径（电话/系统预警/医院报告）", "P0")
        return cond

    @property
    def now_report_intro(self):
        ev, inst, d, c = self["event"], self["institution"], self["dates"], self["counts"]
        head = ev.get("intro") 
        if head:
            return head
        rep = self._missing("dates.report_org", "接报时间、报告人与报告途径", "P0")
        place = inst.get("name") or ev.get("place_short") or "〔机构〕"
        return (f"{rep}。接报后，我中心立即组织专业人员赶赴{place}开展现场流行病学调查、"
                f"病例搜索、样品采集与防控措施指导。截至{self.now_date}，共报告"
                f"{self.prof.get('name') or ev.get('disease') or '相关'}病例"
                f"{c.get('cases') or self._missing('counts.cases', '累计病例数', 'P0')}例。"
                f"现将初步调查情况报告如下：")

    @property
    def now_progress_intro(self):
        ev = self["event"]
        intro = ev.get("intro")
        if intro:
            return intro
        nm = ev.get("name") or "本起疫情"
        return f"现将{nm}截至{self.now_date}的进展情况报告如下："

    @property
    def now_final_intro(self):
        ev = self["event"]
        if ev.get("intro"):
            return ev["intro"]
        rule = self.prof.get("closure_rule") or "最后1例病例有效隔离后经过1个最长潜伏期无新发病例"
        return (f"经采取综合防控措施，{rule}，所有病例均已痊愈，"
                f"本次疫情已得到有效控制，达到结案标准。现将调查处理情况报告如下：")

    @property
    def now_case_intro(self):
        return self["event"].get("intro") or (
            f"{self._missing('dates.report_org', '接报时间、报告人与报告途径', 'P0')}。"
            f"接报后，我中心立即组织人员开展流行病学调查与处置。现将调查情况报告如下：")

    # --- 率
    @property
    def rate_text(self):
        r = self["event"].get("_rate")
        c = self["counts"]
        if r is None:
            return self._missing("counts.exposed", "罹患率分母（波及/暴露人口数）", "P0")
        return f"{r}%（{c.get('cases')}/{c.get('exposed')}）"

    # --- 分布描述
    @property
    def group_text(self):
        gall = self["stats"].get("group") or []
        g = [x for x in gall if x["group"] != "不详"]
        unk = sum(x["cases"] for x in gall if x["group"] == "不详")
        if not g:
            return self._missing("group_denoms", "各班级/单元人数与病例数", "P1")
        n = sum(x["cases"] for x in g)
        top = g[:3]
        bits = []
        for x in top:
            if x.get("rate") is not None:
                bits.append(f"{x['group']}{x['cases']}例（罹患率{x['rate']}%）")
            else:
                bits.append(f"{x['group']}{x['cases']}例")
        total = self["stats"].get("n") or n
        rest = total - n - unk
        head = f"{n}例病例分布于{len(g)}个班级（单元）"
        if unk:
            head += f"，另有{unk}例班级信息不详"
        if rest > 0:
            head += f"，其余{rest}例未归入具体班级（如教职员工）"
        tail = "，其余班级发病数均在5例及以下" if len(g) > 3 else ""
        return head + "，其中" + "，".join(bits) + tail + "。"

    @property
    def population_text(self):
        st = self["stats"]
        sc = self["event"].get("sex_counts") or {}
        male = st.get("male") or sc.get("男") or sc.get("male")
        female = st.get("female") or sc.get("女") or sc.get("female")
        if not st.get("n"):
            return self._missing("cases.sex", "病例性别、年龄构成", "P1")
        if male is None and female is None:
            head = f"共{st['n']}例病例"
            tail = "，" + self._missing("cases.sex", "病例性别、年龄构成", "P1")
            return head + tail
        ratio = f"{round(male / female, 2)}:1" if female else "—"
        txt = f"共{st['n']}例病例，其中男性{male}例、女性{female}例，男女性别比{ratio}。"
        if st.get("age_sex"):
            bands = list(st["age_sex"].keys())
            peak = max(st["age_sex"].items(), key=lambda kv: kv[1]["男"] + kv[1]["女"])
            txt += f"年龄以{peak[0]}岁组最多（{peak[1]['男'] + peak[1]['女']}例）。"
        occ = self["event"].get("occupation_note")
        if occ:
            txt += occ
        return txt

    @property
    def age_mode_band(self):
        st = self["stats"].get("age_sex") or {}
        if not st:
            return "—"
        peak = max(st.items(), key=lambda kv: kv[1]["男"] + kv[1]["女"])
        return peak[0].split("-")[0]

    @property
    def time_text(self):
        ec = self["stats"].get("epicurve") or {}
        bins = ec.get("bins") or []
        d = self["dates"]
        if not bins:
            # 无个案明细时，用汇总的首末例日期保守描述，不臆造分布
            if d.get("first_onset") or d.get("last_onset"):
                return (f"本次疫情首例病例于{_d(d.get('first_onset')) if d.get('first_onset') else '—'}发病，"
                        f"末例病例于{_d(d.get('last_onset')) if d.get('last_onset') else '—'}发病。"
                        f"（本报告依据汇总数据撰写，未取得逐例发病日期明细，故未绘制流行曲线。）")
            return self._missing("dates.first_onset", "首例/末例发病日期与时间分布", "P0")
        peak = max(bins, key=lambda b: b[1])
        span = (ec["end"] - ec["start"]).days + 1
        bh = ec.get("bin_hours")
        unit = "小时" if bh and bh < 24 else "天"
        first = d.get("first_onset") or _d(ec["start"])
        last = d.get("last_onset") or _d(ec["end"])
        txt = f"本次疫情自{first}首例发病，至{last}末例发病，历时{span}天，共{self['stats']['n']}例。"
        if bh:
            bhs = int(bh) if float(bh).is_integer() else bh
            txt += f"流行曲线以{bhs}{unit}为间隔绘制，发病高峰出现在{_d(peak[0], '%-m月%-d日')}（{peak[1]}例）。"
        gens = self["stats"].get("generations") or []
        if gens:
            gmax = max(g["gen"] for g in gens)
            if gmax >= 2:
                txt += f"按发病时间推算，本次疫情已出现{gmax}代病例，各代高峰间隔接近一个常见潜伏期。"
        return txt

    @property
    def clinical_text(self):
        s = self["stats"].get("symptoms") or []
        n = self["stats"].get("n") or 0
        if not s:
            return self._missing("symptoms", "病例症状构成（症状、例数与占比）", "P1")
        parts = [f"{k}{v}例（{core.pct(v, n):.2f}%）" for k, v in s[:6]]
        txt = f"{n}例病例中，" + "，".join(parts) + "。"
        if self["counts"].get("hospital") == 0 or self["counts"].get("severe") == 0:
            txt += "所有病例均为轻症，无重症及死亡病例。"
        return txt

    # --- 实验室
    @property
    def lab_text(self):
        lab = self.ctx.get("lab") or {}
        if not lab:
            return self._missing("lab.result", "实验室检测结果（标本类型、份数、阳性数、检测方法）", "P0")
        if lab.get("text"):
            return lab["text"]
        bits = []
        for s in (lab.get("samples") or []):
            bits.append(f"{s.get('type','标本')}{s.get('n','?')}份"
                        f"（阳性{s.get('pos',0)}份，{s.get('method','核酸检测')}）")
        txt = "共采集" + "；".join(bits) + "。"
        if lab.get("result"):
            txt += f"检测结果：{lab['result']}。"
        return txt

    # --- 研判
    @property
    def conclusion_nature(self):
        ev = self["event"]
        if ev.get("nature"):
            return ev["nature"]
        prof = self.prof.get("name") or ev.get("disease") or ""
        place = self["institution"].get("name") or ev.get("place_short") or ""
        return f"{place}{prof}暴发疫情"

    @property
    def judgement_text(self):
        ev = self["event"]
        if ev.get("judgement"):
            return ev["judgement"]
        prof = self.prof
        txt = (f"根据流行病学分布特征、临床特征及实验室检测结果，综合判断本次疫情为一起"
               f"{self.conclusion_nature}。")
        if prof.get("latent_common_days"):
            txt += (f"结合{prof.get('name')}潜伏期（常见{prof['latent_common_days']}天、"
                    f"最长{prof.get('latent_max_days', '?')}天）与病例发病时间分布，"
                    f"符合人传人/共同暴露所致聚集性发病的时间特征。")
        txt += self._missing("conclusion.nature",
                             "疫情性质研判与病因假设（暴发/聚集/散发，主要传播途径判断）", "P0")
        return txt

    @property
    def risk_text(self):
        ev = self["event"]
        if ev.get("risk"):
            return ev["risk"]
        prof = self.prof
        bits = []
        if prof.get("latent_max_days"):
            bits.append(f"该病最长潜伏期{prof['latent_max_days']}天，末例发病后仍需观察至满一个潜伏期")
        bits.append("集体单位人群密集、接触频繁，若晨检与缺勤追踪落实不到位，存在后续续发病例风险")
        if prof.get("outbreak_threshold"):
            bits.append(f"暴发判定标准为{prof['outbreak_threshold']}")
        txt = "；".join(bits) + "。"
        if not ev.get("risk"):
            txt += self._missing("risk.level", "风险等级评估与是否建议升级应急响应", "P1") + "。"
        return txt

    @property
    def economic_text(self):
        e = self.ctx.get("economic") or {}
        if not e:
            return (self._missing("economic.direct", "直接经济损失（元）", "P1") + "　" +
                    self._missing("economic.indirect", "间接经济损失（元）", "P1"))
        d, i = e.get("direct"), e.get("indirect")
        txt = f"本起疫情共造成经济损失{(d or 0) + (i or 0):,.0f}元，其中直接经济损失{d or 0:,.0f}元，间接经济损失{i or 0:,.0f}元。"
        if e.get("items"):
            txt += "直接经济损失构成：" + "、".join(f"{k}{v:,.0f}元" for k, v in e["items"].items()) + "。"
        if e.get("benefit"):
            txt += f"经测算，通过及时处置避免{e['benefit'].get('avoided','—')}人发病，效益约{e['benefit'].get('value',0):,.0f}元。"
        return txt

    @property
    def closure_text(self):
        ev = self["event"]
        if ev.get("closure"):
            return ev["closure"]
        prof = self.prof
        rule = prof.get("closure_rule") or "最后1例病例有效隔离后经过1个最长潜伏期无新发病例"
        return (f"鉴于{rule}，且所有病例均已痊愈、相关污染场所已完成终末消毒，"
                f"经专家组讨论，该起疫情可予结案。")

    @property
    def outcome_text(self):
        c = self["counts"]
        bits = []
        if c.get("recovered") is not None:
            bits.append(f"累计痊愈{c['recovered']}例")
        if c.get("current") is not None:
            bits.append(f"现隔离治疗/医学观察{c['current']}例")
        if c.get("hospital") is not None:
            bits.append(f"住院{c['hospital']}例")
        if c.get("severe") is not None:
            bits.append(f"重症{c['severe']}例")
        if c.get("death") is not None:
            bits.append(f"死亡{c['death']}例")
        return "，".join(bits) + "。" if bits else self._missing("counts.recovered", "病例转归（痊愈、在治、重症、死亡）", "P1")

    @property
    def contacts_text(self):
        ct = self.ctx.get("contacts") or {}
        if not ct:
            return self._missing("contacts.total", "密切接触者判定标准、总人数与医学观察结果", "P0")
        if ct.get("text"):
            return ct["text"]
        txt = ""
        if ct.get("criteria"):
            txt += f"按{ct['criteria']}判定密切接触者。"
        if ct.get("total") is not None:
            txt += f"共判定密切接触者{ct['total']}人"
        if ct.get("observed") is not None:
            txt += f"，均已实施{ct.get('days', '—')}天医学观察"
        if ct.get("abnormal") is not None:
            txt += f"，观察期内出现异常{ct['abnormal']}人"
        if ct.get("second_gen") is not None:
            txt += f"，发生二代病例{ct['second_gen']}例"
        return txt + "。" if txt else self._missing("contacts.total", "密切接触者总人数与观察结果", "P0")

    @property
    def measures_effect(self):
        ev = self["event"]
        return ev.get("measures_effect") or self._missing(
            "measures.effect", "控制措施效果评价（末例后观察期、二代病例、接种率、缺勤恢复）", "P0")

    @property
    def next_steps(self):
        ev = self["event"]
        if ev.get("next_steps"):
            return ev["next_steps"]
        prof = self.prof
        items = [
            "继续落实晨午检与因病缺勤病因追查，每日零报告至末例病例后一个最长潜伏期",
            "加强教室、宿舍、食堂等场所通风与预防性消毒，做好记录",
            "在知情同意、自愿自费原则下推进应急接种，提高免疫屏障覆盖率",
            "持续开展健康教育，告知家长与教职工早期症状识别与及时就诊要求",
        ]
        if prof.get("key_exposures"):
            items.insert(2, f"针对{prof['key_exposures'][0]}等关键环节开展专项排查")
        return "\n".join(f"{i+1}. {t}" for i, t in enumerate(items))

    @property
    def cdc_measures(self):
        return self["event"].get("cdc_measures") or self._missing(
            "measures.cdc", "疾控机构与辖区医疗机构落实的措施", "P0")

    @property
    def lessons(self):
        return self["event"].get("lessons") or self._missing(
            "lessons", "存在问题与经验教训", "P1")

    @property
    def recommendations(self):
        return self["event"].get("recommendations") or self._missing(
            "recommendations", "今后工作建议（学校/辖区医疗机构/疾控三个层面）", "P1")

    # --- 图与表（已带编号与题注）
    @property
    def fig_epicurve(self):
        return self.figs.get("epicurve", "")

    @property
    def fig_age_sex(self):
        return self.figs.get("age_sex", "")

    @property
    def fig_timeline(self):
        return self.figs.get("timeline", "")

    # 其余图位：按模板调用顺序取名，缺图即空字符串（模板用 if 包裹）
    @property
    def fig_group(self):
        return self.figs.get("group_fig", "")

    @property
    def fig_symptom(self):
        return self.figs.get("symptom", "")

    @property
    def fig_chain(self):
        return self.figs.get("chain", "")

    @property
    def fig_geo(self):
        return self.figs.get("geo", "")

    @property
    def fig_generation(self):
        return self.figs.get("generation", "")

    @property
    def fig_latent(self):
        return self.figs.get("latent", "")

    @property
    def fig_env(self):
        return self.figs.get("env", "")

    @property
    def fig_or(self):
        return self.figs.get("or", "")

    @property
    def fig_vax(self):
        return self.figs.get("vax", "")

    @property
    def fig_floor(self):
        return self.figs.get("floor", "")

    @property
    def table_symptoms(self):
        raw = self["event"].get("symptom_table")
        if isinstance(raw, str) and raw.strip():
            return raw.strip() + "\n"
        return self.tabs.get("symptoms", "")

    @property
    def table_group(self):
        return self.tabs.get("group", "")

    @property
    def timeline_marks(self):
        return self.ctx.get("timeline_marks")

    @property
    def missing_list(self):
        if self["pass"] == 1:
            return []
        order = {"P0": 0, "P1": 1, "P2": 2}
        return sorted(self.pend.items, key=lambda x: (order[x["grade"]], x["seq"]))


# ------------------------------------------------------------------ 图表
def make_figures(ctx, out_dir, prof, event, dpi_note=True):
    """按可用数据决定画哪些图，返回 (figs_md, tables_md, files)。"""
    fig_dir = os.path.join(out_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    figs, tables, files = {}, {}, []
    n = [0]

    def add(key, path, caption):
        if not path:
            return ""
        n[0] += 1
        files.append(path)
        rel = os.path.relpath(path, out_dir)
        cap = f"图{n[0]}　{caption}"
        figs[key] = f"![{cap}]({rel})\n"
        return figs[key]

    st = ctx["stats"]
    ev = ctx["event"]
    d = ctx["dates"]
    inst = ctx.get("institution") or {}
    pname = (prof.get("name") or ev.get("disease") or "该病")
    place = inst.get("name") or ev.get("place_short") or ""

    # 1 流行曲线
    ec = st.get("epicurve") or {}
    if ec.get("bins"):
        evs = []
        for key, lab in (("intervention", "实施干预"),):
            v = ev.get(key)
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and item.get("date"):
                        evs.append((core.parse_date(item["date"]), item.get("label", lab)))
                    elif isinstance(item, str):
                        dd = core.parse_date(item)
                        if dd:
                            evs.append((dd, lab))
        p = viz.epicurve(ec["bins"], ec["bin_hours"], os.path.join(fig_dir, "fig1_epicurve.png"),
                         title=f"{place}{pname}病例发病时间分布" if place else "病例发病时间分布",
                         events=evs, first_dt=ec.get("start"), last_dt=ec.get("end"))
        add("epicurve", p, f"{place}{pname}病例发病时间分布")
    # 2 班级分布
    if (st.get("group") or []) and len([g for g in st["group"] if g["group"] != "不详"]) >= 2:
        p = viz.group_bar(st["group"], os.path.join(fig_dir, "fig2_group.png"), title="病例班级（单元）分布")
        add("group_fig", p, "病例班级（单元）分布")
    # 3 年龄性别
    if st.get("age_sex"):
        p = viz.age_sex(st["age_sex"], os.path.join(fig_dir, "fig3_age_sex.png"), title="病例年龄性别分布")
        add("age_sex", p, "病例年龄性别分布")
    # 4 代际
    if (prof.get("latent_common_days") and st.get("generations")):
        p = viz.generation_steps(ctx["cases"], prof["latent_common_days"],
                                 os.path.join(fig_dir, "fig4_generation.png"))
        add("generation", p, "病例代际分布（按发病时间推算）")
    # 5 潜伏期（食源）
    if st.get("latent"):
        p = viz.latent_hist(st["latent"]["values"], os.path.join(fig_dir, "fig5_latent.png"))
        add("latent", p, "病例潜伏期分布")
    # 6 地理
    geo = ev.get("geo") or []
    if geo:
        if isinstance(geo[0], (list, tuple)) and len(geo[0]) == 3:
            p = viz.geo_dist(None, os.path.join(fig_dir, "fig6_geo.png"), points=geo)
        else:
            p = viz.geo_dist([tuple(x) for x in geo], os.path.join(fig_dir, "fig6_geo.png"))
        add("geo", p, "病例地理分布")
    # 7 症状
    if st.get("symptoms"):
        p = viz.symptom_bar(st["symptoms"], st.get("n") or 1,
                            os.path.join(fig_dir, "fig7_symptom.png"))
        add("symptom", p, "病例症状构成")
    # 8 传播链
    tc = ev.get("transmission") or {}
    if tc.get("nodes"):
        nodes = []
        for x in tc["nodes"]:
            x = dict(x)
            x["onset"] = core.parse_date(x.get("onset"))
            nodes.append(x)
        p = viz.transmission_chain(nodes, tc.get("edges") or [],
                                   os.path.join(fig_dir, "fig8_chain.png"),
                                   title=tc.get("title") or "病例传播链示意")
        add("chain", p, tc.get("title") or "病例传播链示意")
    # 9 采样
    if ev.get("env_sampling"):
        p = viz.env_sampling([tuple(x) for x in ev["env_sampling"]],
                             os.path.join(fig_dir, "fig9_env.png"))
        add("env", p, "采样与检测结果")
    # 10 病例-对照
    if ev.get("case_control"):
        p = viz.case_control_forest([tuple(x) for x in ev["case_control"]],
                                    os.path.join(fig_dir, "fig10_or.png"))
        add("or", p, "危险因素病例对照分析（OR）")
    # 11 时间轴
    tm = []
    for k, lab in (("first_onset", "发病"), ("visit", "就诊"), ("diagnosed", "确诊"),
                   ("isolated", "隔离"), ("discharge", "出院")):
        v = d.get(k) or ev.get(k)
        if v:
            tm.append((core.parse_date(v), lab))
    if len(tm) >= 2:
        p = viz.case_timeline(tm, os.path.join(fig_dir, "fig11_timeline.png"))
        add("timeline", p, "病例关键时间节点")

    # ---- 表
    if st.get("symptoms"):
        rows = ["| 症状 | 病例数 | 占比（%） |", "|---|---|---|"]
        for k, v in st["symptoms"][:10]:
            rows.append(f"| {k} | {v} | {core.pct(v, st.get('n') or 1)} |")
        tables["symptoms"] = "\n".join(rows) + "\n"
    if st.get("group"):
        rows = ["| 班级（单元） | 病例数 | 人数 | 罹患率（%） |", "|---|---|---|---|"]
        tot_c = tot_d = 0
        for g in st["group"][:30]:
            rows.append(f"| {g['group']} | {g['cases']} | {g['denom'] or '—'} | {g['rate'] if g['rate'] is not None else '—'} |")
            tot_c += g["cases"]
            tot_d += g["denom"] or 0
        rows.append(f"| 合计 | {tot_c} | {tot_d or '—'} | {core.pct(tot_c, tot_d) if tot_d else '—'} |")
        tables["group"] = "\n".join(rows) + "\n"
    return figs, tables, files


# ------------------------------------------------------------------ 导出
def to_docx(md_path, docx_path, profile="default"):
    try:
        import md2docx
    except Exception as e:
        return None, f"md2docx 不可用：{e}"
    try:
        md2docx.convert(md_path, docx_path, profile)
        return docx_path, None
    except Exception as e:
        return None, f"docx 生成失败：{e}"


def _find_soffice():
    """按平台找 LibreOffice 可执行文件：环境变量 → PATH → 各平台默认安装位置。"""
    env = os.environ.get("SOFFICE_BIN")
    if env and os.path.exists(env):
        return env
    for name in ("soffice", "libreoffice"):
        hit = shutil.which(name)
        if hit:
            return hit
    cands = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",   # macOS
        "/opt/homebrew/bin/soffice",
        "/usr/bin/soffice",                                        # Linux
        "/usr/local/bin/soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",     # Windows
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for cand in cands:
        if os.path.exists(cand):
            return cand
    return None


def to_pdf(docx_path, out_dir, md_path=None):
    office = _find_soffice()
    if not office:
        # 没有 LibreOffice：走 PyMuPDF 兜底排版（内容一致、版式独立一套）
        if md_path:
            try:
                import sys as _sys
                _here = os.path.dirname(os.path.abspath(__file__))
                if _here not in _sys.path:
                    _sys.path.insert(0, _here)
                from md2pdf_fallback import md_to_pdf
                pdf = md_to_pdf(md_path, os.path.splitext(docx_path)[0] + ".pdf")
                return str(pdf), None
            except Exception as exc:
                return None, f"未找到 LibreOffice，兜底 PDF 也失败：{exc}"
        return None, ("未找到 LibreOffice（soffice）。md/docx 已生成，PDF 需要它："
                      "macOS 用 brew install --cask libreoffice，Windows 装 LibreOffice，"
                      "或用环境变量 SOFFICE_BIN 指定路径")
    env = dict(os.environ, HOME=os.path.expanduser("~"))
    r = subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
                       capture_output=True, timeout=300, env=env)
    pdf = os.path.splitext(docx_path)[0] + ".pdf"
    if os.path.exists(pdf):
        return pdf, None
    return None, (r.stderr or b"").decode("utf-8", "ignore")[-300:]


# ------------------------------------------------------------------ 主流程
def build(event_path, out_dir, stage="initial", line_list=None, formats=("md", "docx", "pdf"),
          docx_profile="default", extra=None, privacy="both"):
    os.makedirs(out_dir, exist_ok=True)
    if event_path.endswith((".yaml", ".yml")):
        raw = core.load_yaml(event_path)
    else:
        raw = json.load(open(event_path, encoding="utf-8"))
    event = dict(raw.get("event", raw))
    # 顶层同级键（group_denoms / contacts / lab / economic 等常写在 event 外）并入事件
    for k, v in raw.items():
        if k in ("event", "line_list", "stage", "timeline_marks"):
            continue
        if k not in event:
            event[k] = v
    if extra:
        for k, v in extra.items():
            if v not in (None, ""):
                event[k] = v
    ll = line_list or raw.get("line_list")
    if ll and not os.path.isabs(ll):
        ll = os.path.join(os.path.dirname(os.path.abspath(event_path)), ll)
    cases = core.load_line_list(ll) if ll else raw.get("cases")
    stage = (event.get("stage") or stage).lower()

    ctx = core.build_context(event, cases=cases, stage=stage)
    ctx["timeline_marks"] = raw.get("timeline_marks")
    prof = ctx["profile"]
    # 结案申请单是一页纸，不配图（避免产出无用的 figures/ 目录）
    if stage == "closure":
        figs, tabs, fig_files = {}, {}, []
    else:
        try:
            figs, tabs, fig_files = make_figures(ctx, out_dir, prof, event)
        except ImportError as e:                  # 没装绘图依赖：只出文字稿
            print(f"[warn] 绘图依赖缺失（{e}），本次不生成图，正文自动省略图位",
                  file=sys.stderr)
            figs, tabs, fig_files = {}, {}, []
    pend = Pending(stage)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TPL_DIR),
        undefined=jinja2.Undefined,
        finalize=lambda x: "" if x is None else x,
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters["d"] = _d
    env.globals.update(ph=pend, CN=CN_NUM)
    tpl = env.get_template(STAGE_TPL.get(stage, STAGE_TPL["initial"]))

    # 两遍渲染：第一遍收集〔待补〕，第二遍带附录定稿
    view = View(ctx, pend, prof, figs, tabs, stage)
    tpl.render(v=view)
    view["pass"] = 2
    md = tpl.render(v=view)
    md = re.sub(r"\n{3,}", "\n\n", md)
    # 图号按正文出现顺序重排（生成顺序 ≠ 阅读顺序，先画的不一定先出现）
    counter = {"n": 0}

    def _renum(m):
        counter["n"] += 1
        return f"![图{counter['n']}　{m.group(1)}]({m.group(2)})"

    md = re.sub(r"!\[图\d+　([^\]]*)\]\(([^)]+)\)", _renum, md)

    base = os.path.splitext(os.path.basename(event_path))[0]
    name = event.get("filename") or f"{stage}-{base}"

    def emit(md_text, suffix):
        """写 md（必要时转 docx/pdf），返回 {格式: 路径}。"""
        md_path = os.path.join(out_dir, f"{name}{suffix}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        got = {"md": md_path}
        if "docx" in formats:
            docx_path = os.path.join(out_dir, f"{name}{suffix}.docx")
            got_path, err = to_docx(md_path, docx_path, docx_profile)
            got["docx"] = got_path or err
            if got_path and "pdf" in formats:
                pdf, err2 = to_pdf(got_path, out_dir, md_path=md_path)
                got["pdf"] = pdf or err2
        elif "pdf" in formats:
            got["pdf"] = "PDF 需先导出 docx（Word 渲染链路），已跳过"
        return {k: v for k, v in got.items() if v}

    # 人名清单：事件字段 + 个案 CSV + YAML 里手工补的 privacy.names
    names = set()
    names |= deident.collect_from_event(event)
    names |= deident.collect_from_line_list(ll)
    names |= set((event.get("privacy") or {}).get("names") or [])

    outs, red_outs, red_stats = {}, {}, None
    # 未脱敏版是内部留档：名字直写，便于与个案表核对
    if privacy in ("raw", "both"):
        outs = emit(md, "")
    # 脱敏版是外发稿：先改文本再转格式，图形与附表一并走
    if privacy in ("redacted", "both"):
        red_md, red_stats = deident.redact(md, names)
        red_outs = emit(red_md, "-脱敏")

    report = {
        "完成度": f"{ctx['completeness']['score']}%（{ctx['completeness']['level']}）",
        "待补项": f"P0 {ctx['completeness']['by_grade'].get('P0', 0)} / "
                  f"P1 {ctx['completeness']['by_grade'].get('P1', 0)} / "
                  f"P2 {ctx['completeness']['by_grade'].get('P2', 0)}",
        "图": len([x for x in fig_files]),
        "输出": outs,
    }
    if red_outs:
        report["脱敏输出"] = red_outs
        report["脱敏处理"] = deident.describe(red_stats)
    if privacy == "redacted":
        report["提示"] = "本次只出脱敏版；内部留档请加 --privacy raw 或 both。"
    return report, (outs or red_outs), md


def main():
    ap = argparse.ArgumentParser(description="流调报告生成器")
    ap.add_argument("--event", required=True, help="事件 YAML/JSON")
    ap.add_argument("--stage", default="initial", choices=list(STAGE_TPL))
    ap.add_argument("--line-list", help="个案 CSV（大疫情网导出或自定义）")
    ap.add_argument("--out", default="./流调输出")
    ap.add_argument("--formats", default="md,docx,pdf")
    ap.add_argument("--docx-profile", default="default", choices=["default", "gongwen", "compact"])
    ap.add_argument("--privacy", default="both", choices=["raw", "redacted", "both"],
                    help="输出策略：raw=只出未脱敏版（内部留档）；redacted=只出脱敏版（可外发）；"
                         "both=两版都出（默认）")
    ap.add_argument("--check", action="store_true", help="只做输入体检，不出稿")
    a = ap.parse_args()

    if a.check:
        raw = core.load_yaml(a.event) if a.event.endswith((".yaml", ".yml")) else json.load(open(a.event))
        ev = raw.get("event", raw)
        cases = core.load_line_list(a.line_list or raw.get("line_list")) if (a.line_list or raw.get("line_list")) else raw.get("cases")
        ctx = core.build_context(ev, cases=cases, stage=a.stage)
        c = ctx["completeness"]
        print(f"\n完成度 {c['score']}%　{c['level']}")
        print(f"P0 {c['by_grade'].get('P0',0)} 项 / P1 {c['by_grade'].get('P1',0)} 项 / P2 {c['by_grade'].get('P2',0)} 项\n")
        for m in c["missing"]:
            print(f"  [{m['grade']}] {m['desc']}　（{m['due']}）")
        return

    report, outs, md = build(a.event, a.out, a.stage, a.line_list,
                             tuple(x.strip() for x in a.formats.split(",")), a.docx_profile,
                             privacy=a.privacy)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
