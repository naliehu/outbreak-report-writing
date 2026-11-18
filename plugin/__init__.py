"""epi-report 插件：把 outbreak-report-writing 技能的轻量流水线暴露成工具。

设计取舍：
- 不做生成逻辑，只做编排（生成逻辑在技能里，改一次两处同步，避免两份实现漂移）。
- 所有产出落到调用方指定目录，返回绝对路径，调用方可直接交付。
- 缺项不报错：完成度不足时照样出稿，把待补项随摘要返回。
"""
import json
import os
import subprocess
from pathlib import Path

SKILL = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))) / "skills" / "outbreak-report-writing"
BUILD = SKILL / "scripts" / "build_report.py"
VENV_PY = SKILL / "vendor" / "venv" / "bin" / "python"

SCHEMA = {
    "name": "epi_report",
    "description": (
        "生成传染病现场流行病学调查报告（流调报告）。输入一份事件 YAML/JSON（可只填五个字段）"
        "和可选的大疫情网个案 CSV，输出 markdown/docx/pdf，并自动配流行曲线、班级分布、"
        "年龄性别、代际、传播链等图。缺项按 P0/P1/P2 分级列入附录。"
        "action=check 只做输入体检不出稿。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["build", "check"], "default": "build",
                        "description": "build=出稿；check=只体检缺项"},
            "event_path": {"type": "string", "description": "事件 YAML 或 JSON 的绝对路径"},
            "out_dir": {"type": "string", "description": "输出目录（绝对路径）"},
            "stage": {"type": "string", "enum": ["initial", "progress", "final", "closure", "case"],
                       "default": "initial",
                       "description": "initial 初次／progress 进程／final 结案／closure 结案申请单／case 单例病例"},
            "line_list": {"type": "string", "description": "可选：大疫情网导出的个案 CSV 路径"},
            "formats": {"type": "string", "default": "md,docx,pdf",
                         "description": "逗号分隔，可选 md,docx,pdf"},
            "docx_profile": {"type": "string", "enum": ["default", "gongwen", "compact"],
                              "default": "default", "description": "Word 版式"},
            "privacy": {"type": "string", "enum": ["both", "raw", "redacted"], "default": "both",
                         "description": "输出策略：both=未脱敏版+脱敏版（默认）；raw=只出未脱敏版；"
                                        "redacted=只出脱敏版（可外发，姓名改化名，证件/电话/门牌（略））"},
        },
        "required": ["event_path"],
    },
}


def _py():
    return str(VENV_PY) if VENV_PY.exists() else "python3"


def handler(args, **kwargs):
    action = (args.get("action") or "build").lower()
    event_path = args.get("event_path")
    if not event_path:
        return json.dumps({"error": "缺 event_path"}, ensure_ascii=False)
    if not os.path.exists(event_path):
        return json.dumps({"error": f"找不到事件文件：{event_path}"}, ensure_ascii=False)
    if not BUILD.exists():
        return json.dumps({"error": f"技能未安装在预期位置：{BUILD}"}, ensure_ascii=False)

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)

    cmd = [_py(), str(BUILD), "--event", event_path]
    if action == "check":
        cmd.append("--check")
    else:
        out_dir = args.get("out_dir") or str(Path(event_path).parent / "流调输出")
        cmd += ["--out", out_dir,
                "--stage", args.get("stage") or "initial",
                "--formats", args.get("formats") or "md,docx,pdf",
                "--docx-profile", args.get("docx_profile") or "default",
                "--privacy", args.get("privacy") or "both"]
        if args.get("line_list"):
            cmd += ["--line-list", args["line_list"]]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=env,
                           cwd=str(SKILL))
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "生成超时（>15 分钟），检查输入规模或图片数量"}, ensure_ascii=False)

    if r.returncode != 0:
        return json.dumps({"error": "生成失败", "returncode": r.returncode,
                           "stderr": (r.stderr or "")[-1500:],
                           "stdout": (r.stdout or "")[-800:]}, ensure_ascii=False)

    out = (r.stdout or "").strip()
    try:
        payload = json.loads(out)
    except Exception:
        payload = {"raw": out[-2000:]}
    payload["skill_dir"] = str(SKILL)
    return json.dumps(payload, ensure_ascii=False)


def register(ctx):
    ctx.register_tool(name="epi_report", toolset="epi_report", schema=SCHEMA, handler=handler)
