# Ausbruchsuntersuchungsbericht schreiben (`outbreak-report-writing`)

[English](README.en.md) · [简体中文](README.md) · [繁體中文（台灣）](README.zh-TW.md) · **Deutsch** · [日本語](README.ja.md)

Macht aus den **einzigen** bruchstückhaften Feldinformationen, die man hat, einen sofort berichtsfähigen Ausbruchsbericht: Der Text folgt dem chinesischen CDC-Berichtsstil, was noch fehlt oder nicht beschaffbar ist, wird am Berichtsende nach Dringlichkeit aufgelistet, epidemiologische Abbildungen werden der Krankheit entsprechend automatisch ergänzt, Export nach Word / PDF / Markdown jederzeit — in zwei Fassungen, roh und de-identifiziert.

Das hier ist keine einfache Ausbruchsbericht-„Vorlage". Es wurde aus den Abschlussberichten von **über 1.300 echten Ausbruchsakten** rückwärts rekonstruiert: Kapitelskelett aus der gemessenen Reihenfolge in 477 Berichten, Stilparameter aus der Statistik über 16.815 Sätze, Krankheitskriterien aus den in den Quellen genannten Beobachtungszeiträumen und Behandlungsregeln. Achtung: Der Skill selbst, seine Vorlagen, die kodierten Kriterien und die erzeugten Berichte sind **chinesisch** — ein Amtsformat des chinesischen CDC. Diese Übersetzungen dienen nur dazu, dass nicht chinesischsprachige Kolleginnen und Kollegen das Paket lesen, installieren und erweitern können.

## Welches Problem das löst

| Das alte Problem | Was hier passiert |
|---|---|
| Daten fehlen, der Bericht ist nicht schreibbar, die Führungsebene braucht aber Primärmaterial | Fehlende Felder werden zu roten `〔待補P0-2〕`-Markern im Text — jetzt eine lesbare Fassung abgeben, Anhang A sagt, was noch fehlt und wie dringend |
| Jedes Mal Kapitelreihenfolge neu überlegen und den letzten Bericht abschreiben | Sechs feste Genre-Skelette; `stage` wählen und los |
| Epikurven als Liniendiagramm mit willkürlicher Klassierung | Klassenbreite aus der Inkubationszeit (Norovirus 4–8 h, Varizellen 5–7 d), erster/letzter Fall und Interventionszeitpunkte markiert |
| Eine Schulklasse erscheint als vier Zeilen im Linelist-Export | Feld `单位` (Einheit) wird automatisch normalisiert — 18 Testfälle, inklusive falsch geschriebener Schulnamen |
| Unklar, welche wichtigen Angaben noch zu ermitteln sind | Die P0-Punkte in Anhang A sind die entscheidenden; eine 12-Punkte-Selbstprüfung geht sie durch |
| Abschlussbericht ohne Kosten-Nutzen-Analyse | Abschnitt 9 gliedert die Kosten nach den nationalen Standardkategorien und liefert die Tabelle |

## Schnellstart

```bash
cd ~/.hermes/skills/outbreak-report-writing
PY="env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python"

# Fünf Felder genügen für einen Entwurf
$PY scripts/build_report.py --event examples/03-残缺输入/event.yaml \
    --stage initial --out ./我的输出 --formats md,docx,pdf

# Mit echter Fall-CSV als Grundlage (vier Abbildungen automatisch)
$PY scripts/build_report.py --event examples/02-某实验学校水痘-真实个案/event.yaml \
    --stage initial --line-list examples/02-某实验学校水痘-真实个案/个案-已脱敏.csv \
    --out ./我的输出 --formats md,docx,pdf
```

Die Beispielpfade sind die chinesischen Originalordnernamen — unverändert übernehmen.

`--stage`: `initial` Erster Bericht / `progress` Verlaufsbericht / `final` Abschlussbericht / `closure` Abschlussantrag / `case` Einzelfall.

## Ausgabe: zwei Fassungen gleichzeitig

Standardmäßig entstehen zwei Dateien; die mit der Endung `-脱敏` (de-identifiziert) kann unbedenklich nach außen.

| Position | Rohe Fassung (intern) | De-identifizierte Fassung (extern) |
|---|---|---|
| Name | 冀斌 | 冀某 (bei gleichem Nachnamen automatisch durchnummeriert) |
| Ausweisnummer / Mobil / Festnetz / E-Mail | unverändert | （略）(entfernt) |
| Geburtsdatum | 1995年7月30日 | （略）, Alter bleibt erhalten |
| Adresse | Dieburger Str. 78 Darmstadt, 64287 | （略） |
| Einrichtung / Verwaltungsbezirk / Datum / Fallzahlen / Befallsrate | bleibt | bleibt |

Schalter: `--privacy both` (Standard) / `raw` nur intern / `redacted` nur extern.
Im Plugin heißt der Parameter `privacy`. Namenslisten werden automatisch aus den Ereignisfeldern und der Fall-CSV gezogen; ein Regex fängt von Hand in den Text getippte Ausweisnummern.

## Zwei Wege

- **Leichtgewichtige Vorlage** (`scripts/build_report.py`): Ereignis-YAML oder Linelist-CSV → eines der sechs Genres direkt. Für Einzelfälle, Ad-hoc-Arbeit oder wenn nur eine exportierte Tabelle vorliegt.
- **Vollmaschine** (`scripts/flowreport.py`): `report.json` (93 Felder / 11 Kapitel) → vier Abbildungen + drei Formate + Snapshots + Freigabe-Gate. Wenn ein Dutzend aufeinanderfolgender Verlaufsberichte durch Prüfung und Zeichnung müssen.

