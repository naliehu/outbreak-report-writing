"""脱敏：把成稿里能指向具体人的信息替换掉，生成可外传的版本。

为什么单独一层、而不是在模板里留空
    报告要能上会、能外发，也必须能内部留档。同一份数据出两个版本，比出一个"半脱敏"
    版本安全——永远有一份完整的原始稿在本地，也永远有一份可以直接发的稿子。
    因此脱敏发生在成稿之后、格式转换之前：先改文本，再转 Word/PDF，图形与附表一起走。

原则
    1. 结构化来源优先：事件 YAML 与个案 CSV 里写明的人名、证件号、电话，逐字替换，
       不靠猜；替换前后同一个人用同一个化名，报告仍然读得通。
    2. 正则兜底：身份证、手机号、固话、出生日期、门牌号。漏一个都算失败。
    3. 不动机构名、行政区、日期、病例数：这些是报告成立的基础，删了就没法看了。
    4. 每次替换都记账（redact_stats），让人知道改了什么、改了几处。
"""

import os
import re

# ---------------------------------------------------------------- 人名来源
# 事件 YAML 里可能承载人名的键（大小写不敏感匹配键名尾部）
NAME_KEYS = (
    "name", "patient", "case_name", "first_case_name", "reporter", "reporter_name",
    "investigator", "surveyor", "applicant", "reviewer", "doctor", "nurse",
    "contact_name", "guardian", "parent", "填卡医生", "报告人", "调查人", "流调人员",
    "审核人", "申请人", "家长姓名", "患者姓名", "姓名",
)
# 个案 CSV 里承载人名的列
NAME_COLS = ("患者姓名", "姓名", "家长姓名", "填卡医生", "报告人", "调查人", "流调人员",
             "医生", "接报人", "审核人")

# 这些键虽然含 name，但指的是机构/地区/病种，不能当人名替换
NAME_KEY_BLOCK = ("institution", "school", "hospital", "district", "town", "village",
                  "community", "city", "province", "org", "unit_name", "disease",
                  "filename", "place", "venue", "region", "county", "street")

ID_PAT = re.compile(r"(?<![\dXx])(?:\d{17}[\dXx]|\d{15})(?![\dXx])")
MOBILE_PAT = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
TEL_PAT = re.compile(r"(?<!\d)0\d{2,3}[-\s]?\d{7,8}(?:[-\s]?\d{1,4})?(?!\d)")
BIRTH_PAT = re.compile(r"(出生日期|出生年月|生日)\s*[:：]?\s*"
                       r"\d{4}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*日?")
# 门牌层：到"号/室/栋/单元"为止的细地址
ADDR_PAT = re.compile(r"([\u4e00-\u9fa5]{1,12}(?:村|社区|居委|委会|街道|路|街|巷|弄|组|小区|花园|公寓|大厦|苑|里))"
                      r"\s*\d+\s*(?:号|号院)[^\s，。；、）)]{0,16}")
UNIT_ADDR_PAT = re.compile(r"\d+\s*(?:号楼|栋|幢|单元)\s*\d*\s*(?:室|户)?")
EMAIL_PAT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

SURNAME_MASK = "某"


def _is_person_key(k):
    kl = str(k).lower()
    if any(b in kl for b in NAME_KEY_BLOCK):
        return False
    return any(kl == n or kl.endswith("_" + n) or kl.endswith(n) for n in NAME_KEYS)


# 这些值不是人名：占位符与"不详"类表述
NAME_STOP = {"待填", "待查", "待补", "不详", "未知", "暂无", "无", "略", "某某",
             "未填写", "未提供", "不适用", "同上", "姓名"}


