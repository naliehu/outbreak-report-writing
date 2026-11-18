# 传染病流调报告撰写技能 —— Windows 环境安装脚本
# 用法（在本目录打开 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#
# 作用：用系统 Python 建 vendor\venv，装齐依赖，然后跑一次 doctor 自检。
# 说明：Windows 版发布包不含预编译的 vendor\venv，故本脚本负责现场生成。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

Write-Host "== 1/4 查找 Python ==" -ForegroundColor Cyan
$py = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) {
    throw "未找到 Python。请先安装 Python 3.10+（python.org 安装时勾选 'Add Python to PATH'），再重跑本脚本。"
}
$ver = & $py -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
$ok = & $py -c "import sys; print(1 if sys.version_info >= (3,10) else 0)"
if ($ok -ne "1") { throw "Python 版本为 $ver，需 3.10 及以上。" }
Write-Host "   Python $ver ($py)"

Write-Host "== 2/4 创建 vendor\venv ==" -ForegroundColor Cyan
if (Test-Path "vendor\venv\Scripts\python.exe") {
    Write-Host "   已存在，跳过创建"
} else {
    & $py -m venv vendor\venv
}
$vpy = Join-Path $root "vendor\venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) { throw "venv 创建失败：$vpy 不存在" }

Write-Host "== 3/4 安装依赖 ==" -ForegroundColor Cyan
& $vpy -m pip install --upgrade pip --quiet
& $vpy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败（检查网络或 pip 源）。" }

Write-Host "== 4/4 自检 ==" -ForegroundColor Cyan
& $vpy scripts\flowreport.py doctor
if ($LASTEXITCODE -ne 0) {
    Write-Host "自检有项目未通过；md/docx 仍可导出，PDF 需要先装 LibreOffice。" -ForegroundColor Yellow
} else {
    Write-Host "全部就绪。试跑：" -ForegroundColor Green
    Write-Host '  .\vendor\venv\Scripts\python.exe scripts\build_report.py --event 事件.yaml --stage initial --out .\输出 --formats md,docx,pdf'
}
