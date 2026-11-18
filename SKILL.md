---
name: outbreak-report-writing
description: "Use when 写、补或导出传染病流调报告（缺项分级+四图+三格式）。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [epidemiology, outbreak, 流调, report, docx, pdf, visualization]
    category: research
    related_skills: [outbreak-epi-reasoning, docx-surgery, email-deliver-files]
---

# 传染病流调报告撰写流水线

一套可反复执行的「有限信息 → 报告」流程：接到电话就能起报（1 例即可），信息边补边出，
**每一版都能直接导出 Word / PDF / Markdown**，缺失项按 L1/L2/L3 三级就地高亮并单独出补采工单。
报告本体包含 11 章 + 四张图（传播链、传播代际、地理分布、流行曲线），图在数据不够时降级但仍出图并标注缺口。

工具链已随 skill 自带（`vendor/`），不依赖 kanban 交付目录：

```
vendor/spec/            数据模型 93 字段 + 定级规则 + 11 章骨架 + derive.py（分级唯一实现）
vendor/report_engine/   组装：报告 JSON → AST（缺项内联高亮、封面 Top3、第十章清单、增量缓存）
vendor/flowfig/         四图：投影 + 渲染 + 几何门禁 + 缺口降级矩阵
vendor/report_export/   导出：AST → md/docx/pdf + 阶段快照（PDF 由同一份 docx 经 LibreOffice 转）
scripts/flowreport.py   本 skill 的执行入口（下面所有命令都是它）
templates/              最小可用报告骨架 + disease_profiles.yaml（12 病种档案）+ 五套 .j2 体裁模板
```

## 两条路径，一套判据

| 路径 | 入口 | 适合 | 产物 |
|---|---|---|---|
| **全量引擎** | `scripts/flowreport.py`（report.json，93 字段 / 11 章） | 一起正式突发事件、要反复出十几期进程报告、要进审签流程 | JSON 真源 + 四图 + 三格式 + 快照 + 签发门禁 |
| **轻量模板** | `scripts/build_report.py`（事件 YAML 或大疫情网 CSV） | 单例病例、只有五分钟、手上只有一份导出表 | 六种体裁直出 md/docx/pdf + 自动配图 + 附录 A |

两条路径的缺项分级是**同一套判据的两种叫法**，不是两套标准：

| 全量引擎 | 轻量模板 | 判据 |
|---|---|---|
| L1 阻断传播 | **P0** | 缺了则性质判定、事件分级、直报或结案不成立 |
| L2 影响研判 | **P1** | 章节缺内容，结论仍成立但会被退稿 |
| L3 完善叙述 | **P2** | 提升可信度，可在结案前补 |

先判断这次要交的是哪份东西：一次性单例用轻量模板最快；要连续跟十几天、最后报省里，用全量引擎。

## When to Use

用：拿到一起疫情（或一份不完整的流调材料），要出／续写流调报告；要把现有报告补全；
要在信息还不全时先给领导一个能看的版本；要出传播链／代际／地理／流行曲线图；
要判断"还差什么、差的东西有多急"。

不用：单纯做疫情数据解读与传播链推理（用 `outbreak-epi-reasoning`）；
单纯改一份已有的 Word 排版（用 `gexin` 或 `docx-surgery`）。

## 六条铁律

1. **不编造。** 宁可留一个醒目的红框，也不填一个"看起来对"的值。写不出就写状态（见下）。
2. **空 ≠ 缺失 ≠ 不适用。** 没问过 = `MISSING`；问了对方不知道 = `UNKNOWN`；
   对方拒答 = `REFUSED`；实验室/公安还没回 = `PENDING`；多来源冲突 = `CONFLICT`；
   按定义不适用 = `NA`（仅限台账允许的字段）；**问过并确认为没有** = `NONE`。
   用 `NONE` 消音前必须真的问过，否则等于漏管。
3. **状态是算出来的。** `DRAFT / PARTIAL / READY` 由数据决定，永远不要手改状态字段。
   `READY` 只代表"无 L1、无冲突、章节可渲染"，**不等于可以签发**（签发跑 `gate`）。
