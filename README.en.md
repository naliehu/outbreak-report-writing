# Outbreak Investigation Report Writer (`outbreak-report-writing`)

**English** · [简体中文](README.md) · [繁體中文（台灣）](README.zh-TW.md) · [Deutsch](README.de.md) · [日本語](README.ja.md)

Turn the **incomplete** information you actually have in the field into an outbreak investigation report you can submit the same day: the body follows Chinese CDC house style, missing pieces are never faked, figures are generated per disease, and Word / PDF / Markdown export at any point.

This is not a template someone improvised. It was reverse-engineered from **1,300+ real outbreak dossiers** (all Wuxi City communicable-disease emergency files, 2011–2026: typhoid and paratyphoid in Jiangyin, cholera in Yixing, mpox in Liangxi, imported dengue, fever-with-thrombocytopenia syndrome, plus one-page closure applications sent from districts to the municipal CDC). The section skeleton comes from the measured ordering of 477 reports, the style parameters from statistics over 16,815 sentences, and the disease criteria from observation windows and handling rules stated in the source texts.

## What it solves

| The old problem | What this does |
|---|---|
| Data is incomplete, so the report stalls for three days | Missing fields become red `〔待補P0-2〕` markers in the body — ship a readable draft now, and Appendix A tells you what is still missing and how urgent it is |
| Re-deciding section order and copying last year's report every time | Six fixed genre skeletons; pick a `stage` and go |
| Epidemic curves drawn as line charts with arbitrary bin widths | Bin width derives from the incubation period (norovirus 4–8 h, varicella 5–7 d), with first/last case and intervention points marked |
| One school class arrives as four rows in the line list export | The `单位` (unit) field is normalised automatically — 18 test cases, including misspelled school names |
| Unsure which pieces of information are still missing | Appendix A's P0 items are the critical ones; a 12-question self-check walks through them |
| Closure report missing a cost-benefit analysis | Section 9 breaks costs down by national standard categories and gives you the table |

## Quick start

```bash
cd ~/.hermes/skills/outbreak-report-writing
PY="env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python"

# Five fields are enough to produce a draft
$PY scripts/build_report.py --event examples/03-残缺输入/event.yaml \
    --stage initial --out ./我的输出 --formats md,docx,pdf

# Driven by a real case CSV (four figures generated automatically)
$PY scripts/build_report.py --event examples/02-某实验学校水痘-真实个案/event.yaml \
    --stage initial --line-list examples/02-某实验学校水痘-真实个案/个案-已脱敏.csv \
    --out ./我的输出 --formats md,docx,pdf
```

`--stage`: `initial` first report / `progress` progress report / `final` final report / `closure` closure application / `case` single case.

## Output: two versions at once

By default you get two files; the one ending in `-脱敏` (de-identified) is safe to send outside.

| Item | Internal version | De-identified version |
|---|---|---|
| Name | 张志强 | 张某 (numbered automatically when two people share a surname) |
| ID number / mobile / landline / e-mail | as-is | （略）(omitted) |
| Date of birth | 2008年12月23日 | （略）, age retained |
| Address | 石塘湾村27号3幢2单元501室 | 石塘湾村（略）— truncated to village/community level |
| Institution / administrative area / dates / case counts / attack rate | retained | retained |

Switch: `--privacy both` (default) / `raw` internal only / `redacted` external only. The plugin exposes the same as `privacy`. Name lists are collected automatically from the event fields and the case CSV, and a regex catches ID numbers typed into the body by hand.

## Two paths

- **Lightweight template** (`scripts/build_report.py`): event YAML or case CSV export → any of the six genres. Use this for single cases, ad-hoc work, or when you only have one exported table.
- **Full engine** (`scripts/flowreport.py`): `report.json` (93 fields / 11 chapters) → four figures + three formats + snapshots + a sign-off gate. Use this when you are producing a dozen consecutive progress reports inside a review workflow.

The gap grading is the same criteria under two names: L1 blocks transmission = P0, L2 affects assessment = P1, L3 improves narrative = P2.

## Privacy

Every example in this repository is already de-identified: names, ID numbers, parents' names, phone numbers and street addresses are removed; institutions are written as 「某高级中学／某实验学校」 ("a senior high school / an experimental school"); only epidemiological structure and statistical definitions remain. The original dossiers are **not** in this repository and are not distributed with the skill.

## DSH plugin (DeepSeek Harness)

Besides working as a skill, the repository *is* a DSH plugin package. Install it and your agent gains an `epi_report` tool — one sentence produces a report, no commands to memorise.

```bash
dsh plugin --profile web add github:naliehu/outbreak-report-writing
dsh --profile web          # effective after restart; just say "use epi_report for a first report"
```

Tool parameters: `action` (build / check), `event_path` (event YAML/JSON, required), `stage` (initial / progress / final / closure / case), `line_list` (case CSV), `out_dir`, `formats`, `docx_profile`.

The plugin does very little, deliberately: find the skill directory → pick a Python interpreter → pass arguments → return artefact paths. How the report is written, which figures are drawn, how gaps are graded — all of that lives in `scripts/`, so one edit takes effect on both surfaces.

Dependencies degrade gracefully:

| Installed | You get |
|---|---|
| python3 + pyyaml + jinja2 | Markdown body (figures and Word are skipped with a stated reason) |
| + matplotlib | plus four narrative figures and three distribution charts |
| + python-docx | plus Word; PDF as well if LibreOffice is present |

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
  01 report types & skeletons → report-types.md (six genres, section by section)
  02 per-disease notes      12 diseases: what to emphasise, where they get confused
  03 visualisation rules    decision table + seven hard rules + captions
  06 style & sentence bank  quantified style from 477 reports, seven functional patterns,
                            six rules for numbers, an explicit ban list
  intake-playbook.md       what to ask on site, and what to do when nobody knows
  toolchain.md             module contracts, Chinese font rendering, troubleshooting
templates/                five .j2 genre templates + disease_profiles.yaml (add your own diseases)
scripts/                  epi_core / epi_viz / build_report / md2docx / flowreport
plugin/                   Hermes plugin source (exposed as the epi_report tool)
tests/                    unit tests
examples/                 three runnable examples with generated output
```

## Handing it to colleagues

1. **Copy the whole thing**: the `outbreak-report-writing/` directory (including `vendor/venv`, ~150 MB) — `python3 scripts/build_report.py` just runs, no network, no pip.
2. **Templates only**: take `templates/*.j2` + `references/06-文风与句式库.md` and fill them in by hand; half the value of this skill sits in that document.
3. **Install as a plugin**: copy `plugin/` to `~/.hermes/plugins/epi-report/` and Hermes gains the `epi_report` tool.
4. **Add a disease**: edit `templates/disease_profiles.yaml` only, no code changes.

## Known limitations

- No licensed administrative base map, so geographic output is limited to venue cards or lat/long bubble sketches — not publishable as a GIS thematic map.
- Incubation and isolation periods for typhoid, dengue, fever-with-thrombocytopenia syndrome, food-borne illness and chikungunya come from guidelines rather than the local corpus; those entries carry `verify: true` in the YAML. Check the current national scheme before use.
- Generations are inferred from onset dates (0.6 × typical incubation threshold), not topology. When contact relationships are documented, the transmission chain wins.
- The Word layout uses 仿宋_GB2312; if the font is not installed it falls back to 宋体 silently.

## Language

The skill, its templates, its generated output and the regulatory criteria it encodes are **Chinese** — this is a Chinese CDC reporting format. These translated READMEs exist so non-Chinese-speaking collaborators can evaluate, install and extend the package; they do not change what the tool emits.
