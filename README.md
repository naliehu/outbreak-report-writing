# 传染病流调报告撰写技能（outbreak-report-writing）

[English](README.en.md) · **简体中文** · [繁體中文（台灣）](README.zh-TW.md) · [Deutsch](README.de.md) · [日本語](README.ja.md)

把不完整的现场信息变成一份当下就能上报的流调报告：正文按疾控体例写，缺的流调信息按紧迫程度列在末尾，配图按病种自动配齐，Word／PDF／Markdown 随时导出，原版与脱敏版各一份。给它事件信息和个案表就能出稿，缺什么、多急，附录 A 会写清楚。

章节骨架、文风参数与病种判据从 1300 余份真实流调报告反向提炼：477 份定章节顺序，16815 句定文风，原文口径定判据。macOS 与 Windows 包都是解压即用。

## 解决什么问题

| 老问题 | 这里的做法 |
|---|---|
| 数据没齐，报告写不下去，指挥层需要看到一手资料 | 缺的字段变成正文里的红色〔待补P0-2〕，先出一版能看的，附录 A 告诉你还差什么、多急 |
| 每次都要重新想章节顺序、抄上回的报告 | 六种体裁固定骨架，选 stage 直接出 |
| 流行曲线画成折线、间隔随便定 | 按潜伏期自动定分箱（诺如 4–8 小时、水痘 5–7 天），标注首末例与干预时点 |
| 大疫情网导出的个案表一个班拆成四行 | `单位` 字段自动归一（18 组用例覆盖，含校名错字） |
| 写完不知道还需流调哪些重要信息 | 附录 A 的 P0 就是核心信息，自检 12 问逐条过 |
| 结案报告缺成本效益分析 | 第九节按国家标准科目分项，直接给表格 |

> **从 GitHub clone 的版本不含 `vendor/`**（约 150 MB，被 `.gitignore` 排除），需另行取得并放回技能根目录。缺它时全量引擎 `scripts/flowreport.py` 不可用，轻量引擎 `scripts/build_report.py` 不受影响。

## 安装

### 平台包（Releases）

| 平台 | 文件 | 内容 |
|---|---|---|
| macOS（Apple Silicon） | `outbreak-report-writing-<ver>-macos-arm64.tar.gz` | 含 `vendor/venv`（arm64 独立解释器 + 依赖），解压改路径即用 |
| macOS（Intel） | `outbreak-report-writing-<ver>-macos-x86_64.tar.gz` | 同上，x86_64 版 |
| Windows（x64） | `outbreak-report-writing-<ver>-windows-x64-embedded.zip` | 含 `vendor/python`（CPython 3.12 + 依赖），解压即用，不碰本机 Python |
| 任意平台 | `git clone` | 轻量版直接可用；全量需自备 `vendor/` |

PDF 两种出法：装了 LibreOffice 走 docx→pdf，版式与 Word 一致；没装则自动用内置 PyMuPDF 排版，内容与图表齐全，版式另成一套。md/docx 不依赖外部程序。

`vendor/venv` 按打包机器的架构编译，换平台会失效：脚本与插件自动回退到系统 `python3`，或跑一次 `install.sh`（macOS／Linux）／`install.ps1`（Windows）重建。

### 中国大陆网络

GitHub 直连不稳时，把域名换成镜像前缀即可（`https://ghfast.top/`、`https://ghproxy.net/`，一个失效就换另一个；版本号按需要改）：

```bash
# 装插件（约 0.5 MB）
dsh plugin add https://ghfast.top/https://github.com/naliehu/outbreak-report-writing/releases/download/v1.2.4/outbreak-report-writing-1.2.4.tgz

# 下载免安装包（约 90 MB，文件名换成对应平台）
curl -L -o obrw.tar.gz https://ghfast.top/https://github.com/naliehu/outbreak-report-writing/releases/download/v1.2.4/outbreak-report-writing-1.2.4-macos-arm64.tar.gz

# 依赖走国内 PyPI 镜像
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

## 快速上手

```bash
cd ~/.hermes/skills/outbreak-report-writing
# 全量装法用 venv 解释器；轻量装法把这行换成 PY="python3"
PY="env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python"

# 只有五个字段也能出稿
$PY scripts/build_report.py --event 事件.yaml \
    --stage initial --out ./我的输出 --formats md,docx,pdf

# 真实个案 CSV 驱动（自动出四张图）
$PY scripts/build_report.py --event 事件.yaml \
    --stage initial --line-list 个案.csv \
    --out ./我的输出 --formats md,docx,pdf
