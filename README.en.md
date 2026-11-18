# Outbreak Investigation Report Writer (`outbreak-report-writing`)

**English** · [简体中文](README.md) · [繁體中文（台灣）](README.zh-TW.md) · [Deutsch](README.de.md) · [日本語](README.ja.md)

Turns the **only** fragmentary field information you have into an outbreak investigation report you can submit right now: the body follows Chinese CDC house style, whatever is still missing or unobtainable is listed at the end of the report by urgency, epidemiological figures are matched to the disease automatically, Word / PDF / Markdown export at any point — in two versions, raw and de-identified.

This is not a simple outbreak-report "template". It was reverse-engineered from the final reports among **1,300+ real outbreak dossiers**: the chapter skeleton from the measured ordering in 477 reports, the style parameters from statistics over 16,815 sentences, the disease criteria from observation windows and handling rules stated in the source texts. Note that the skill itself, its templates, the criteria it encodes and the reports it emits are **Chinese** — a Chinese CDC official-document format; these translations exist only so non-Chinese-speaking colleagues can read, install and extend it.

## What it solves

| The old problem | What this does |
|---|---|
| Data is incomplete, the report cannot be written, and command level needs first-hand material | Missing fields become red `〔待補P0-2〕` markers in the body — ship a readable draft now, and Appendix A says what is still missing and how urgent it is |
| Re-deciding section order and copying the previous report every time | Six fixed genre skeletons; pick a `stage` and go |
| Epidemic curves drawn as line charts with arbitrary bin widths | Bin width derives from the incubation period (norovirus 4–8 h, varicella 5–7 d), with first/last case and intervention points marked |
| One school class arrives as four rows in the line-list export | The `单位` (unit) field is normalised automatically — 18 test cases, including misspelled school names |
| Unsure which important information still needs investigating | The P0 items in Appendix A are the critical ones; a 12-question self-check walks through them |
| Closure report missing a cost-benefit analysis | Section 9 breaks costs down by the national standard categories and gives you the table |

> **⚠️ A GitHub clone does not include `vendor/`.** The `vendor/` tree (~150 MB: `spec`, `report_engine`, `flowfig`, `report_export`, `venv`) is excluded by `.gitignore` and must be obtained separately and placed in the skill root. Without it the **full engine** `scripts/flowreport.py` fails ("vendor 目录不完整"), while the **lightweight template engine** `scripts/build_report.py` below is self-contained and works out of the box.

## Install (two ways, pick one)

### A. Light — clone and go

```bash
git clone --depth 1 https://github.com/naliehu/outbreak-report-writing.git
mkdir -p ~/.dsh/skills
rsync -a --exclude=.git outbreak-report-writing/ ~/.dsh/skills/outbreak-report-writing/
python3 -m pip install --user jinja2 matplotlib python-docx
```

No `vendor/` in this mode, so only `scripts/build_report.py` works: event YAML (five fields is enough) + line-list CSV → six report genres + 4 figures + md/docx/pdf (plus a redacted copy) + Appendix A gap list graded P0 (24 h) / P1 (48 h) / P2 (before closure). No 93-field validation, no L1/L2/L3 finalisation gate, no stage snapshot, no cross-format consistency check — `scripts/flowreport.py doctor` will report a missing `vendor/spec`.

### B. Full — bring `vendor/` along

```bash
rsync -a --exclude=.git --exclude=__pycache__ \
  /path/to/complete-copy/ ~/.dsh/skills/outbreak-report-writing/
python3 ~/.dsh/skills/outbreak-report-writing/scripts/flowreport.py doctor   # all eight green before use
```

Adds `vendor/` (~150 MB): `report.json` (93 fields) → 11 chapters / 17 tables / 4 figures / 16-page PDF, gaps highlighted in place and graded L1/L2/L3 to decide whether finalisation is blocked, top-3 blockers on the cover, per-item collection routes in chapter 10, stage snapshots, and md=docx=pdf consistency verification.

`vendor/venv` is architecture-specific: on another platform the scripts fall back to system `python3`, so install `requirements.txt` there, or run `bash install.sh` (macOS/Linux) / `powershell -ExecutionPolicy Bypass -File install.ps1` (Windows) to rebuild the venv.

### Platform bundles (Releases)

| Platform | File | What you get |
|---|---|---|
| macOS (Apple Silicon) | `outbreak-report-writing-<ver>-macos-arm64.tar.gz` | ships `vendor/venv` (arm64, self-contained interpreter) — unpack and run, no pip and no system Python needed |
| macOS (Intel) | `outbreak-report-writing-<ver>-macos-x86_64.tar.gz` | ships `vendor/venv` (x86_64, self-contained interpreter) — unpack and run on Intel Macs, no pip needed |
| Windows (x64) | `outbreak-report-writing-<ver>-windows-x64.zip` | ships `vendor/` code without venv — run `install.ps1` once (needs Python 3.10+) |
| any | `git clone` | light mode works immediately; full mode needs your own `vendor/` |

PDF export has two routes. With LibreOffice installed (`brew install --cask libreoffice` on macOS; on Windows it lands under Program Files, or point `SOFFICE_BIN` at it) the pipeline is md → docx → pdf and the layout matches Word exactly. Without it, nothing breaks: the built-in PyMuPDF layout engine produces the PDF directly (all content, figures and pagination; layout is its own scheme, slightly different from the docx version). md/docx need nothing extra.

## Quick start

