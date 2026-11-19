# 感染症疫学調査報告書の作成（`outbreak-report-writing`）

[English](README.en.md) · [简体中文](README.md) · [繁體中文（台灣）](README.zh-TW.md) · [Deutsch](README.de.md) · **日本語**

不完全な現場情報から、その場で提出できる疫学調査報告書を作ります。本文は中国CDCの公文書様式、未取得の疫学情報は緊急度順に末尾へ、図は疾患ごとに自動で揃い、Word／PDF／Markdown へ書き出し、原本版と匿名化版を同時に生成します。イベント情報と症例リストを渡せば草稿が出ます。何が足りないかは付録Aに書かれます。

章立て・文体パラメータ・疾患判定基準は 1,300 件余りの実在調査記録から逆算しています：477 件で章順、16,815 文で文体、原文の記載で判定基準。macOS と Windows のパッケージは解凍するだけで動きます。報告書本体は中国CDCの公文書（中国語）で、この翻訳は読む・導入する・拡張するためのものです。

## 何を解決するか

| 従来の困りごと | ここでの方法 |
|---|---|
| データが揃わず報告書が書けないが、指揮層は一次資料を必要としている | 欠けた項目は本文中の赤い `〔待補P0-2〕` になる。まず読める版を出し、付録Aが「何が足りないか、どれほど急ぐか」を示す |
| 毎回章の順序を考え直し、前回の報告書を写す | 六つの体裁ごとに固定の骨格。`stage` を選べばそのまま出力 |
| 流行曲線を折れ線で描き、間隔を適当に決める | 潜伏期から階級幅を自動決定（ノロウイルス4〜8時間、水痘5〜7日）。初発例・最終例・介入時点を明示 |
| 大疫情網のエクスポートで同じクラスが4行に分かれる | `单位`（所属）フィールドを自動正規化。18ケースのテスト済み（校名の誤字を含む） |
| どの重要情報をまだ調査すべきか分からない | 付録AのP0が核心となる情報。12項目のセルフチェックで順に確認 |
| 結案報告に費用便益分析が欠けている | 第9節で国家標準の科目ごとに分類し、表をそのまま提示 |

> **GitHub から clone した版には `vendor/` が含まれません**（約 150 MB、`.gitignore` で除外）。別途入手してスキルのルートに置いてください。無い場合フルエンジン `scripts/flowreport.py` は使えませんが、軽量版 `scripts/build_report.py` は影響を受けません。

## インストール

### プラットフォーム別パッケージ

| プラットフォーム | ファイル | 内容 |
|---|---|---|
| macOS（Apple Silicon） | `outbreak-report-writing-<ver>-macos-arm64.tar.gz` | arm64 インタプリタと依存を同梱、解凍するだけ |
| macOS（Intel） | `outbreak-report-writing-<ver>-macos-x86_64.tar.gz` | 同上（x86_64 ビルド） |
| Windows（x64） | `outbreak-report-writing-<ver>-windows-x64-embedded.zip` | インタプリタと依存を同梱、解凍するだけ |
| 任意 | `git clone` | 軽量版はそのまま使える；全量版は `vendor/` を自前で用意 |

PDF は二通り：LibreOffice があれば docx → pdf（Word と同一レイアウト）、無ければ内蔵 PyMuPDF が直接組版（内容と図は同じ、レイアウトは独自）。md/docx は外部ソフト不要。

### 中国本土からの利用

プラグインは npm に公開済み。ミラーを設定すれば 1 秒以内にインストールできます（0.5 MB）：

```bash
npm config set registry https://registry.npmmirror.com
dsh plugin add outbreak-report-writing
```

npm 版は軽量版（インタプリタと依存を含みません）。初回使用前に `bash install.sh`（または `install.ps1`）を一度実行してください。すぐ動く完全版は下のアーカイブを使ってください。

GitHub への直結が不安定な場合、URL の先頭にミラーを付けます：`https://ghfast.top/` または `https://ghproxy.net/`（使えなくなったらもう一方へ、バージョンは適宜変更）。

```bash
# プラグイン（約 0.5 MB）
dsh plugin add https://ghfast.top/https://github.com/naliehu/outbreak-report-writing/releases/download/v1.2.4/outbreak-report-writing-1.2.4.tgz

# フルパッケージ（約 90 MB、ファイル名は環境に合わせて変更）
curl -L -o obrw.tar.gz https://ghfast.top/https://github.com/naliehu/outbreak-report-writing/releases/download/v1.2.4/outbreak-report-writing-1.2.4-macos-arm64.tar.gz

# 依存は PyPI ミラーから
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

## クイックスタート

```bash
cd ~/.hermes/skills/outbreak-report-writing
PY="env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python"

# 5項目だけでも草案が出る
$PY scripts/build_report.py --event 事件.yaml \
    --stage initial --out ./我的输出 --formats md,docx,pdf

# 実在の症例CSVを入力にする（図4枚を自動生成）
$PY scripts/build_report.py --event 事件.yaml \
    --stage initial --line-list 个案.csv \
    --out ./我的输出 --formats md,docx,pdf
