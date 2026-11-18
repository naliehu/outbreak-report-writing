# 传染病流调报告撰写技能（outbreak-report-writing）

把手上一堆**不完整**的现场信息，变成一份当天就能上报的流调报告：正文按疾控体例写，
缺的部分不冒充，图按病种自动配齐，Word／PDF／Markdown 随时导出。

这套东西不是拍脑袋写的模板。它从 **1300 余份真实流调文稿**（2011–2026 年无锡市传染病类突发事件
全部卷宗、江阴伤寒／副伤寒、宜兴霍乱、梁溪猴痘、输入性登革热、发热伴、区县上报市疾控的结案申请单）
里反向提炼：章节骨架来自 477 份报告的实测顺序，文风参数来自 16815 句的统计，
病种判据来自原文写明的观察期与处置口径。

## 解决什么问题

| 老问题 | 这里的做法 |
|---|---|
| 数据没齐，报告写不下去，一拖就是三天 | 缺的字段变成正文里的红色〔待补P0-2〕，先出一版能看的，附录 A 告诉你还差什么、多急 |
| 每次都要重新想章节顺序、抄上回的报告 | 六种体裁固定骨架，选 stage 直接出 |
| 流行曲线画成折线、间隔随便定 | 按潜伏期自动定分箱（诺如 4–8 小时、水痘 5–7 天），标注首末例与干预时点 |
| 大疫情网导出的个案表一个班拆成四行 | `单位` 字段自动归一（18 组用例覆盖，含校名错字） |
| 写完不知道会不会被退 | 附录 A 的 P0 就是退稿点，自检 12 问逐条过 |
| 结案报告缺成本效益分析被要求返工 | 第九节按国家标准科目分项，直接给表格 |

## 三十秒上手

```bash
cd ~/.hermes/skills/outbreak-report-writing
PY="env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python"

# 只有五个字段也能出稿
$PY scripts/build_report.py --event examples/03-残缺输入/event.yaml \
    --stage initial --out ./我的输出 --formats md,docx,pdf

# 真实个案 CSV 驱动（自动出四张图）
$PY scripts/build_report.py --event examples/02-某实验学校水痘-真实个案/event.yaml \
    --stage initial --line-list examples/02-某实验学校水痘-真实个案/个案-已脱敏.csv \
    --out ./我的输出 --formats md,docx,pdf
```

`--stage`：`initial` 初次／`progress` 进程／`final` 结案／`closure` 结案申请单／`case` 单例病例。

## 输出：同时给你两版

成稿默认出两份，`-脱敏` 那一份可以直接发出去：

| 项目 | 未脱敏版（内部） | 脱敏版（外发） |
|---|---|---|
| 姓名 | 张志强 | 张某（同姓不同人自动加序号） |
| 身份证 / 手机 / 固话 / 邮箱 | 原样 | （略） |
| 出生日期 | 2008年12月23日 | （略），年龄保留 |
| 住址 | 石塘湾村27号3幢2单元501室 | 石塘湾村（略） |
| 机构 / 行政区 / 日期 / 病例数 / 罹患率 | 保留 | 保留 |

开关：`--privacy both`（默认）／`raw` 只出内部版／`redacted` 只出外发版。
插件里对应参数 `privacy`。人名清单自动从事件字段和个案 CSV 里取，正则可兜住手工写进正文的证件号。

## 两条路径

- **轻量模板**（`scripts/build_report.py`）：事件 YAML 或大疫情网 CSV → 六种体裁直出。单例、临时、只有一份导出表时用这个。
- **全量引擎**（`scripts/flowreport.py`）：report.json（93 字段／11 章）→ 四图 + 三格式 + 快照 + 签发门禁。要连出十几期进程报告、进审签流程时用这个。

两条路径的缺项分级是同一套判据的两种叫法：L1 阻断传播 = P0，L2 影响研判 = P1，L3 完善叙述 = P2。

## 已验证的事实（不是"应该能跑"）

- `tests/test_core.py`：38 项单测全过（班名归一 18 例、日期 6 种写法、年龄跨生日、分箱规则）。
- 某实验学校：28 例真实个案 CSV → 初次报告 + 4 张图（流行曲线、班级分布、年龄性别、代际），
  班级分布 10 例与原始报告一致。
- 某高级中学：49 例结案报告，分层罹患率（24.07%／16.98%／11.76%）与原始报告原文完全对上，
  经济损失 42,410 元分项一致。