4. **任何完成度都要能出。** 不许以"还没写完"为由拒绝导出一版。缺什么由报告自己说。
5. **补采清单要带后果。** 只告诉撰写人"缺发病日期"没有用，要说清"缺了会漏排多少人"——
   台账里每个字段都带了 `ask`（怎么补）与 `why`（不补的后果），直接用，不要自己另编。
6. **外发先脱敏，源头和产物一起脱。** 任何要离开本单位的东西（发同事、传仓库、发公众号、
   当示例）都不能带姓名、证件号、家长姓名、联系电话、门牌地址、完整出生日期。
   删完必须**重新生成**：md/docx/pdf 里嵌的是旧文本，只改源文件不改产物等于没改。
   机械步骤与扫描清单见 `references/data-sharing-and-desensitization.md`。

## 目录与命名约定

一次疫情一个工作目录，报告 JSON 是唯一真源，其余都是派生物：

```
<工作目录>/
  report.json              报告 JSON（唯一真源，所有修改只改这里）
  待补信息工单.md            ask --write 生成，给人看的补采清单
  exports/                 md/docx/pdf + assets/ + figures/ + snapshots/
```

## 轻量路径（十分钟出稿）

```bash
LITE=~/.hermes/skills/outbreak-report-writing/scripts/build_report.py
PY="env -u PYTHONPATH ~/.hermes/skills/outbreak-report-writing/vendor/venv/bin/python"

$PY "$LITE" --event 事件.yaml --check                      # 只看缺什么
$PY "$LITE" --event 事件.yaml --stage final \
   --line-list 个案-已脱敏.csv --out ./输出 --formats md,docx,pdf  # 三格式全出
```

`--stage` 取 `initial`（初次）／`progress`（进程）／`final`（结案）／`closure`（结案申请单）／
`case`（单例病例）。正文里缺的字段渲染成红色〔待补P0-2〕，附录 A 按 P0→P1→P2 排序并写明时限。
事件 YAML 与个案 CSV 由使用者自建，字段清单见 `references/intake-playbook.md`。

改代码或改模板后，用**回归对账**验收：拿一份已定稿的历史报告，把它的数据录成 YAML，跑一遍，
逐项比对分层罹患率、病例数、经济损失分项与原文是否一致。数字对得上才算流水线可用；
只看"能生成文件"不算（图丢了、班名拆了、分母错了，文件照样能生成）。单测只管班名/日期/分箱这类纯函数。


### 输出两个版本（未脱敏 / 脱敏）

成稿一律出两版，`--privacy` 控制：

| 取值 | 出什么 | 用途 |
|---|---|---|
| `both`（默认） | `xxx.md/.docx/.pdf` 与 `xxx-脱敏.md/.docx/.pdf` | 印一份报领导、发一份给学校或外单位 |
| `raw` | 只有未脱敏版 | 内部留档，需与个案表逐条核对时 |
| `redacted` | 只有脱敏版 | 直接给外单位、发群、进公号 |

脱敏做什么（`scripts/deident.py`）：

- 人名 → 姓 + 某（张一→张某）；同一人全文一致，同姓不同人自动加序号
- 身份证、手机、固话、邮箱、出生日期 → `（略）`（年龄保留，出生日期去掉）
- 门牌 → 保留到村/社区/路，`27号3幢2单元501室` 变 `（略）`
- **保留**机构名、行政区、日期、病例数、罹患率——删了报告就没法定位

人名清单来自三处：事件 YAML 的人名键（`first_case.name`、`reporting.reporter` 等）、
个案 CSV 的 `患者姓名/家长姓名/填卡医生` 列、以及 YAML 里 `privacy.names` 手工补的名单。
正则兜底不依赖清单，所以手工写进正文的证件号也跑不掉。什么时候该换、什么时候必须留、
以及改这一层容易踩的坑，见 `references/data-sharing-and-desensitization.md` 第六节。

规矩：**凡是没有明确说要在内部流转的稿子，一律用 `-脱敏` 那一份。**

## 七步流程

先设一个变量，后面所有命令都用它：

```bash
SK=~/.hermes/skills/outbreak-report-writing/scripts/flowreport.py
python3 "$SK" doctor          # 一次性：依赖自检（缺 soffice 只影响 PDF，缺中文字体只影响图）
```

### 1. 起报：1 例就能建

