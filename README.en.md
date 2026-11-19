# Outbreak Investigation Report Writer (`outbreak-report-writing`)

**English** · [简体中文](README.md) · [繁體中文（台灣）](README.zh-TW.md) · [Deutsch](README.de.md) · [日本語](README.ja.md)

Turns incomplete field information into an outbreak report you can submit now: CDC house style, missing items listed at the end by urgency, figures matched to the disease, Word / PDF / Markdown export, raw and de-identified versions. Give it an event file and a case list and it drafts; Appendix A says what is missing and how urgently.

Chapter order, style parameters and disease criteria are reverse-engineered from 1,300+ real dossiers: 477 reports for chapter order, 16,815 sentences for style, source wording for criteria. Both macOS and Windows bundles run unpacked. The reports themselves are Chinese CDC official documents; these translations are for reading, installing and extending the skill.

## What it solves

| The old problem | What this does |
|---|---|
| Data is incomplete, the report cannot be written, and command level needs first-hand material | Missing fields become red `〔待補P0-2〕` markers in the body — ship a readable draft now, and Appendix A says what is still missing and how urgent it is |
| Re-deciding section order and copying the previous report every time | Six fixed genre skeletons; pick a `stage` and go |
| Epidemic curves drawn as line charts with arbitrary bin widths | Bin width derives from the incubation period (norovirus 4–8 h, varicella 5–7 d), with first/last case and intervention points marked |
| One school class arrives as four rows in the line-list export | The `单位` (unit) field is normalised automatically — 18 test cases, including misspelled school names |
| Unsure which important information still needs investigating | The P0 items in Appendix A are the critical ones; a 12-question self-check walks through them |
| Closure report missing a cost-benefit analysis | Section 9 breaks costs down by the national standard categories and gives you the table |

> **A GitHub clone does not include `vendor/`** (~150 MB, excluded by `.gitignore`); obtain it separately and place it in the skill root. Without it the full engine `scripts/flowreport.py` is unavailable; the light engine `scripts/build_report.py` is unaffected.

## Install

### Platform bundles (Releases)

| Platform | File | Contents |
|---|---|---|
| macOS (Apple Silicon) | `outbreak-report-writing-<ver>-macos-arm64.tar.gz` | bundled arm64 interpreter and dependencies; unpack and run |
| macOS (Intel) | `outbreak-report-writing-<ver>-macos-x86_64.tar.gz` | same, x86_64 build |
| Windows (x64) | `outbreak-report-writing-<ver>-windows-x64-embedded.zip` | bundled interpreter and dependencies; unpack and run |
| any | `git clone` | light mode works as-is; full mode needs your own `vendor/` |

PDF has two routes: with LibreOffice it goes docx → pdf and matches Word; without it the built-in PyMuPDF engine lays it out directly — same content and figures, its own layout. md/docx need no external program.

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

Both engines grade gaps the same way: L1 = P0, L2 = P1, L3 = P2.

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
