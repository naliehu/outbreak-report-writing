"""脱敏层单测：漏一个标识就算失败。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import deident  # noqa: E402


def _mark(ok: bool) -> str:
    """✓/✗ 在 GBK 控制台会抛 UnicodeEncodeError（中文 Windows 控制台默认 CP936）→ 退化成 ASCII。"""
    fancy, plain = ("✓", "[OK]") if ok else ("✗", "[NO]")
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        fancy.encode(enc, "strict")
        return fancy
    except (UnicodeEncodeError, LookupError):
        return plain

CASES = [
    # (说明, 原文, 不得残留的片段)
    ("身份证", "身份证号 110101199001011234，已核实", ["110101199001011234"]),
    ("手机", "联系电话 13812345678。", ["13812345678"]),
    ("固话", "报告单位电话 010-88886666。", ["010-88886666"]),
    ("出生日期", "年龄 17 岁（出生日期 2009年1月1日）", ["2009年1月1日"]),
    ("门牌", "现住xx市xx区xx街道xx路27号xx栋501室", ["27号", "501室"]),
    ("邮箱", "邮箱 zhangyi@example.com", ["zhangyi@example.com"]),
]

fail = 0
for label, src, must_vanish in CASES:
    out, stats = deident.redact(src)
    left = [x for x in must_vanish if x in out]
    ok = not left
    print(f"{_mark(ok)} {label}: {out}")
    fail += 0 if ok else 1

# 人名：全文一致化名，且同姓不同人区分
text = "首例张一发病，其母李二陪同；流调员陈三核实。次例张一（同名不同人）由陈三报告。"
out, stats = deident.redact(text, names={"张一", "李二", "陈三"})
checks = [
    ("原姓名消失", not any(n in out for n in ("张一", "李二", "陈三"))),
    ("保留姓氏", "张某" in out and "李某" in out and "陈某" in out),
    ("计数正确", stats["人名"] == 5),
]
for label, ok in checks:
    print(f"{_mark(ok)} {label}: {out}")
    fail += 0 if ok else 1

# 机构与地名必须保留（脱敏不能把报告弄成没法定位）
keep = "xx市xx区xx中学，xx街道xx社区，2026年3月11日，12例"
out2, _ = deident.redact(keep, names=set())
ok = out2 == keep
print(f"{_mark(ok)} 机构/地名/日期不动: {out2}")
fail += 0 if ok else 1

print("\n" + ("全部通过" if fail == 0 else f"{fail} 项失败"))
sys.exit(1 if fail else 0)