```bash
python3 "$SK" init --id FI-2026-0031 \
  --title "某市X区一起不明原因肺炎聚集性疫情的流行病学调查报告" \
  --out ~/流调/FI-2026-0031/report.json
```

建出来的是 schema 合法的**最小骨架**（1 例病例 + 报告头），此时状态必然是 `DRAFT`：
锚点（病例身份、任一病例时间、街道级住址、疾病/病原）还没满足。这是正常的，不是错误。

### 2. 决定先问什么：按级别，不按章节

```bash
python3 "$SK" ask <report.json> --level L1     # 当班必须补的（≤4h）
python3 "$SK" status <report.json>             # 全局：状态/覆盖率/各级计数/Top3/下一步
```

L1 的定义是"缺了明天就可能有人被漏管"：发病日期、阳性日期、联系电话、暴露事件、
街道级住址、隔离日期、密接名单、措施记录。**先把这 8 类问齐**，其余再说。
L1 清零之前不要去润色文字。

### 3. 落 JSON：把回答写进去

只改 `report.json`。写法要点：

- 病例信息进 `cases[]`，密接 `contacts[]`，场所 `locations[]`，传播关系 `transmissionLinks[]`，
  措施 `measures[]`；每个实体必须有 `key`（传播关系里用 `id`）。
- 拿不到的值写 `null` **并在该对象的 `presence` 里标状态**，必要时配 `presenceNote` 写清"谁说的不知情"：

```json
"presence": { "onsetDate": "UNKNOWN", "phone": "PENDING" },
"presenceNote": {
  "onsetDate": "家长口述“前两天开始发烧”，具体日期未确认",
  "phone": "仅班主任转达，手机号待学校提供"
}
```

- 报告级字段（`outbreak.*`、`meta.*`）挂在根对象的 `presence` 上，键用相对路径的点号形式，
  如 `{"outbreak.diseaseName": "PENDING"}`。
- 枚举值有约束（如 `exposureLevel` 只能是"密切接触者/次密切接触者/一般接触者/重点人群"，
  `measures[].type` 只能用"隔离治疗/密接管理/核酸筛查/终末消毒/风险区划定/健康教育/疫苗接种/交通管制/其他"）。
  写错时 `status` 会直接把允许值列出来，按提示改。
- 传播关系要写 `generationFrom`/`generationTo`，否则代际图只能画"代次不明"；
  代次**不由拓扑推导**，这是上游刻意的"不猜"约定。

字段台账速查：`python3 "$SK" fields --level L1`、`python3 "$SK" fields --entity case`；
全量台账在 `vendor/spec/field-registry.json`。

### 4. 中途交付：随时导一版

```bash
python3 "$SK" build <report.json> --out ~/流调/FI-2026-0031/exports --snapshot --note "起报"
```

产出 `md / docx / pdf` + `figures/` 四图 + `assets/` 内嵌图 + `snapshots/<时间戳>-<状态>/`。
导出后自动自检（章节齐全、图嵌入、提示三通道可见、三格式文本一致率 ≥0.99），
`[✓]` 全绿才算这一版成立。**草稿也能给领导看**：页眉红字"草稿"、大字水印、
封面写明"缺失 L1 8 项…全部结论待核实"，不会被当成定稿。

### 5. 补采循环

```bash
python3 "$SK" ask <report.json> --write      # 生成/更新 待补信息工单.md，给人去催
#  ……按工单补数据，改 report.json……
python3 "$SK" status <report.json>           # 看级别是否下降、新增了哪些
python3 "$SK" build  <report.json> --out … --snapshot --note "补齐L1后"
python3 "$SK" diff <旧快照ID> <新快照ID> --out …   # 补齐了哪些、新增了哪些
```

`diff` 的"新增缺失"通常是因为新加了实体（如加了 measures 就多出 effect/endDate 两项），
不是错误，向用户解释一句即可。

### 6. 定稿门禁

```bash
python3 "$SK" gate <report.json> --require L2   # 对外签发默认口径（L1=0 且 L2=0 且无冲突）
python3 "$SK" gate <report.json> --require L1   # 内部上报口径
```

不通过时退出码 3，并列出必须先处理的编号。**要么补齐，要么在第九/十部分写明未受控风险
与替代核实结论**；不要改状态字段绕过门禁。

