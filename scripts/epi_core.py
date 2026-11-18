#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
epi_core.py —— 流调报告生成核心：数据装载、派生统计、完成度评分、缺失信息分级

设计原则
1. 绝不因为缺数据而报错：任何字段缺失都降级为"待补充"，仍能出稿。
2. 所有派生指标只在数据充足时计算，否则返回 None 并登记缺失项。
3. 缺失信息按 P0/P1/P2 三级 + 时限窗口排序，直接可粘贴进报告附录 A。
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
from collections import Counter, defaultdict, OrderedDict

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.path.join(BASE, "templates", "disease_profiles.yaml")

# ---------------------------------------------------------------- 基础工具

def load_yaml(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML：pip install pyyaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_profiles():
    return load_yaml(PROFILE_PATH)["diseases"]


def get_profile(disease: str) -> dict:
    """按病种名/别名匹配档案；找不到返回空档案（不阻塞）。"""
    profs = load_profiles()
    if not disease:
        return {}
    d = str(disease).strip()
    for name, p in profs.items():
        keys = [name] + list(p.get("aliases") or [])
        if any(k and k in d for k in keys):
            return dict(p, name=name)
    for name, p in profs.items():          # 反向包含匹配
        if d in name:
            return dict(p, name=name)
    return {}


def parse_date(v):
    """容忍 2026-3-26 / 2026年3月26日 / 2026/3/26 9:00 / Excel 序列号。"""
    if v is None or v == "":
        return None
    if isinstance(v, (dt.date, dt.datetime)):
        return v if isinstance(v, dt.datetime) else dt.datetime(v.year, v.month, v.day)
    s = str(v).strip().strip("'\"")
    if not s:
        return None
    if re.fullmatch(r"\d{5}(\.\d+)?", s):          # Excel 序列日期
        try:
            return dt.datetime(1899, 12, 30) + dt.timedelta(days=float(s))
        except Exception:
            return None
    s = s.replace("年", "-").replace("月", "-").replace("日", " ")
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2}))?", s)
    if m:
        y, mo, d, hh, mm = m.groups()
        try:
            return dt.datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0))
        except ValueError:
            return None
    return None


def age_from(birth, onset=None):
    b, o = parse_date(birth), parse_date(onset) or dt.datetime.now()
    if not b:
        return None
    return o.year - b.year - ((o.month, o.day) < (b.month, b.day))


def pct(a, b, nd=2):
    if not b:
        return None
    return round(100.0 * a / b, nd)


def fmt_d(d):
    return d.strftime("%Y年%-m月%-d日") if d else "—"


def fmt_dt(d):
    return d.strftime("%Y年%-m月%-d日%H时%M分") if d else "—"


# ---------------------------------------------------- 大疫情网个案 CSV 归一

# 大疫情网导出字段 → 内部字段
LINE_LIST_MAP = {
    "患者姓名": "name", "姓名": "name",
    "性别": "sex",
    "出生日期": "birth",
    "年龄": "age",
    "单位": "group",
    "人群分类": "occupation", "职业": "occupation",
    "详细住址": "address", "现住地址": "address2",
    "发病日期": "onset", "终审发病": "onset",
    "诊断日期": "diagnosed", "终审诊断": "diagnosed",
    "病例类型": "case_type", "病例分类": "case_type",
    "疾病病种": "disease",
    "报告单位": "report_unit",
    "备注": "note",
    "家长姓名": "guardian",
    "现住址类型": "addr_type",
    "死亡时间": "death",
}
TYPE_NORM = {"临床诊断病例": "临床诊断", "确诊病例": "实验室确诊", "实验室诊断病例": "实验室确诊",
             "疑似病例": "疑似", "阳性检测": "阳性检测", "病原携带者": "病原携带"}

_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_CN_OUT = "零一二三四五六七八九十"


def cn2int(s):
    s = str(s).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if s.startswith("十"):
        return 10 + _CN_DIGIT.get(s[1:2], 0)
    if s.endswith("十"):
        return _CN_DIGIT.get(s[0], 0) * 10
    if "十" in s:
        a, b = s.split("十", 1)
        return _CN_DIGIT.get(a, 0) * 10 + (_CN_DIGIT.get(b, 0) if b else 0)
    return _CN_DIGIT.get(s)