```

事案YAMLと症例CSVは自分で用意します。フィールド一覧は `references/intake-playbook.md` にあります。

`--stage`：`initial` 初回報告／`progress` 経過報告／`final` 結案報告／`closure` 結案申請書／`case` 単一症例。

## 出力：2版を同時に

既定では2ファイルが生成されます。`-脱敏`（匿名化済み）が付いた方はそのまま外部に出せます。

| 項目 | 原本版（内部） | 匿名化版（外部） |
|---|---|---|
| 氏名 | 张一 | 张某（同姓で別人の場合は自動で番号付与） |
| 身分証番号／携帯／固定電話／メール | そのまま | （略） |
| 生年月日 | 1995年7月30日 | （略）、年齢は保持 |
| 住所 | Dieburger Str. 78 Darmstadt, 64287 | （略） |
| 機関名／行政区／日付／症例数／罹患率 | 保持 | 保持 |

切り替え：`--privacy both`（既定）／`raw` は内部版のみ／`redacted` は外部版のみ。
プラグイン側のパラメータは `privacy`。氏名リストは事案フィールドと症例CSVから自動収集し、本文に手書きされた身分証番号は正規表現で捕捉します。

## 二つの経路

- **軽量テンプレート**（`scripts/build_report.py`）：事案YAMLまたは大疫情網CSV → 六体裁を直接出力。単一症例、臨時対応、エクスポート表が1枚しかない場合に。
- **フルエンジン**（`scripts/flowreport.py`）：`report.json`（93フィールド／11章）→ 図4枚＋3形式＋スナップショット＋署名ゲート。十数期の経過報告を連続して作り、審査・署名フローに載せる場合に。

両エンジンの欠測判定は同じ：L1 = P0、L2 = P1、L3 = P2。

## プライバシー

原本の調査記録は本リポジトリに含まれておらず、スキルにも同梱していません。

## DSHプラグイン（DeepSeek Harness）

スキルとして使うだけでなく、本リポジトリ自体がDSHプラグインパッケージです。導入するとエージェントに `epi_report` ツールが加わり、一言で報告書が出ます。コマンドを覚える必要はありません。

```bash
dsh plugin --profile web add github:naliehu/outbreak-report-writing
dsh --profile web          # 再起動後に有効。「epi_report で初回報告を出して」と伝えるだけ
```

ツールパラメータ：`action`（build／check）、`event_path`（事案YAML/JSON、必須）、`stage`
（initial／progress／final／closure／case）、`line_list`（症例CSV）、`out_dir`、`formats`、`docx_profile`。

プラグインの役割は意図的に小さく明確です：スキルディレクトリを探す → Pythonインタプリタを選ぶ → 引数を渡す → 生成物のパスを返す。報告書の書き方、図の描き方、欠測の格付けはすべて `scripts/` にあり、一度直せば両方に効きます。

依存関係は必要に応じて縮退します：

| 導入済み | 出力できるもの |
|---|---|
| python3 + pyyaml + jinja2 | Markdown本文（図とWordは理由を明記して省略） |
| さらに matplotlib | ナラティブ図4枚と分布図3枚を追加 |
| さらに python-docx | Wordを追加。PDFは常に出る（LibreOffice不在時はPyMuPDFで代替） |

一括導入：`python3 -m pip install pyyaml jinja2 matplotlib python-docx`

設定（プロファイルの `cordis.patch.yml` に記述、すべて省略可）：

```yaml
- insert:
    - id: epi-report
      name: 'outbreak-report-writing'
      config:
        skillDir: ~/path/to/outbreak-report-writing   # 既定では自動探索
        python: /usr/bin/python3                      # 既定では vendor/venv/bin/python を優先
        outDir: ~/流调输出                             # 既定は <事案ファイルと同じ階層>/流调输出
```

## 構成

```
SKILL.md                  スキル本体（判定基準、手順、文体の要点、落とし穴）
references/               深掘り資料
  01 報告書の種類と骨格 → report-types.md（六体裁を節ごとに）
  02 分病种要点.md        12疾患の力点と混同しやすい境界
  03 可视化作图规范.md     判断表＋ハードルール7条＋図表キャプション
  06 文风与句式库.md       477件の報告書から定量化した文体、機能文型7種、数字の6原則、禁止リスト
  intake-playbook.md       現場で何を聞くか、聞けないときどうするか
  toolchain.md             モジュール契約、中国語描画、トラブルシューティング
templates/                .j2体裁テンプレート5種＋disease_profiles.yaml（疾患は自分で追加可）
scripts/                  epi_core / epi_viz / build_report / md2docx / flowreport
plugin/                   Hermesプラグインのソース（epi_report ツールとして公開）
tests/                    単体テスト
```

## 配布

1. **丸ごとコピー**：`outbreak-report-writing/` ディレクトリ全体（`vendor/venv` 込み、約150 MB）を渡せば、`python3 scripts/build_report.py` がそのまま動きます。ネットワークもpipも不要。
2. **テンプレートだけ**：`templates/*.j2` と `references/06-文风与句式库.md` を持っていき手で埋めても、規範に沿った報告書になります。このスキルの価値の半分はこの文書にあります。
3. **プラグインとして導入**：`plugin/` を `~/.hermes/plugins/epi-report/` にコピーすれば、Hermes に `epi_report` ツールが加わり、一言で生成できます。
4. **疾患を追加**：`templates/disease_profiles.yaml` だけを編集。コードは触りません。

## 既知の制約

- 正式な行政区基図がないため、地理分布は会場カードか緯度経度のバブル模式図までです。GIS主題図としての外部公開はできません。
- 腸チフス、デング熱、血小板減少を伴う発熱症候群、食品媒介性疾患、チクングニアの潜伏期はガイドライン由来です。YAMLに `verify: true` を付けているので、使用前に現行の国家防控方案を確認してください。
- 世代は発症日からの推定（0.6×典型潜伏期の閾値）であり、トポロジー推論ではありません。接触関係が判明している場合は伝播連鎖を優先します。
- Wordレイアウトのフォント（仿宋_GB2312）はシステムへの導入が必要です。無い場合は宋体へ無言でフォールバックします。