def collect_from_event(event, out=None):
    """从事件字典里挖出人名集合（只认人名键，且值像人名）。

    institution/place 这类子树整枝跳过——里面的 name 是机构名，绝不能当人名换掉。
    """
    out = out if out is not None else set()
    if isinstance(event, dict):
        for k, v in event.items():
            if str(k).lower() in NAME_KEY_BLOCK:
                continue
            if isinstance(v, (dict, list)):
                collect_from_event(v, out)
            elif isinstance(v, str) and _is_person_key(k):
                for token in re.split(r"[、,，/\s]+", v.strip()):
                    token = token.strip("（）()：: ")
                    if 2 <= len(token) <= 4 and re.fullmatch(r"[\u4e00-\u9fa5·]+", token) \
                            and token not in NAME_STOP:
                        out.add(token)
    elif isinstance(event, list):
        for it in event:
            collect_from_event(it, out)
    return out


def collect_from_line_list(path, out=None):
    """从个案 CSV 里取人名列（大疫情网导出为 GBK，需回退解码）。"""
    out = out if out is not None else set()
    if not path or not os.path.exists(path):
        return out
    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8-sig", "gbk", "gb18030", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        return out
    header = text.splitlines()[0].split(",")
    idx = [i for i, h in enumerate(header) if h.strip() in NAME_COLS]
    if not idx:
        return out
    for line in text.splitlines()[1:]:
        cells = line.split(",")
        for i in idx:
            if i < len(cells):
                v = cells[i].strip().strip("'\"")
                if 2 <= len(v) <= 4 and re.fullmatch(r"[\u4e00-\u9fa5·]+", v) \
                        and v not in ("不详", "无", "未知"):
                    out.add(v)
    return out


def mask_name(name):
    """张三 → 张某；复姓与少数民族姓名取首字 + 某。"""
    if not name:
        return name
    if "·" in name:
        return name.split("·")[0] + SURNAME_MASK
    return name[0] + SURNAME_MASK


def redact(text, names=(), keep_surname=True):
    """返回 (脱敏后文本, 统计字典)。names 是待替换的人名集合。"""
    stats = {"人名": 0, "身份证": 0, "手机": 0, "固话": 0, "出生日期": 0,
             "门牌": 0, "邮箱": 0}
    out = text

    # 1) 人名：长的先替换，避免"张志强"里的"张志"先被换掉
    used = {}
    for name in sorted(set(names), key=len, reverse=True):
        if name not in out:
            continue
        alias = mask_name(name) if keep_surname else "病例"
        if alias in used and used[alias] != name:      # 同姓不同人，加序号区分
            i = 2
            while f"{alias}{i}" in used:
                i += 1
            alias = f"{alias}{i}"
        used[alias] = name
        n = out.count(name)
        out = out.replace(name, alias)
        stats["人名"] += n

    # 2) 证件与联系方式
    out, n = ID_PAT.subn("（略）", out); stats["身份证"] += n
    out, n = MOBILE_PAT.subn("（略）", out); stats["手机"] += n
    out, n = TEL_PAT.subn("（略）", out); stats["固话"] += n
    out, n = EMAIL_PAT.subn("（略）", out); stats["邮箱"] += n

    # 3) 出生日期保年龄、去日期
    def _birth(m):
        return f"{m.group(1)}（略）"
    out, n = BIRTH_PAT.subn(_birth, out); stats["出生日期"] += n

    # 4) 门牌：只在"人的住址"语境脱敏；单位地址（学校、市场）属公开信息，保留
    def _mask_addr(m, keep_head=True):
        ctx = out[max(0, m.start() - 10):m.end()]
        if any(w in ctx for w in ("现住", "住址", "居住", "家庭住", "家中", "宅", "租住")):
            stats["门牌"] += 1
            return (m.group(1) + "（略）") if keep_head else "（略）"
        return m.group(0)
    out = ADDR_PAT.sub(lambda m: _mask_addr(m, True), out)
    out = UNIT_ADDR_PAT.sub(lambda m: _mask_addr(m, False), out)

    return out, stats


def redact_file(md_path, out_path, names=()):
    """读 md → 脱敏 → 写新 md，返回统计。"""
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    new, stats = redact(text, names)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(new)
    stats["_changed"] = new != text
    return stats


def describe(stats):
    """把统计压成一句话，便于打印与写进 JSON。"""
    parts = [f"{k} {v} 处" for k, v in stats.items() if k != "_changed" and v]
    return "、".join(parts) if parts else "未发现可脱敏项"
