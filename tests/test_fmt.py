"""跨平台日期格式化回归：Windows 的 CRT 不支持 %-m/%-d，这里模拟它并验证两边行为一致。"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import epi_core as core  # noqa: E402

fail = 0


def eq(got, want, label):
    global fail
    ok = got == want
    print(f"{'✓' if ok else '✗'} {label}: {got!r}" + ("" if ok else f"  期望 {want!r}"))
    fail += 0 if ok else 1


class WinCrtDate(dt.date):
    """模拟 Windows CRT：任何 %-X 修饰符都抛 ValueError（MSVC 的真实行为）。"""

    def strftime(self, fmt):
        if "%-" in fmt:
            raise ValueError("Invalid format string")
        return super().strftime(fmt)


class WinCrtDateTime(dt.datetime):
    def strftime(self, fmt):
        if "%-" in fmt:
            raise ValueError("Invalid format string")
        return super().strftime(fmt)


d1 = dt.date(2026, 11, 19)
d2 = dt.date(2026, 3, 5)
dt1 = dt.datetime(2026, 11, 19, 10, 5)

# --- 1. 新实现：普通平台
eq(core._fmt(d1, "%Y年%-m月%-d日"), "2026年11月19日", "两位月日不去零")
eq(core._fmt(d2, "%Y年%-m月%-d日"), "2026年3月5日", "单位数月日去前导零")
eq(core._fmt(dt1, "%Y年%-m月%-d日%H时%M分"), "2026年11月19日10时05分", "时分：%M 保留前导零")
eq(core._fmt(d2, "%-m月%-d日"), "3月5日", "短格式")
eq(core._fmt(d1, "%%Y"), "%Y", "%% 转义为字面百分号")
eq(core._fmt(None, "%Y年"), "—", "None 返回破折号")
eq(core.fmt_d(d1), "2026年11月19日", "fmt_d")
eq(core.fmt_dt(dt1), "2026年11月19日10时05分", "fmt_dt")

# --- 2. 同一份 _fmt 在「不支持 %- 的 CRT」上必须照常工作（Bug #1 的复现与修复证明）
w1 = WinCrtDate(2026, 11, 19)
w2 = WinCrtDate(2026, 3, 5)
eq(core._fmt(w1, "%Y年%-m月%-d日"), "2026年11月19日", "模拟 Windows CRT：两位")
eq(core._fmt(w2, "%Y年%-m月%-d日"), "2026年3月5日", "模拟 Windows CRT：单位数去零")
eq(core._fmt(WinCrtDateTime(2026, 11, 19, 10, 5), "%Y年%-m月%-d日%H时%M分"),
   "2026年11月19日10时05分", "模拟 Windows CRT：日期时间")

# 旧写法在同一对象上必然崩 —— 证明这个测试确实覆盖了 Windows 的失败路径
try:
    WinCrtDate(2026, 11, 19).strftime("%Y年%-m月%-d日")
    crash = False
except ValueError:
    crash = True
eq(crash, True, "旧写法在模拟 CRT 上抛 ValueError（基准）")

# --- 3. 与平台原生 strftime 输出一致（POSIX 上 %- 可用，可作对照）
mismatch = []
for day in (dt.date(2026, 1, 1), dt.date(2026, 1, 5), dt.date(2026, 9, 9),
            dt.date(2026, 10, 10), dt.date(2026, 11, 30)):
    native = day.strftime("%Y年%-m月%-d日")
    ours = core._fmt(day, "%Y年%-m月%-d日")
    if native != ours:
        mismatch.append((day, native, ours))
eq(mismatch, [], "与 POSIX 原生 strftime 输出逐字一致")

# --- 4. 不含 %- 的格式串不受影响（图表轴标签等仍走原生路径）
eq(core._fmt(d1, "%Y-%m-%d"), "2026-11-19", "纯标准指令不变")

print("\n" + ("全部通过" if fail == 0 else f"{fail} 项失败"))
sys.exit(1 if fail else 0)
