"""脱敏层单测：漏一个标识就算失败。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import deident  # noqa: E402

CASES = [
    # (说明, 原文, 不得残留的片段)
    ("身份证", "身份证号 320206200207172847，已核实", ["320206200207172847"]),
    ("手机", "联系电话 13812345678。", ["13812345678"]),
    ("固话", "报告单位电话 0510-83571986。", ["0510-83571986"]),
    ("出生日期", "年龄 17 岁（出生日期 2008年12月23日）", ["2008年12月23日"]),
    ("门牌", "现住惠山区洛社镇石塘湾村27号3幢2单元501室", ["27号", "501室"]),
    ("邮箱", "邮箱 zhangzq@example.com", ["zhangzq@example.com"]),
]

fail = 0
for label, src, must_vanish in CASES:
    out, stats = deident.redact(src)
    left = [x for x in must_vanish if x in out]
    ok = not left
    print(f"{'✓' if ok else '✗'} {label}: {out}")
    fail += 0 if ok else 1

# 人名：全文一致化名，且同姓不同人区分
text = "首例张志强发病，其母李秀兰陪同；流调员王建国核实。次例张志强（同名不同人）由王建国报告。"
out, stats = deident.redact(text, names={"张志强", "李秀兰", "王建国"})
checks = [
    ("原姓名消失", not any(n in out for n in ("张志强", "李秀兰", "王建国"))),
    ("保留姓氏", "张某" in out and "李某" in out and "王某" in out),
    ("计数正确", stats["人名"] == 5),
]
for label, ok in checks:
    print(f"{'✓' if ok else '✗'} {label}: {out}")
    fail += 0 if ok else 1

# 机构与地名必须保留（脱敏不能把报告弄成没法定位）
keep = "无锡市惠山区某高级中学，某镇某社区，2026年3月11日，12例"
out2, _ = deident.redact(keep, names=set())
ok = out2 == keep
print(f"{'✓' if ok else '✗'} 机构/地名/日期不动: {out2}")
fail += 0 if ok else 1

print("\n" + ("全部通过" if fail == 0 else f"{fail} 项失败"))
sys.exit(1 if fail else 0)
