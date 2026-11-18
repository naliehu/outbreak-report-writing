# 工具链与排障（模块级）

## 依赖

Python 3.10+：`jsonschema`、`python-docx`、`matplotlib`、`Pillow`、`pypdf`；
LibreOffice（`soffice`）用于 PDF；中文字体（macOS Songti SC/Heiti SC，Windows 微软雅黑/黑体）。
`flowreport doctor` 一次查全，缺 soffice 只影响 PDF，缺中文字体只影响图（会变方框）。

## 一条命令背后的四步

```
report.json ──derive──> completeness(定级/排序/编号/状态机)
            ──compose─> AST(章节/表格/提示/图槽)
            ──flowfig─> 四张 PNG(+SVG) 挂进 AST 的 figure.asset
            ──export──> md / docx / pdf(+assets, figures, snapshots)
```

`flowreport build` 就是这四步再加重排检查；想单独用某一步：

```bash
V=~/.hermes/skills/outbreak-report-writing/vendor
PYTHONPATH=$V python3 -m report_engine build report.json --out-dir out --format md,html,ast
PYTHONPATH=$V python3 -m flowfig report.json --out out/figures --slots
PYTHONPATH=$V python3 -m report_export pipeline report.json --out out --figures --snapshot
PYTHONPATH=$V python3 $V/spec/derive.py report.json --full          # 缺失清单全量
```

## 契约要点（改代码/排查时看）

- **分级唯一真源是 `vendor/spec/derive.py`**，渲染层与导出层零判断；不要在任何地方另立阈值。
- `completeness.missing` 已排序、已定级、已编号、已带 `render`（颜色/底色/边框/图标/徽标）。
- `section.renderable=false` 表示数据不足但正文含占位；`figure.gap=true` 表示图内已标缺口。
- 编号 `M-xxxx` 只在第十部分出现，正文提示引用"见第十部分"，避免长段红字。
- `sortKey = {rank}-{sectionOrder:02d}-{fieldOrder:03d}-{path}`，字典序即展示序。
- 状态机：锚点不齐 → `DRAFT`；锚点齐且有 L1/冲突/章节不可渲染 → `PARTIAL`；
  否则 `READY`。三种状态**都允许导出**，`READY` 不豁免签发门禁。
- 增量缓存 key = `sha1(章节 fingerprint + 本章相关缺失项签名)`，签名不含 M 编号，
  所以补数据不会把无关章节全刷。跨次运行用 `--cache PATH` 复用。

## 排障

| 现象 | 原因 / 处理 |
| --- | --- |
| `schema 校验失败` 且列出 enum | 枚举值写错，照提示改；`fields` 命令可速查 |
| `W-STALE-PRESENCE` | 值已填但 `presence` 还写着 MISSING/UNKNOWN，删掉该条目 |
| `W-EMPTY-ARRAY ×N` | 空数组按缺失计；确认为无写 `NONE`，未问过就保持缺失 |
| `W-NA-ABUSE` | 用了台账不允许的 `NA`，被强制改判 MISSING；改 `NONE` 或补值 |
| `W-STRUCTURAL` | schema 必填项缺失，JSON 要退回补字段（引擎不把它当业务缺失） |
| PDF 报"找不到 soffice" | 装 LibreOffice，或先 `--formats md,docx` |
| 图里汉字是方框 | 先查字体是否真缺（macOS 装 Songti SC / PingFang，Linux 装 Noto Sans CJK）；**字体已装仍出方框 → rcParams 设得太晚**，见下节 |
| `GeoDistribution` 只有数字没有区县 | 缺 `currentAddress.district/street`，图按契约降级（不是 bug） |
| 代际图只有一个"代次不明"列 | 关系没写 `generationFrom/To`，按"不猜"契约降级 |
| 图内压字/越界 | 几何门禁会直接抛 `GeometryError` 不出图；按提示减少标签或换 `renderMode` |

## 已知上游瑕疵（skill 层已处理）

1. `flowfig v1.0.0` 的 `Gaps.level()` 把 `renderMode=normal` 判成 PARTIAL，导致 0 缺失报告
   出图被契约校验拒绝 → 本 vendor 副本按 `MODE_TO_LEVEL[render_mode]` 修正（等同上游 v1.0.1）。
2. `report_engine` 在不可渲染章节会同时输出占位说明「X待补：Y」与告警「Y」，同一句两遍
   → `flowreport build` 删掉被占位说明完整包含的重复行（含新信息的告警保留）。
3. 封面会印 `引擎告警：W-EMPTY-ARRAY ×N` 这类录入卫生提示 → 默认从 AST 移除（终端仍打印），
   需要保留加 `--keep-entry-warnings`。

## 中文出图与模板渲染（自建脚本栈的通用坑）

- **matplotlib 字体必须在模块导入时设，不能在绘图函数里设。** `Text` 对象创建时就把 `fontproperties`
  从 rcParams 固化了；之后在 `style()` 里再 `plt.rcParams.update({"font.family": ...})` 只影响新对象，
  已建好的标题与坐标轴仍是 DejaVu → 方框，而 `fontManager` 里明明有中文字体。写成模块级
  `_apply_rc()`，import 即执行；`style()` 只留 spines / ticks / 标签。