Die Lückenbewertung ist dieselbe Systematik unter zwei Namen: L1 blockiert Übertragung = P0, L2 beeinflusst die Bewertung = P1, L3 verbessert die Darstellung = P2.

## Datenschutz

Die Originalakten der Ermittlungen sind nicht in diesem Repository und werden nicht mit dem Skill verteilt.

## DSH-Plugin (DeepSeek Harness)

Das Repository ist nicht nur ein Skill, sondern selbst ein DSH-Plugin-Paket: Installiert bekommt der Agent ein Werkzeug `epi_report` — ein Satz genügt, keine Befehle zum Merken.

```bash
dsh plugin --profile web add github:naliehu/outbreak-report-writing
dsh --profile web          # nach Neustart aktiv; einfach sagen: "nutze epi_report für einen Erster-Bericht"
```

Werkzeugparameter: `action` (build / check), `event_path` (Ereignis-YAML/JSON, Pflicht), `stage`
(initial / progress / final / closure / case), `line_list` (Fall-CSV), `out_dir`, `formats`, `docx_profile`.

Das Plugin tut bewusst wenig und klar umrissen: Skill-Verzeichnis finden → Python-Interpreter wählen → Argumente übergeben → Artefaktpfade zurückgeben. Wie der Bericht geschrieben, welche Abbildungen gezeichnet, wie Lücken bewertet werden, steht alles in `scripts/` — eine Änderung wirkt auf beiden Oberflächen.

Abhängigkeiten degradieren bei Bedarf:

| Installiert | Ergebnis |
|---|---|
| python3 + pyyaml + jinja2 | Markdown-Text (Abbildungen und Word entfallen mit Begründung) |
| + matplotlib | dazu vier erzählende Abbildungen und drei Verteilungscharts |
| + python-docx | dazu Word; PDF zusätzlich, wenn LibreOffice vorhanden ist |

Alles auf einmal: `python3 -m pip install pyyaml jinja2 matplotlib python-docx`

Konfiguration (in `cordis.patch.yml` des Profils, vollständig optional):

```yaml
- insert:
    - id: epi-report
      name: 'outbreak-report-writing'
      config:
        skillDir: ~/path/to/outbreak-report-writing   # standardmäßig automatisch gesucht
        python: /usr/bin/python3                      # bevorzugt vendor/venv/bin/python
        outDir: ~/流调输出                             # Standard: <Ereignisordner>/流调输出
```

## Aufbau

```
SKILL.md                  der Skill selbst (Kriterien, Ablauf, Stilregeln, Fallstricke)
references/               Tiefenmaterial
  01 报告类型与骨架 → report-types.md (sechs Genres, Kapitel für Kapitel)
  02 分病种要点.md        12 Krankheiten: Schwerpunkte, Verwechslungsgefahr
  03 可视化作图规范.md     Entscheidungstabelle + sieben harte Regeln + Bildunterschriften
  06 文风与句式库.md       quantifizierter Stil aus 477 Berichten, sieben Funktionsmuster,
                           sechs Zahlenregeln, eine ausdrückliche Verbotsliste
  intake-playbook.md       was man vor Ort fragt, und was, wenn niemand es weiß
  toolchain.md             Modulverträge, chinesische Schriftdarstellung, Fehlersuche
templates/                fünf .j2-Genre-Vorlagen + disease_profiles.yaml (eigene Krankheiten ergänzen)
scripts/                  epi_core / epi_viz / build_report / md2docx / flowreport
plugin/                   Hermes-Plugin-Quellcode (als Werkzeug epi_report exponiert)
tests/                    Unit-Tests
examples/                 drei lauffähige Beispiele mit erzeugter Ausgabe
```

## An Kolleginnen und Kollegen weitergeben

1. **Alles kopieren**: das Verzeichnis `outbreak-report-writing/` (inklusive `vendor/venv`, ca. 150 MB) — `python3 scripts/build_report.py` läuft sofort, ohne Netz, ohne pip.
2. **Nur die Vorlagen**: `templates/*.j2` + `references/06-文风与句式库.md` mitnehmen und von Hand füllen — auch manuell gefüllt ergibt das einen regelkonformen Bericht; die Hälfte des Werts steckt in diesem Dokument.
3. **Als Plugin installieren**: `plugin/` nach `~/.hermes/plugins/epi-report/` kopieren, Hermes hat dann das Werkzeug `epi_report` — ein Satz, fertig.
4. **Krankheit ergänzen**: nur `templates/disease_profiles.yaml` bearbeiten, kein Code.

## Bekannte Grenzen

- Keine lizenzierte Verwaltungskarte, daher räumliche Darstellung nur als Ortskarten oder Lat/Long-Blasenskizze — nicht als GIS-Themenkarte publizierbar.
- Inkubationszeiten für Typhus, Dengue, Fieber mit Thrombozytopenie-Syndrom, lebensmittelbedingte Erkrankungen und Chikungunya stammen aus Leitlinien; diese Einträge tragen `verify: true`, vor Gebrauch das aktuelle nationale Schema prüfen.
- Generationen werden aus Erkrankungsdaten geschätzt (0,6 × typische Inkubationsschwelle), nicht topologisch hergeleitet. Bei dokumentierten Kontakten gilt die Übertragungskette.
- Das Word-Layout nutzt 仿宋_GB2312; fehlt die Schrift, wird stillschweigend auf 宋体 zurückgefallen.
