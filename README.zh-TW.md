# 傳染病疫情調查報告撰寫技能（`outbreak-report-writing`）

[English](README.en.md) · [简体中文](README.md) · **繁體中文（台灣）** · [Deutsch](README.de.md) · [日本語](README.ja.md)

把不完整的現場資訊變成一份當下就能陳報的疫調報告：本文依疾管機關體例撰寫，暫缺的疫調資訊依急迫程度列在最後，圖表依病種自動備齊，Word／PDF／Markdown 隨時匯出，原版與去識別化版各一份。給它事件檔和個案表就能出稿，缺什麼、多急，附錄 A 會寫清楚。

章節骨架、文風參數與病種判準從 1300 餘份真實疫調報告反向提煉：477 份定章節順序，16,815 句定文風，原文口徑定判準。macOS 與 Windows 包都是解壓即用。報告本身是中國疾控公文（中文），這幾份翻譯只是為了讓不諳中文的協力者能讀懂、安裝與擴充。

## 解決什麼問題

| 原本的困境 | 這裡的做法 |
|---|---|
| 資料沒齊、報告寫不下去，但指揮層需要看到第一手資料 | 缺漏的欄位變成本文裡的紅色 `〔待補P0-2〕`，先出一版能看的，附錄 A 告訴你還缺什麼、多急 |
| 每次都要重新想章節順序、抄上一份報告 | 六種體裁固定骨架，選好 stage 直接產出 |
| 流行曲線畫成折線、組距隨便定 | 依潛伏期自動決定組距（諾羅病毒 4–8 小時、水痘 5–7 天），標註首例、末例與介入時點 |
| 大疫情網匯出的個案表，同一個班級被拆成四列 | `單位` 欄位自動正規化（涵蓋 18 組案例，含校名錯字） |
| 寫完不知道還需疫調哪些重要資訊 | 附錄 A 的 P0 就是核心資訊，12 項自我檢查逐條核對 |
| 結案報告缺成本效益分析 | 第九節依國家標準科目分項，直接給表格 |

> **從 GitHub clone 的版本不含 `vendor/`**（約 150 MB，被 `.gitignore` 排除），需另行取得並放回技能根目錄。缺它時全量引擎 `scripts/flowreport.py` 不可用，輕量引擎 `scripts/build_report.py` 不受影響。

## 安裝

### 平台包

| 平台 | 檔案 | 內容 |
|---|---|---|
| macOS（Apple Silicon） | `outbreak-report-writing-<ver>-macos-arm64.tar.gz` | 內含 `vendor/venv`（arm64 獨立解譯器 + 相依套件），解壓改路徑即用 |
| macOS（Intel） | `outbreak-report-writing-<ver>-macos-x86_64.tar.gz` | 同上，x86_64 版 |
| Windows（x64） | `outbreak-report-writing-<ver>-windows-x64-embedded.zip` | 內含 `vendor/python`（CPython 3.12 + 相依套件），解壓即用，不碰本機 Python |
| 任意平台 | `git clone` | 輕量版直接可用；全量需自備 `vendor/` |

PDF 兩種出法：裝了 LibreOffice 走 docx→pdf，版式與 Word 一致；沒裝則自動用內建 PyMuPDF 排版，內容與圖表齊全，版式另成一套。md/docx 不依賴外部程式。

`vendor/venv` 依打包機器的架構編譯，換平台會失效：腳本與外掛會自動回退到系統 `python3`，或跑一次 `install.sh`（macOS／Linux）／`install.ps1`（Windows）重建。

## 快速上手

```bash
cd ~/.hermes/skills/outbreak-report-writing
PY="env -u PYTHONPATH -u VIRTUAL_ENV vendor/venv/bin/python"

# 只有五個欄位也能出稿
$PY scripts/build_report.py --event 事件.yaml \
    --stage initial --out ./我的输出 --formats md,docx,pdf

# 以真實個案 CSV 驅動（自動產出四張圖）
$PY scripts/build_report.py --event 事件.yaml \
    --stage initial --line-list 个案.csv \
    --out ./我的输出 --formats md,docx,pdf
```

事件 YAML 與個案 CSV 請自行準備，欄位清單見 `references/intake-playbook.md`。

`--stage`：`initial` 初次／`progress` 進程／`final` 結案／`closure` 結案申請單／`case` 單一病例。

## 輸出：同時給你兩版

完稿預設產出兩份，檔名帶 `-脱敏` 的那一份可以直接對外發出：

| 項目 | 未去識別化版（內部） | 去識別化版（對外） |
|---|---|---|
| 姓名 | 张一 | 张某（同姓不同人自動加序號） |
| 身分證號／手機／市話／電子郵件 | 原樣 | （略） |
| 出生日期 | 1995年7月30日 | （略），年齡保留 |
| 住址 | Dieburger Str. 78 Darmstadt, 64287 | （略） |
| 機構／行政區／日期／病例數／侵襲率 | 保留 | 保留 |