def int2cn(n):
    n = int(n)
    if n <= 10:
        return _CN_OUT[n]
    if n < 20:
        return "十" + _CN_OUT[n - 10]
    return _CN_OUT[n // 10] + "十" + (_CN_OUT[n % 10] if n % 10 else "")


_SCHOOL_RE = re.compile(r"^[\u4e00-\u9fa5A-Za-z]{0,12}?(?:幼儿园|实验学校|实验小学|实验中学|小学|中学|学校|幼托中心|托幼机构)")
_GRADE_UNIT = "高大中托小初"


def norm_group(g):
    """把大疫情网里五花八门的"单位"字段归一为可统计的班级/单元名。

    例：'xx小学一（3）班' / '一(3)班' / '一3班' / '一年级（3）班' → '一（3）班'
        '高二14班' → '高二14班'；'大（3）班' → '大（3）班'；只有校名 → '不详'
    """
    s = re.sub(r"\s+", "", str(g or ""))
    if not s or s in ("不详", "无", "-", "—", "/"):
        return "不详"
    # 去掉前缀校名（含"校名错字"这类错字，只要以"学校/小学/幼儿园"结尾即视为校名）
    prev = None
    while prev != s:
        prev = s
        s = _SCHOOL_RE.sub("", s)
    s = s.replace("(", "（").replace(")", "）")
    if not s or s in ("不详", "无"):
        return "不详"
    # 幼儿园/高中式：大（3）班、中1班、高二14班、小（2）班
    m = re.match(r"^([高大中托小初])([一二三四五六七八九十]{0,2})[（(]?([一二三四五六七八九十\d]{1,2})[)）]?班$", s)
    if m:
        unit, grade, cls = m.groups()
        gi = cn2int(grade) if grade else None
        ci = cn2int(cls)
        if ci is not None:
            if gi is not None:
                return f"{unit}{int2cn(gi)}{int(ci)}班"
            return f"{unit}（{int(ci)}）班"
    # 年级+班式：四（1）班、四年级二班、二6班、2（6）班
    m = re.match(r"^([一二三四五六七八九十\d]{1,2})(?:年级)?[（(]?([一二三四五六七八九十\d]{1,2})[)）]?班$", s)
    if m:
        gi, ci = cn2int(m.group(1)), cn2int(m.group(2))
        if gi and ci:
            return f"{int2cn(gi)}（{int(ci)}）班"
    # 单纯"X班"
    m = re.match(r"^([一二三四五六七八九十\d]{1,2})班$", s)
    if m:
        ci = cn2int(m.group(1))
        if ci:
            return f"{int(ci)}班"
    return s if len(s) <= 12 else "不详"


def load_line_list(path):
    """读取个案 CSV（自动识别编码与字段），返回标准化病例列表。"""
    if not path or not os.path.exists(path):
        return []
    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", "replace")
    rdr = csv.DictReader(text.splitlines())
    rows = []
    for r in rdr:
        c = {}
        for k, v in r.items():
            if k is None:
                continue
            k = k.strip()
            key = LINE_LIST_MAP.get(k)
            if key:
                c[key] = (v or "").strip()
        if not c:
            continue
        c.setdefault("name", "")
        c["case_type"] = TYPE_NORM.get(c.get("case_type", ""), c.get("case_type", ""))
        c["onset_dt"] = parse_date(c.get("onset"))
        c["dx_dt"] = parse_date(c.get("diagnosed"))
        if not c.get("age"):
            a = age_from(c.get("birth"), c.get("onset"))
            c["age"] = str(a) if a is not None else ""
        # 班级/单位清洗：取"X年X班""大（3）班"等
        # 班级/单位归一（大疫情网"单位"字段由填卡医生自由填写，清洗后才能统计）
        c["group_clean"] = norm_group(c.get("group"))
        rows.append(c)
    return rows


# ---------------------------------------------------------------- 派生统计

def epicurve(cases, bin_hours=None, latency_max_days=None):
    """返回时间分布：[(bin_start, count)]；自动选择时间间隔。"""
    onsets = sorted([c["onset_dt"] for c in cases if c.get("onset_dt")])
    if not onsets:
        return {"bins": [], "bin_hours": None, "start": None, "end": None}
    start, end = onsets[0], onsets[-1]
    span_h = max(1.0, (end - start).total_seconds() / 3600.0)
    n = len(onsets)
    if bin_hours is None:
        # 规则：使柱子数落在 8–35 之间；间隔尽量取 潜伏期的 1/4~1/3
        cand = [1, 2, 3, 4, 6, 8, 12, 24, 24 * 2, 24 * 3, 24 * 7]
        if latency_max_days:
            q = max(1.0, latency_max_days * 24 / 4.0)
            cand = sorted(set(cand + [round(q), round(q * 1.5), round(latency_max_days * 24 / 3)]))
            cand = [c for c in cand if c >= 1]
        best = min(cand, key=lambda b: (abs(span_h / b - 20), b))
        bin_hours = best if span_h / best <= 40 else max(cand)
    b0 = start.replace(minute=0, second=0, microsecond=0)
    if bin_hours >= 24:
        b0 = b0.replace(hour=0)
    buckets = Counter()
    for o in onsets:
        k = int((o - b0).total_seconds() // 3600 // bin_hours)
        buckets[k] += 1
    kmax = int((end - b0).total_seconds() // 3600 // bin_hours)
    bins = [(b0 + dt.timedelta(hours=bin_hours * k), buckets.get(k, 0)) for k in range(kmax + 1)]
    return {"bins": bins, "bin_hours": bin_hours, "start": start, "end": end, "by_hour": len(bin_hours and str(bin_hours)) and bin_hours < 24}


def group_dist(cases, denoms=None):
    """班级/单位分布，含罹患率（需分母）。"""
    c = Counter([x.get("group_clean") or "不详" for x in cases])
    rows = []
    for g, n in c.most_common():
        d = (denoms or {}).get(g)
        rows.append({"group": g, "cases": n, "denom": d, "rate": pct(n, d) if d else None})
    return rows


def age_sex(cases):
    t = defaultdict(lambda: {"男": 0, "女": 0, "不详": 0})
    for x in cases:
        a = x.get("age")
        try:
            a = int(float(a))
        except Exception:
            continue
        band = f"{a // 5 * 5}-{a // 5 * 5 + 4}"
        s = x.get("sex") if x.get("sex") in ("男", "女") else "不详"
        t[band][s] += 1
    return OrderedDict(sorted(t.items(), key=lambda kv: int(kv[0].split("-")[0])))


def symptom_dist(cases, symptoms=None):
    if symptoms is None:
        cnt = Counter()
        for x in cases:
            for s in (x.get("symptoms") or []):
                cnt[s] += 1
        return cnt.most_common()
    n = len([x for x in cases])
    return [(s, sum(1 for x in cases if s in (x.get("symptoms") or [])), n) for s in symptoms]


def latent_dist(cases):
    """食源性疾病：进食时间→发病时间（小时）。需 cases[].meal_dt。"""
    out = []
    for x in cases:
        m, o = parse_date(x.get("meal")), x.get("onset_dt")
        if m and o and o >= m:
            out.append((o - m).total_seconds() / 3600.0)
    if not out:
        return None
    out.sort()
    return {"n": len(out), "min": round(out[0], 1), "max": round(out[-1], 1),
            "median": round(out[len(out) // 2], 1),
            "mean": round(sum(out) / len(out), 1), "values": out}


def generations(cases, latent_common_days=None):
    """按发病时间分代：以首例为第1代，间隔≥(0.6×常见潜伏期)视为新一代。"""
    pts = sorted([(c["onset_dt"], i, c) for i, c in enumerate(cases) if c.get("onset_dt")],
                 key=lambda x: (x[0], x[1]))
    if not pts:
        return []
    gap = (latent_common_days or 3) * 0.6
    gen, last, out = 1, pts[0][0], []
    for o, _i, c in pts:
        if (o - last).total_seconds() / 86400.0 >= gap:
            gen += 1
            last = o
        out.append({"case": c, "gen": gen})
    # 只保留"有意义"的分代：代际数不超过 8
    if out and out[-1]["gen"] > 8:
        return []
    return out


def completeness(event, cases, stage="initial"):
    """按报告阶段的必填权重计算完成度，并输出 P0/P1/P2 缺失清单。

    字段名以报告模板实际读取的键为准；同义键通过 ALIAS 兜底，避免
    "明明写了却判为缺失"这类假阴性。
    """
    E = event or {}
    ALIAS = {
        "first_case.detail": ["first_case_text", "first_case"],
        "measures.effect": ["measures_effect"],
        "conclusion.nature": ["judgement", "nature"],
        "contacts.observed_result": ["contacts.second_gen", "contacts.abnormal"],
        "contacts.total": ["contacts.count"],
        "lab.result": ["lab.text", "lab.summary"],
        "symptoms": ["symptom_table"],
        "economic.direct": ["economic.direct_loss"],
        "institution.students": ["institution.student_total"],
        "dates.isolated_last": ["dates.isolated"],
        "vax.rate": ["vaccination.rate"],
    }

    def _get(path):
        cur = E
        for k in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    def has(path, minlen=1):
        for p in [path] + ALIAS.get(path, []):
            cur = _get(p)
            if cur in (None, "", [], {}):
                continue
            if isinstance(cur, str) and len(cur.strip()) < minlen:
                continue
            return True
        return False

    checks = []  # (字段路径, 说明, 等级, 权重, 时限)
    def add(path, desc, grade, w, due, ok=None):
        ok = has(path) if ok is None else ok
        checks.append({"field": path, "desc": desc, "grade": grade,
                       "weight": w, "due": due, "ok": bool(ok)})

    # --- P0：不补则结论/上报/结案不成立
    add("event.name", "事件名称（含地区、机构、病种）", "P0", 3, "24小时")
    add("event.disease", "病种判定", "P0", 3, "24小时")
    add("event.level", "事件级别（一般/较大/未分级）", "P0", 2, "24小时")
    add("dates.first_onset", "首例发病日期", "P0", 3, "24小时")
    add("dates.report_org", "接报时间与报告人", "P0", 2, "24小时")
    add("dates.web_report", "网络直报时间", "P0", 2, "24小时")
    add("counts.cases", "累计病例数", "P0", 3, "24小时")
    add("counts.exposed", "波及/暴露人口数（罹患率分母）", "P0", 3, "24小时")
    add("case_def", "病例定义（疑似/临床诊断/确诊）", "P0", 3, "24小时")
    add("lab.result", "实验室检测结果（病原确认）", "P0", 3, "48小时")
    add("measures", "已采取的预防控制措施", "P0", 3, "当日")

    if stage in ("final", "progress"):
        add("dates.last_onset", "末例病例发病日期", "P0", 3, "结案前")
        add("dates.isolated_last", "末例隔离日期", "P0", 3, "结案前")
        add("contacts.total", "密切接触者总人数", "P0", 3, "48小时")
        add("contacts.observed_result", "医学观察期满结果（有无二代病例）", "P0", 3, "结案前")
        add("conclusion.nature", "疫情性质判定（暴发/聚集/散发）", "P0", 3, "结案前")
        add("measures.effect", "控制措施效果评价", "P0", 2, "结案前")
        add("disinfection.area", "消毒面积/频次", "P1", 1, "结案前")

    if stage == "final":
        add("economic.direct", "直接经济损失（元）", "P1", 2, "结案前")
        add("economic.indirect", "间接经济损失（元）", "P1", 1, "结案前")
        add("lessons", "存在问题与经验教训", "P1", 1, "结案前")
        add("recommendations", "今后工作建议", "P1", 1, "结案前")

    # --- P1：章节完整性与可信度
    add("institution.name", "机构名称与详细地址", "P1", 2, "24小时")
    add("institution.students", "学生/员工总数及男女构成", "P1", 2, "24小时")
    add("institution.classes", "班级/单元数", "P1", 1, "48小时")
    add("first_case.detail", "首例病例详细信息（年龄、班级、住址、接种史）", "P1", 3, "24小时")
    add("counts.clinical", "临床诊断病例数", "P1", 1, "48小时")
    add("counts.confirmed", "实验室确诊病例数", "P1", 1, "48小时")
    add("symptoms", "症状构成（例数与占比）", "P1", 2, "48小时")
    add("exposure", "暴露史/流行病学史", "P1", 3, "48小时")
    add("group_denoms", "各班/各单元人数（分层罹患率分母）", "P1", 2, "48小时")
    add("reporting.reporter", "报告人/审核人/联系电话", "P1", 1, "结案前")

    # --- P2：精细化提升
    add("vax.rate", "应急接种应种/实种人数与接种率", "P2", 1, "结案前")
    add("env_sampling", "环境/食品/水源采样份数与结果", "P2", 1, "48小时")
    add("institution.map", "机构平面图/校舍分布图", "P2", 0.5, "结案前")
    add("media", "舆情监测与风险沟通情况", "P2", 0.5, "结案前")
    add("photos", "现场处置照片", "P2", 0.5, "结案前")
    add("line_list", "个案一览表（可用于复核统计）", "P2", 2, "48小时")

    # 个案数据驱动的检查
    if cases:
        checks.append({"field": "cases", "desc": "个案明细（发病日期完整率）", "grade": "P1", "weight": 2,
                       "due": "48小时", "ok": sum(1 for c in cases if c.get("onset_dt")) / len(cases) > 0.8})
        checks.append({"field": "cases.sex", "desc": "个案性别/年龄完整率", "grade": "P2", "weight": 1,
                       "due": "48小时", "ok": sum(1 for c in cases if c.get("sex")) / len(cases) > 0.9})

    total_w = sum(c["weight"] for c in checks)
    got_w = sum(c["weight"] for c in checks if c["ok"])
    score = round(100 * got_w / total_w, 1) if total_w else 0.0
    missing = [c for c in checks if not c["ok"]]
    order = {"P0": 0, "P1": 1, "P2": 2}
    missing.sort(key=lambda c: (order[c["grade"]], -c["weight"]))
    by_grade = Counter(c["grade"] for c in missing)
    return {"score": score, "checks": checks, "missing": missing,
            "by_grade": dict(by_grade), "stage": stage,
            "level": ("可直接定稿" if score >= 90 else
                      "可出稿，个别数据待补" if score >= 75 else
                      "可出草稿，关键结论待补" if score >= 50 else
                      "仅为框架稿，需现场数据支撑")}


# ---------------------------------------------------------------- 报告上下文

def build_context(event, cases=None, stage="initial", line_list_path=None):
    """把原始输入整理成模板可渲染的上下文字典。缺什么就留 None/空。"""
    cases = cases if cases is not None else load_line_list(line_list_path)
    E = event or {}
    prof = get_profile(E.get("disease") or "")
    dates = E.get("dates") or {}
    counts = E.get("counts") or {}
    inst = E.get("institution") or {}

    ev = dict(E)
    ev["_first_onset"] = parse_date(dates.get("first_onset"))
    ev["_last_onset"] = parse_date(dates.get("last_onset"))
    ev["_report"] = parse_date(dates.get("report_org"))
    ev["_profile"] = prof

    # 从个案补齐病例数与首末例
    if cases:
        onsets = [c["onset_dt"] for c in cases if c.get("onset_dt")]
        if onsets:
            if not parse_date(dates.get("first_onset")):
                dates["first_onset"] = min(onsets).strftime("%Y-%m-%d")
            if not parse_date(dates.get("last_onset")):
                dates["last_onset"] = max(onsets).strftime("%Y-%m-%d")
            ev["_first_onset"] = parse_date(dates["first_onset"])
            ev["_last_onset"] = parse_date(dates["last_onset"])
        counts.setdefault("cases", len(cases))
        counts.setdefault("confirmed", sum(1 for c in cases if c.get("case_type") == "实验室确诊"))
        counts.setdefault("clinical", sum(1 for c in cases if c.get("case_type") == "临床诊断"))
    E["dates"] = dates
    E["counts"] = counts

    rate = None
    try:
        if counts.get("cases") and counts.get("exposed"):
            rate = pct(float(counts["cases"]), float(counts["exposed"]))
    except Exception:
        rate = None
    ev["_rate"] = rate

    ec = epicurve(cases or [], latency_max_days=prof.get("latent_max_days")) if cases else {"bins": []}
    # 无个案明细时，用事件级汇总数据兜底（不臆造，只搬运作者给的数据）
    sym = None
    if cases:
        sym = symptom_dist(cases)
    elif isinstance(E.get("symptoms"), dict):
        sym = sorted(E["symptoms"].items(), key=lambda kv: -kv[1])
    grp = None
    if cases:
        grp = group_dist(cases, E.get("group_denoms") or {})
    elif isinstance(E.get("group_counts"), dict):
        grp = group_dist([{"group_clean": k} for k, n in E["group_counts"].items()
                          for _ in range(int(n))], E.get("group_denoms") or {})
    ctx = {
        "event": ev,
        "profile": prof,
        "dates": dates,
        "counts": counts,
        "institution": inst,
        "lab": E.get("lab") or {},
        "contacts": E.get("contacts") or {},
        "measures": E.get("measures") or [],
        "economic": E.get("economic") or {},
        "cases": cases or [],
        "stats": {
            "n": len(cases or []) or (counts.get("cases") or 0),
            "epicurve": ec,
            "group": grp or [],
            "age_sex": age_sex(cases or []) if cases else {},
            "symptoms": sym or [],
            "latent": latent_dist(cases or []) if cases else None,
            "generations": generations(cases or [], prof.get("latent_common_days")) if cases else [],
            "sex_ratio": None,
        },
        "completeness": completeness(E, cases, stage),
        "stage": stage,
        "generated_at": dt.datetime.now(),
    }
    if cases:
        m = sum(1 for c in cases if c.get("sex") == "男")
        f = sum(1 for c in cases if c.get("sex") == "女")
        if f:
            ctx["stats"]["sex_ratio"] = f"{round(m / f, 2)}:1"
        ctx["stats"]["male"], ctx["stats"]["female"] = m, f
    return ctx


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else None
    if p:
        ev = load_yaml(p) if p.endswith((".yaml", ".yml")) else json.load(open(p))
        c = build_context(ev.get("event", ev), line_list_path=ev.get("line_list"), stage=ev.get("stage", "initial"))
        print(f"完成度 {c['completeness']['score']}%  ({c['completeness']['level']})")
        for m in c["completeness"]["missing"]:
            print(f"  [{m['grade']}] {m['desc']}  ({m['due']})")