```bash
cd ~/.hermes/skills/outbreak-report-writing
PY="env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python"

# Five fields are enough to produce a draft
$PY scripts/build_report.py --event 事件.yaml \
    --stage initial --out ./我的输出 --formats md,docx,pdf

# Driven by a real case CSV (four figures generated automatically)
$PY scripts/build_report.py --event 事件.yaml \
    --stage initial --line-list 个案.csv \
    --out ./我的输出 --formats md,docx,pdf
```

The event YAML and the case CSV are files you provide yourself; the field list is in `references/intake-playbook.md`.

`--stage`: `initial` first report / `progress` progress report / `final` final report / `closure` closure application / `case` single case.

## Output: two versions at once

By default you get two files; the one ending in `-脱敏` (de-identified) is safe to send outside.

| Item | Raw version (internal) | De-identified version (external) |
|---|---|---|
| Name | 张一 | 张某 (numbered automatically when two people share a surname) |
| ID number / mobile / landline / e-mail | as-is | （略）(omitted) |
| Date of birth | 1995年7月30日 | （略）, age retained |
| Address | Dieburger Str. 78 Darmstadt, 64287 | （略） |
| Institution / administrative area / dates / case counts / attack rate | retained | retained |

Switches: `--privacy both` (default) / `raw` internal only / `redacted` external only.
The plugin exposes the same as `privacy`. Name lists are collected automatically from the event fields and the case CSV, and a regex catches ID numbers typed into the body by hand.

## Two paths

- **Lightweight template** (`scripts/build_report.py`): event YAML or line-list CSV → any of the six genres directly. Use this for single cases, ad-hoc work, or when you only have one exported table.
- **Full engine** (`scripts/flowreport.py`): `report.json` (93 fields / 11 chapters) → four figures + three formats + snapshots + a sign-off gate. Use this when you need a dozen consecutive progress reports inside a review-and-sign workflow.

The gap grading is the same criteria under two names: L1 blocks transmission = P0, L2 affects assessment = P1, L3 improves narrative = P2.

## Privacy

The original investigation dossiers are not in this repository and are not distributed with the skill.

## DSH plugin (DeepSeek Harness)

Besides working as a skill, the repository itself is a DSH plugin package: install it and your agent gains an `epi_report` tool — one sentence produces a report, no commands to memorise.

```bash
dsh plugin --profile web add github:naliehu/outbreak-report-writing
dsh --profile web          # effective after restart; just say "use epi_report for a first report"
```

Tool parameters: `action` (build / check), `event_path` (event YAML/JSON, required), `stage`
(initial / progress / final / closure / case), `line_list` (case CSV), `out_dir`, `formats`, `docx_profile`.

The plugin does very little, deliberately: find the skill directory → pick a Python interpreter → pass arguments → return artefact paths. How the report is written, which figures are drawn, how gaps are graded — all of it lives in `scripts/`, so one edit takes effect on both surfaces.

Dependencies degrade on demand:

| Installed | You get |
|---|---|
| python3 + pyyaml + jinja2 | Markdown body (figures and Word are skipped with a stated reason) |
| + matplotlib | plus four narrative figures and three distribution charts |
| + python-docx | plus Word; PDF always (PyMuPDF fallback if LibreOffice is absent) |

Install everything at once: `python3 -m pip install pyyaml jinja2 matplotlib python-docx`

Configuration (in the profile's `cordis.patch.yml`, entirely optional):

```yaml
- insert:
    - id: epi-report
      name: 'outbreak-report-writing'
      config:
        skillDir: ~/path/to/outbreak-report-writing   # auto-discovered by default
        python: /usr/bin/python3                      # prefers vendor/venv/bin/python
        outDir: ~/流调输出                             # defaults to <event dir>/流调输出
```

## Layout

```
SKILL.md                  the skill itself (criteria, workflow, style rules, pitfalls)
references/               depth material
  01 报告类型与骨架 → report-types.md (six genres, section by section)
  02 分病种要点.md        12 diseases: what to emphasise, where they get confused
  03 可视化作图规范.md     decision table + seven hard rules + captions
  06 文风与句式库.md       quantified style from 477 reports, seven functional patterns,
                           six rules for numbers, an explicit ban list
  intake-playbook.md      what to ask on site, and what to do when nobody knows
  toolchain.md            module contracts, Chinese font rendering, troubleshooting
templates/                five .j2 genre templates + disease_profiles.yaml (add your own diseases)
scripts/                  epi_core / epi_viz / build_report / md2docx / flowreport
plugin/                   Hermes plugin source (exposed as the epi_report tool)
tests/                    unit tests
```

## Promotion

1. **Copy the whole thing**: the `outbreak-report-writing/` directory (including `vendor/venv`, ~150 MB) — `python3 scripts/build_report.py` just runs, no network, no pip.
2. **Templates only**: take `templates/*.j2` + `references/06-文风与句式库.md` and fill them in by hand; filling them manually still yields a compliant report — half the value of this skill sits in that document.
3. **Install as a plugin**: copy `plugin/` to `~/.hermes/plugins/epi-report/` and Hermes gains the `epi_report` tool — one sentence and it is generated.
4. **Add a disease**: edit `templates/disease_profiles.yaml` only, no code changes.

## Known limitations

- No licensed administrative base map, so geographic output is limited to venue cards or lat/long bubble sketches — not publishable as a GIS thematic map.
- Incubation periods for typhoid, dengue, fever-with-thrombocytopenia syndrome, food-borne illness and chikungunya come from guidelines; those entries carry `verify: true` in the YAML, so check the current national scheme before use.
- Generations are inferred from onset dates (0.6 × typical incubation threshold), not topological derivation. When contact relationships are documented, the transmission chain wins.
- The Word layout uses 仿宋_GB2312; if the font is not installed it falls back to 宋体 silently.