開關：`--privacy both`（預設）／`raw` 只出內部版／`redacted` 只出對外版。
外掛對應參數為 `privacy`。人名清單會自動從事件欄位與個案 CSV 取得，正則表達式可攔住手動寫進本文的證件號碼。

## 兩條路徑

- **輕量範本**（`scripts/build_report.py`）：事件 YAML 或大疫情網 CSV → 六種體裁直出。單一病例、臨時任務、手上只有一份匯出表時用這個。
- **完整引擎**（`scripts/flowreport.py`）：`report.json`（93 個欄位／11 章）→ 四張圖 + 三種格式 + 快照 + 簽核閘門。要連續產出十幾期進程報告、進入審簽流程時用這個。

兩套引擎的缺漏分級同源：L1 = P0，L2 = P1，L3 = P2。

## 隱私

原始疫調卷宗不在本倉庫內，也未隨技能散布。

## DSH 外掛（DeepSeek Harness）

除了當技能用，本倉庫本身就是一個 DSH 外掛套件：裝進去之後，代理多出一個 `epi_report` 工具，一句話就能出稿，不必記指令。

```bash
dsh plugin --profile web add github:naliehu/outbreak-report-writing
dsh --profile web          # 重新啟動後生效，直接說「用 epi_report 出一份初次報告」
```

工具參數：`action`（build／check）、`event_path`（事件 YAML/JSON，必填）、`stage`
（initial／progress／final／closure／case）、`line_list`（個案 CSV）、`out_dir`、`formats`、`docx_profile`。

外掛做的事很少，也很明確：找技能目錄 → 挑 Python 解譯器 → 傳參數 → 回收產物路徑。
報告怎麼寫、畫什麼圖、缺漏怎麼分級，全部在 `scripts/` 裡，改一次兩邊同時生效。

相依套件按需降級：

| 已安裝 | 能產出 |
|---|---|
| python3 + pyyaml + jinja2 | Markdown 本文（圖與 Word 自動省略，並註明原因） |
| 再加上 matplotlib | 加四張敘事圖與三張分布圖 |
| 再加上 python-docx | 加 Word；PDF 一律出（無 LibreOffice 時走 PyMuPDF 兜底） |

一次裝齊：`python3 -m pip install pyyaml jinja2 matplotlib python-docx`

設定（寫在 profile 的 `cordis.patch.yml` 裡，可全部省略）：

```yaml
- insert:
    - id: epi-report
      name: 'outbreak-report-writing'
      config:
        skillDir: ~/path/to/outbreak-report-writing   # 預設自動尋找
        python: /usr/bin/python3                      # 預設優先使用 vendor/venv/bin/python
        outDir: ~/流调输出                             # 預設 <事件檔案同層>/流调输出
```

## 目錄

```
SKILL.md                  技能主體（判準、流程、文風要點、常見陷阱）
references/               深入材料
  01 報告類型與骨架 → report-types.md（六體裁逐節寫法）
  02 分病种要点.md        12 個病種的著墨重點與易混邊界
  03 可视化作图规范.md     決策表 + 七條硬規範 + 圖註
  06 文风与句式库.md       477 份報告的量化文風、七種功能句定式、數字六條、禁用清單
  intake-playbook.md      現場怎麼問、問不到怎麼辦
  toolchain.md            模組契約、中文出圖、疑難排解
templates/                五套 .j2 體裁範本 + disease_profiles.yaml（可自行新增病種）
scripts/                  epi_core / epi_viz / build_report / md2docx / flowreport
plugin/                   Hermes 外掛原始碼（封裝成 epi_report 工具）
tests/                    單元測試
```

## 推廣

1. **整包複製**：把 `outbreak-report-writing/` 整個目錄（含 `vendor/venv`，約 150 MB）給同事，`python3 scripts/build_report.py` 就能跑，不必連網、不必 pip。
2. **只要範本**：把 `templates/*.j2` + `references/06-文风与句式库.md` 複製走，手動填寫也是一份合規報告——技能的價值有一半在這個文件裡。
3. **裝成外掛**：把 `plugin/` 複製到 `~/.hermes/plugins/epi-report/`，Hermes 裡就有 `epi_report` 工具，一句話生成。
4. **新增病種**：只改 `templates/disease_profiles.yaml`，不動程式碼。

## 已知限制

- 沒有合法的行政區底圖，地理分布只能做場所卡片／經緯度氣泡示意圖，不能當 GIS 主題圖對外。
- 傷寒、登革熱、發熱伴血小板減少症候群、食源性、屈公病的潛伏期取自指引，YAML 裡標了 `verify: true`，使用前請查當期方案。
- 世代由發病時間推算（0.6× 常見潛伏期閾值），不是拓撲推導；有確切接觸關係時以傳播鏈為準。
- Word 版型的字型（仿宋_GB2312）需系統已安裝，否則退回到宋體，不會報錯。