```

事件 YAML 与个案 CSV 自己提供，字段清单见 `references/intake-playbook.md`。

`--stage`：`initial` 初次／`progress` 进程／`final` 结案／`closure` 结案申请单／`case` 单例病例。

## 输出：同时给你两版

成稿默认出两份，`-脱敏` 那一份可以直接发出去：

| 项目 | 未脱敏版（内部） | 脱敏版（外发） |
|---|---|---|
| 姓名 | 张一 | 张某（同姓不同人自动加序号） |
| 身份证 / 手机 / 固话 / 邮箱 | 原样 | （略） |
| 出生日期 | 1995年7月30日 | （略），年龄保留 |
| 住址 | Dieburger Str. 78 Darmstadt, 64287 |（略）
| 机构 / 行政区 / 日期 / 病例数 / 罹患率 | 保留 | 保留 |

开关：`--privacy both`（默认）／`raw` 只出内部版／`redacted` 只出外发版。
插件里对应参数 `privacy`。人名清单自动从事件字段和个案 CSV 里取，正则可兜住手工写进正文的证件号。

## 两条路径

- **轻量模板**（`scripts/build_report.py`）：事件 YAML 或大疫情网 CSV → 六种体裁直出。单例、临时、只有一份导出表时用这个。
- **全量引擎**（`scripts/flowreport.py`）：report.json（93 字段／11 章）→ 四图 + 三格式 + 快照 + 签发门禁。要连出十几期进程报告、进审签流程时用这个。

两套引擎的缺项分级同源：L1 = P0，L2 = P1，L3 = P2。

## 隐私

原始流调卷宗不在本仓库内，也未随技能分发。

## DSH 插件（DeepSeek Harness）

除了当技能用，本仓库本身就是一个 DSH 插件包：装进去之后，代理多出一个 `epi_report` 工具，
一句话就能出稿，不用记命令。

```bash
dsh plugin --profile web add github:naliehu/outbreak-report-writing
dsh --profile web          # 重启后生效，直接说「用 epi_report 出一份初次报告」
```

Windows 推荐用免安装包（自带解释器与依赖，本机不需要装 Python）：

```powershell
# 解压 outbreak-report-writing-<ver>-windows-x64-embedded.zip 后，在该目录执行
dsh plugin --profile desktop add .\outbreak-report-writing-1.2.4-windows-x64-embedded
```

`package.json` 的 `files` 里列了 `vendor`，所以 `dsh plugin add` 会把整只解释器一起复制进
`node_modules`，插件按 `vendor\venv\Scripts\python.exe` → `vendor\python\python.exe` → `python`
的顺序挑，命中第一个就够用；同理，从 git 装（无 `vendor/`）时会退回系统的 `python`。

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

一次性装齐：`python3 -m pip install -r requirements.txt`（Windows 用 `python -m pip install -r requirements.txt`；
七个依赖是 pyyaml、jinja2、matplotlib、python-docx、jsonschema、pypdf、pymupdf）。

配置（写在 profile 的 `cordis.patch.yml` 里，可全部省略）：

```yaml
- insert:
    - id: epi-report
      name: 'outbreak-report-writing'
      config:
        skillDir: ~/path/to/outbreak-report-writing   # 默认自动查找
        python: /usr/bin/python3                      # 默认优先用 vendor/venv，其次 vendor/python
                                                      # Windows 例：C:\tools\obrw\vendor\python\python.exe
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
```

## 推广

1. **整体拷走**：`outbreak-report-writing/` 整个目录（含 `vendor/venv`，约 150 MB）给同事，`python3 scripts/build_report.py` 就能跑，不需要联网、不需要 pip。
2. **只要模板**：把 `templates/*.j2` + `references/06-文风与句式库.md` 拷走，手工填也是一份合规报告——技能的价值有一半在这个文档里。
3. **装成插件**：把 `plugin/` 拷到 `~/.hermes/plugins/epi-report/`，Hermes 里就有 `epi_report` 工具，一句话生成。
4. **加病种**：只改 `templates/disease_profiles.yaml`，不动代码。

## 已知限制

- 没有合法行政区底图，地理分布只能做场所卡片／经纬度气泡示意图，不能当 GIS 专题图对外。
- 伤寒、登革热、发热伴、食源性、基孔肯雅的潜伏期取自指南，YAML 里标了 `verify: true`，用前查当期方案。
- 代际由发病时间推算（0.6×常见潜伏期阈值），不是拓扑推导；有确切接触关系时以传播链为准。
- Word 版式的字体（仿宋_GB2312）需系统已安装，否则回退到宋体，不报错。
