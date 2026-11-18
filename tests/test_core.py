#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单元测试：凡是自己写的字符串/日期处理，先过这里再进报告。"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import epi_core as c  # noqa: E402

FAIL = []


def eq(got, want, label):
    if got != want:
        FAIL.append(f"{label}: got={got!r} want={want!r}")


# ---------------- 班级名归一
CASES = [
    ("某实验学校一（3）班", "一（3）班"),
    ("某实验学校一(3)班", "一（3）班"),
    ("二4班", "二（4）班"),
    ("刘潭实验小学二年级（6）班", "二（6）班"),
    ("无锡市刘潭实验小学2（6）班", "二（6）班"),
    ("某实验学校四年级二班", "四（2）班"),
    ("刘谭实验学校四1班", "四（1）班"),          # 错别字也要能识别
    ("无锡市北塘区刘潭实验小学", "不详"),         # 只有校名
    ("不详", "不详"),
    ("", "不详"),
    ("高二14班", "高二14班"),
    ("高二（14）班", "高二14班"),
    ("大（3）班", "大（3）班"),
    ("中1班", "中（1）班"),
    ("托（2）班", "托（2）班"),
    ("小2班", "小（2）班"),
    ("高一7班", "高一7班"),
    ("高三18班", "高三18班"),
]
for raw, want in CASES:
    eq(c.norm_group(raw), want, f"norm_group({raw})")

# ---------------- 中文数字
for a, b in [(1, "一"), (9, "九"), (10, "十"), (14, "十四"), (21, "二十一")]:
    eq(c.int2cn(a), b, f"int2cn({a})")
for a, b in [("十", 10), ("十四", 14), ("二十一", 21), ("7", 7), ("二", 2)]:
    eq(c.cn2int(a), b, f"cn2int({a})")

# ---------------- 日期
eq(c.parse_date("2026-03-26"), dt.datetime(2026, 3, 26), "parse_date iso")
eq(c.parse_date("2026年3月26日"), dt.datetime(2026, 3, 26), "parse_date 中文")
eq(c.parse_date("2026/3/26 8:30"), dt.datetime(2026, 3, 26, 8, 30), "parse_date 斜杠带时分")
eq(c.parse_date("2016-2-27 9:37"), dt.datetime(2016, 2, 27, 9, 37), "parse_date 大疫情网格式")
eq(c.parse_date(""), None, "parse_date 空")
eq(c.parse_date("不详"), None, "parse_date 文本")

# ---------------- 年龄
eq(c.age_from("2008-12-23", "2026-03-11"), 17, "age_from 生日已过")
eq(c.age_from("2008-12-23", "2026-07-01"), 17, "age_from 生日未过")

# ---------------- 率
eq(c.pct(49, 3408), 1.44, "pct 两位")
eq(c.pct(1, 0), None, "pct 分母0")

# ---------------- 病种档案
p = c.get_profile("水痘")
eq(p.get("name"), "水痘", "profile 精确")
eq(p.get("latent_max_days"), 21, "profile 水痘最长潜伏期")
p2 = c.get_profile("诺如病毒感染")
eq(p2.get("name"), "诺如病毒感染性腹泻", "profile 别名/模糊")
p3 = c.get_profile("伤寒")
eq(p3.get("name"), "伤寒副伤寒", "profile 伤寒")
eq(c.get_profile("未知怪病"), {}, "profile 未知返回空")

# ---------------- 流行曲线分箱
cases = [{"onset_dt": dt.datetime(2026, 3, 1) + dt.timedelta(days=i % 20)} for i in range(40)]
ec = c.epicurve(cases, latency_max_days=21)
assert ec["bin_hours"] in (12, 24, 48, 72, 1, 2, 3, 4, 6, 8), ec["bin_hours"]
assert sum(b[1] for b in ec["bins"]) == 40, sum(b[1] for b in ec["bins"])
# 诺如：潜伏期3天、18小时暴发 → 建议按小时分箱
noro = [{"onset_dt": dt.datetime(2026, 3, 1, 8) + dt.timedelta(hours=i * 2)} for i in range(30)]
ec2 = c.epicurve(noro, latency_max_days=3)
assert ec2["bin_hours"] < 24, ec2["bin_hours"]
assert sum(b[1] for b in ec2["bins"]) == 30

print(f"通过 {len(CASES) + 20} 项检查" if not FAIL else "")
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("全部通过")