- **字体名用 matplotlib 真实注册名。** `Songti SC`、`Heiti SC`、`PingFang SC`、`STSong` 在 macOS 上存在，
  `SimHei`、`Microsoft YaHei` 不一定；按候选表探测 `fontManager.ttflist`，全落空才退 `sans-serif`。
- **横轴刻点自己算，不要交给 AutoDateLocator。** 跨度 40–60 天时自动 locator 会给出只标年月的稀疏刻度，
  多个柱子共用一个 "2026-04"。显式 `set_xticks + set_xticklabels("%m-%d")`，按柱数取 ≤9 个刻度，
  并裁掉尾部连续零值柱，否则右端一大片空白。
- **Jinja 的 `{{{ x }}}` 是 Mustache 语法**，直接 `TemplateSyntaxError: expected token ':', got '}'`。模板里只用 `{{ x }}`。
- **`x is not none` 对 Jinja Undefined 恒为真。** 字段可能不存在时用 `is defined`，否则缺值会渲染成
  "，死亡例。" 这类半句话，而且不报错。
- **`sorted([(datetime, dict)])` 在同时间两条之间比较 dict 抛 TypeError。** 排序元素存 `(时间, 序号, 对象)`
  并按 `key=lambda t: (t[0], t[1])` 排，别让 Python 去比字典。
- 画水平条形图后改 `set_xticklabels` 而不设 ticks 会触发 FixedLocator 警告并可能标签错位；
  要把刻度标签改成绝对值，用 `FuncFormatter(lambda t, _p: f"{abs(int(t))}")`。

## 内联〔待补〕与两遍渲染（正文要就地提示缺项时）

- 占位符工厂只在渲染时才被调用，所以**必须渲染两遍**：第一遍 `ph(field, desc, grade)` 收集缺项、分配编号，
  附录模板在 `pass == 1` 时输出空；第二遍带入完整清单定稿。同一 `field` 两次必须返回同一编号
  （`by_field` 缓存），否则正文与附录对不上号。
- **编号按等级分册**（`P0-1`、`P1-1`、`P2-1`），附录按 P0→P1→P2 排序、同级保持正文出现顺序。
  先发全局流水号再按等级重排，附录会变成 ⑥⑤①④③② 的乱序，读者没法照着补。
- **完成度校验读的字段路径，必须与模板读的键是同一份字典。** 校验器查 `first_case.detail`、模板读
  `event.first_case_text` 时，报告明明写了也判缺失，完成度虚低、连带图集不出——典型症状是
  "体检说缺一大半，正文却是全的"。要么统一键名，要么在校验器里做别名表
  （`{"first_case.detail": ["first_case_text"], "measures.effect": ["measures_effect"]}`），
  并让别名表与模板同批维护。
- 篇幅类短语（"其余班级发病数均在 5 例及以下"）只在排名确实稀疏时加；各类单位混排（`不详`、只有校名的行）
  要在句子里显式交代"另有 N 例班级信息不详"，否则合计数与分项对不上。

## 材料提取（把历史报告 / 扫描件变成可检索语料）

- `.doc/.docx/.rtf` 用 `textutil -convert txt`（macOS 原生，快且保留表格文本）；**40 MB 级大 .doc 会把
  textutil 卡死**（返回 0 字节）→ 改 `soffice --headless --convert-to txt:Text`。
- 文本层 PDF 用 `pdftotext -enc UTF-8`；**输出不足 50 字节即为扫描件**，转 OCR。
- 扫描件 OCR 走 macOS Vision：`pdftoppm -r 200 -png` 逐页渲染 → `Vision.VNRecognizeTextRequest`，
  `recognitionLanguages=["zh-Hans", "en-US"]`、`recognitionLevel=0`（accurate）、
  `usesLanguageCorrection=True`。中文表格与手写签名以外的印刷体识别质量明显优于 tesseract 默认模型，
  约 1 页/秒；识别出的签字栏会是乱码，属正常，不要据此判断 OCR 失败。
- 批量转换写成 Python + `ThreadPoolExecutor(8)` 调 subprocess，按相对路径镜像到缓存目录，
  最后只打印失败清单。**不要因为个位数扫描件阻塞上千份的提取**：先全量落盘，再单独补 OCR。

## 验收基线（要改 vendor 就跑这套）

```bash
V=~/.hermes/skills/outbreak-report-writing/vendor
cd ~/.hermes/kanban/deliverables/t_c1842b8a && python3 tests/test_export.py    # 198 断言
python3 verify_acceptance.py                                                          # 113 项
cd ~/.hermes/kanban/deliverables/t_fc8370f0 && python3 tests/test_figures.py   # 600 断言
cd ~/.hermes/kanban/deliverables/t_133c77a3 && python3 tests/test_engine.py    # 18 项
```

交付目录若已清理，用 `flowreport build` 对 `vendor/spec` 里的样例报告做冒烟即可：
DRAFT（少信息）、PARTIAL（22 缺失）、READY（0 缺失）三种都要能出三格式且自检全绿。