- 残缺输入：20.6% 完成度仍正常出 md/docx/pdf，附录 A 列 P0 8 项。
- PDF 为 A4、图片 300 dpi 内嵌、页码域正常；结案申请单压到 1 页。

## 隐私

仓库内所有示例均已脱敏：删除姓名、证件号、家长姓名、联系电话与门牌地址，
机构名统一为「某高级中学／某实验学校」，仅保留流行病学结构与统计口径。
原始流调卷宗不在本仓库内，也未随技能分发。

## DSH 插件（DeepSeek Harness）

除了当技能用，本仓库本身就是一个 DSH 插件包：装进去之后，代理多出一个 `epi_report` 工具，
一句话就能出稿，不用记命令。

```bash
dsh plugin --profile web add github:naliehu/outbreak-report-writing
dsh --profile web          # 重启后生效，直接说「用 epi_report 出一份初次报告」
```

工具参数：`action`（build／check）、`event_path`（事件 YAML/JSON，必填）、`stage`
（initial／progress／final／closure／case）、`line_list`（个案 CSV）、`out_dir`、`formats`、`docx_profile`。

插件做的事很少，也很明确：找技能目录 → 挑 Python 解释器 → 传参 → 回收产物路径。
报告怎么写、画什么图、缺项怎么分级，全在 `scripts/` 里，改一次两边同时生效。

依赖按需降级：

| 装了 | 能出 |
|---|---|
| python3 + pyyaml + jinja2 | Markdown 正文（图与 Word 自动省略，并注明原因） |
| 再加 matplotlib | 加四张叙事图与三间分布图 |
| 再加 python-docx | 加 Word；系统有 LibreOffice 则连 PDF 一起出 |

一次性装齐：`python3 -m pip install pyyaml jinja2 matplotlib python-docx`

配置（写在 profile 的 `cordis.patch.yml` 里，可全部省略）：

```yaml
- insert:
    - id: epi-report
      name: 'outbreak-report-writing'
      config:
        skillDir: ~/path/to/outbreak-report-writing   # 默认自动查找
        python: /usr/bin/python3                      # 默认优先用 vendor/venv/bin/python
        outDir: ~/流调输出                             # 默认 <事件文件同级>/流调输出
```

## 目录

```
SKILL.md                  技能主体（判据、流程、文风要点、常见坑）
references/               深度材料
  01 报告类型与骨架 → report-types.md（六体裁逐节写法）
  02 分病种要点.md        12 病种的笔墨重点与易混边界
  03 可视化作图规范.md     决策表 + 七条硬规范 + 图注
  06 文风与句式库.md       477 份报告的量化文风、七种功能句定式、数字六条、禁止清单
  intake-playbook.md      现场怎么问、问不到怎么办
  toolchain.md            模块契约、中文出图、排障
templates/                五套 .j2 体裁模板 + disease_profiles.yaml（可自行加病种）
scripts/                  epi_core / epi_viz / build_report / md2docx / flowreport
plugin/                   Hermes 插件源码（暴露成 epi_report 工具）
tests/                    单测
examples/                 三个可跑示例 + 已生成成品
```

## 推广给同事

1. **整体拷走**：`outbreak-report-writing/` 整个目录（含 `vendor/venv`，约 150 MB）给同事，`python3 scripts/build_report.py` 就能跑，不需要联网、不需要 pip。
2. **只要模板**：把 `templates/*.j2` + `references/06-文风与句式库.md` 拷走，手工填也是一份合规报告——技能的价值有一半在这个文档里。
3. **装成插件**：把 `plugin/` 拷到 `~/.hermes/plugins/epi-report/`，Hermes 里就有 `epi_report` 工具，一句话生成。
4. **加病种**：只改 `templates/disease_profiles.yaml`，不动代码。

## 已知限制

- 没有合法行政区底图，地理分布只能做场所卡片／经纬度气泡示意图，不能当 GIS 专题图对外。
- 伤寒、登革热、发热伴、食源性、基孔肯雅的潜伏期取自指南而非本地语料，YAML 里标了 `verify: true`，用前查当期方案。
- 代际由发病时间推算（0.6×常见潜伏期阈值），不是拓扑推导；有确切接触关系时以传播链为准。
- Word 版式的字体（仿宋_GB2312）需系统已安装，否则回退到宋体，不报错。