### 7. 交付

- 三种格式一起给，Word 优先（用户偏好 Word）。
- 附件命名用 `--name` 指定，默认是 `<reportId>-<version>`。
- 补采工单 `.md` 一起交，撰写人照着催数据。
- 归档/审批链要凭证时看 `exports/export-manifest.json`（AST 规范哈希 + 五项自检）。

## 命令速查

| 命令 | 作用 |
| --- | --- |
| `doctor` | 依赖自检（soffice / 中文字体 / 模块 / 规格包） |
| `init --id … --title … --out …` | 建最小可用报告（1 例即可） |
| `status REPORT [--top N] [--json]` | 状态、覆盖率、三级计数、Top 待补、下一步 |
| `ask REPORT [--level L1] [--write] [--json]` | 分级补采工单（怎么补 + 不补的后果 + 时效） |
| `build REPORT --out DIR [--formats md,docx,pdf] [--no-figures] [--snapshot]` | 组装 + 四图 + 三格式导出 + 自检 |
| `gate REPORT [--require L1\|L2\|L3]` | 签发门禁（退出码 3 = 未通过） |
| `fields [--level L1] [--entity case]` | 93 字段台账速查 |
| `snaps --out DIR` / `diff A B --out DIR` | 快照列表 / 两版对比 |

底层模块也能单独用（需要自定义时）：
`PYTHONPATH=~/.hermes/skills/outbreak-report-writing/vendor python3 -m report_engine build …`
`python3 -m flowfig …`（四图）、`python3 -m report_export pipeline …`（端到端 CLI）。

## 报告里"待补"是怎么醒目的

三通道同时出现，任一通道单独都能看见（黑白打印、色盲、屏幕阅读器都成立）：

1. **图标**：⛔ 阻断传播 / ⚠️ 影响研判 / ℹ️ 完善叙述；
2. **文字**：`【阻断传播】`、`（未采集）`、`（待实验室回报）`、`↑冲突升级`；
3. **颜色**：红 #C62828 / 橙 #E65100 / 蓝 #1565C0 + 同色系底色 + 加粗（L3 为斜体）。

位置：封面 Top3 + "待补信息速览"、每章章首计数框、缺失处就地高亮、图内缺口标注（虚线/问号/斜纹）、
图注限定语、第十部分逐条清单（编号 M-0001… 与工单一一对应）。**编号只在第十部分出现**，
正文提到别的章的缺失时写"（缺失，见第十部分：字段名）"，避免长段红字。

## 常见坑

1. **别为了消提示填占位值。** "不详""待查"进正文会被当成已采集，风险比缺失更大。
   正确做法是 `presence: {"字段": "UNKNOWN"}` + `presenceNote` 写清核实过程。
2. **`NONE` 不是"懒得填"。** 只有真的问过并确认没有（近 14 天未外出、家中无同类病例）才写 `NONE`。
3. **`NA` 会被打回。** 台账不允许的字段写 `NA` 会被强制改判 `MISSING` 并告警（防用 NA 消音）。
4. **改完数据没删旧 presence** → `W-STALE-PRESENCE` 告警，值已填但仍算缺失。删掉该 presence 条目。
5. **空数组默认按缺失计**（`exposures: []`、`symptoms: []`）。确实为无就写 `NONE`，否则保持空着。
6. **`READY` 不等于可签发**（见门禁）。封面写"可提交"指可以进审签流程。
7. **PDF 依赖 LibreOffice。** 没有 `soffice` 时 `build` 会明确报错、不伪造 PDF；
   此时用 `--formats md,docx` 先出前两种。
8. **地理分布是场所卡片示意图，不含行政区底图**（离线无合法底图），别对外说它是 GIS 专题图。
9. **代际不靠拓扑猜。** 关系里没写 `generationFrom` 就是"代次不明"，图上会单列，不要自己推。
10. **系统导出的个案表先清洗再统计。** 大疫情网 `单位` 字段同一班有多种写法（含校名错字），
    不归一出班级分布／分层罹患率，一个班会被拆成多行、最高发病班数字直接错。规则见
    `references/intake-playbook.md` 第 8 节。
11. **改完成度规则或改模板时，两边字段名必须同批改。** 校验器读的键与模板读的键一分叉，
    就出现"体检报缺一大半、正文其实是全的"，还会连带不出图。改任一边后拿一份全字段样例跑一遍自检。
    两个具体形态：①同义键（`first_case_text` / `measures_effect` / `lab.text`）写成 alias 兜底，
    不要为了对齐去改已交付的 YAML；②`group_denoms`、`contacts`、`reporting`、`economic`
    常写在 `event:` 同级，读之前先把顶层同级键并入事件对象，否则明明写了仍判缺失。
12. **画中文图时字体在模块导入时设。** 在绘图函数里设 rcParams 不生效（Text 已固化字体），
    表现为字体装好了仍全是方框；细节见 `references/toolchain.md` 的中文出图一节。
13. **模板必须有图位，否则图生成了却不进正文。** 生成器画了 13 种图，模板只留 3 个 `{{ v.fig_* }}` 位，
    结果是 `figures/` 里一堆 PNG、正文零引用、PDF 里一张图没有。加图先加位。
14. **图号按正文出现顺序重排。** 生成顺序（先画流行曲线）≠ 阅读顺序（临床特征在时间分布之前），
    按生成顺序编号会出现"图1"排在"图2"后面。渲染后正则扫一遍 `![图N　…]` 重编号，一次解决。
15. **md→docx 的图片路径按 md 所在目录解析。** 按 CWD 拼相对路径时文件"存在"判断失败，
    图片被静默跳过，docx/PDF 看着完整却没有图。改完用 `pdfimages -list 输出.pdf` 验收，
    列表为空就是没嵌进去——这一步比肉眼翻 PDF 可靠。
16. **图内不画标题。** 图里已有 `病例班级（单元）分布`，题注再写 `图2　病例班级（单元）分布`，
    印刷出来是重复两遍。图内标题关掉，题注唯一（图注在下、表注在上）。
17. **结案申请单是一页纸，别给它出图。** 它只写五要素，生成 figures/ 是垃圾产出，
    按 stage 跳过绘图。

## 对外分享与发布

报告、模板、技能包要先问一句：这东西会离开单位网络吗？会，就走一遍脱敏（铁律 6）：
删个人身份字段 → 机构名泛化 → 重新生成全部格式 → 对**产物**再扫一遍 → 再交付。
准标识符比姓名更易漏：化名 + 完整出生日期 + 学校 + 班级 + 发病日期凑在一起，圈内人一眼能对上人。
原始卷宗、训练/提取语料、`vendor/` 一律不进仓库（`.gitignore` 先排掉再 `git add`）。

## 已知取舍（写给会追问的人）

- 封面原有一行 `引擎告警：W-EMPTY-ARRAY ×N`，是录入卫生提示，已从封面移除
  （内容仍是第十部分的缺失项），终端照常打印；要保留就加 `--keep-entry-warnings`。
- 上游组装在章节不可渲染时会同时输出"占位说明「X待补：Y」"与"告警「Y」"，
  同一句印两遍；`build` 会删掉被占位说明完整包含的重复行，含新信息的告警保留。
- `flowfig` 的 `Gaps.level()` 已按契约修正为纯查表（上游 v1.0.1 同款），
  否则 0 缺失报告出图会被契约校验拒绝。
- 表头跨页重复、表格行不跨页、图注不脱节、页脚 PAGE/NUMPAGES 域、无空白页：导出层已保证。

**先认体裁再动笔**：同一事件在不同阶段要交的不是同一份文件（初次 / 进程 / 结案 / 结案申请单 /
单例病例 / 报省三节版），骨架不能混用——六种体裁的章节骨架与图型选择见 `references/report-types.md`。

**动笔前先看文风参数**：句长（中位 48 字／平均 60.7 字）、分号并列、体例词频、
七种功能句定式、数字六条规则、不确定性四级表达、病种措辞颗粒度、禁止清单，全在
`references/06-文风与句式库.md`。这是 477 份真实报告统计出来的参数表，照着写就不会跑偏。
分病种"笔墨放在哪里"见 `references/02-分病种要点.md`；出图规范与决策表见 `references/03-可视化作图规范.md`。

更细的现场问法与字段写法见 `references/intake-playbook.md`；
模块级契约、中文出图与排障见 `references/toolchain.md`。
