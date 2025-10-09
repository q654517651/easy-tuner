#Requires -Version 5.1
<#
.SYNOPSIS
  setup_portable_uv.ps1（整合稳健版）
#>

# ---- 参数必须在最前面（仅可在注释/#requires之后）----
param(
  # 运行时根目录（默认脚本上级目录）
  [string]$RuntimeDir = (Resolve-Path -LiteralPath $PSScriptRoot).Path,
  # 使用国内镜像（带默认值，避免 StrictMode 下未绑定时报错）
  [switch]$UseChinaMirror = $false
)

# ---- 严格与失败即停 ----
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---- TLS/编码预处理 ----
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
try {
  [Console]::InputEncoding  = New-Object System.Text.UTF8Encoding($false)
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
} catch {}

# ---- PS7 开启 ANSI；PS5 静默降级 ----
$IsPS7 = $PSVersionTable.PSVersion.Major -ge 7
if ($IsPS7) { try { $PSStyle.OutputRendering = 'Ansi' } catch {} }

function _Color($text, $ansi) { if ($IsPS7) { return "$ansi$text`e[0m" } else { return $text } }
$C_INFO    = { param($t) _Color $t "`e[36;1m" }
$C_WARN    = { param($t) _Color $t "`e[33;1m" }
$C_ERROR   = { param($t) _Color $t "`e[31;1m" }
$C_SUCCESS = { param($t) _Color $t "`e[32;1m" }
$C_DIM     = { param($t) _Color $t "`e[90m"   }

function Timestamp { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
function Info    { param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Message)  Write-Host "$((Timestamp))  $(& $C_INFO 'INFO')     $($Message -join ' ')" }
function Warn    { param([string]$Message)                                                 Write-Host "$((Timestamp))  $(& $C_WARN 'WARN')     $Message" }
function Write-LogError { param([string]$Message)                                          Write-Host "$((Timestamp))  $(& $C_ERROR 'ERROR')    $Message" }
function Success { param([string]$Message)                                                 Write-Host "$((Timestamp))  $(& $C_SUCCESS 'OK')       $Message" }

# ---- 小工具 ----
function Invoke-WebRequestRetry {
  param([string]$Uri,[string]$OutFile,[int]$Retries=3,[int]$DelaySec=2,[int]$TimeoutSec=180)
  for ($i=1; $i -le $Retries; $i++) {
    try {
      Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $OutFile -TimeoutSec $TimeoutSec
      if (Test-Path $OutFile -PathType Leaf) { return }
    } catch {
      if ($i -eq $Retries) { throw }
      Start-Sleep -Seconds $DelaySec
    }
  }
}

function New-DirectoryIfMissing {
  param([Parameter(Mandatory=$true)][string]$Path)
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

# ---- 常量/路径 ----
$PythonVersion = "3.11.9"
$EmbedZipUrl   = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$UvZipUrl      = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"

$BaseDir    = (Resolve-Path $RuntimeDir).Path
$PyDir      = Join-Path $BaseDir "python"
$ScriptsDir = Join-Path $PyDir   "Scripts"
$PyExe      = Join-Path $PyDir   "python.exe"
$PthFile    = Join-Path $PyDir   "python311._pth"
$UvExe      = Join-Path $ScriptsDir "uv.exe"

$TmpDir     = Join-Path $env:TEMP "easy-tuner-installer"
New-DirectoryIfMissing $TmpDir
$EmbedZip   = Join-Path $TmpDir "python-embed.zip"
$UvZip      = Join-Path $TmpDir "uv-windows.zip"

# ---- 环境变量（当前会话）----
$Env:PIP_DISABLE_PIP_VERSION_CHECK = 1
$Env:PIP_NO_CACHE_DIR = 1
$Env:UV_NO_BUILD_ISOLATION = 1
$Env:UV_NO_CACHE = 0
$Env:HF_HUB_ENABLE_HF_TRANSFER = 0

# ---- UV 缓存与链接模式（强烈建议）----
$Env:UV_CACHE_DIR = Join-Path $RuntimeDir "cache\uv"
$Env:UV_LINK_MODE = "copy"
New-DirectoryIfMissing $Env:UV_CACHE_DIR


if ($UseChinaMirror) {
  Info "使用国内镜像（清华 TUNA）"
  $Env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple/"
  $Env:UV_INDEX_URL  = $Env:PIP_INDEX_URL
} else {
  Info "使用默认国际源"
  Remove-Item Env:\PIP_INDEX_URL -ErrorAction SilentlyContinue | Out-Null
  Remove-Item Env:\UV_INDEX_URL  -ErrorAction SilentlyContinue | Out-Null
}

# 可选：PyTorch CUDA 额外源
$Env:PIP_EXTRA_INDEX_URL = "https://download.pytorch.org/whl/cu128"
$Env:UV_EXTRA_INDEX_URL  = $Env:PIP_EXTRA_INDEX_URL

Info "脚本编码: UTF-8，PowerShell: $($PSVersionTable.PSVersion)"
Info "RuntimeDir: $BaseDir"

try {
  # 1) 准备目录
  New-DirectoryIfMissing $BaseDir
  New-DirectoryIfMissing $PyDir
  New-DirectoryIfMissing $ScriptsDir

  # 2) 获取/解压嵌入式 Python
  if (-not (Test-Path $PyExe)) {
    Info "下载嵌入式 Python $PythonVersion ..."
    Invoke-WebRequestRetry -Uri $EmbedZipUrl -OutFile $EmbedZip
    Info "解压到 $PyDir ..."
    Expand-Archive -Path $EmbedZip -DestinationPath $PyDir -Force
  } else {
    Info "发现已存在的嵌入式 Python: $PyExe"
  }

  # 3) 补丁 python311._pth 以启用 site-packages
  if (-not (Test-Path $PthFile)) {
@"
python311.zip
.
Lib\site-packages
import site
"@ | Set-Content -Path $PthFile -Encoding UTF8
    Success "已创建 python311._pth（启用 site-packages）"
  } else {
    $pth = Get-Content $PthFile -Raw
    $changed = $false
    if ($pth -notmatch "(?m)^\.$")                 { Add-Content -Path $PthFile -Value "."; $changed=$true }
    if ($pth -notmatch "(?m)^Lib\\site-packages$") { Add-Content -Path $PthFile -Value "Lib\site-packages"; $changed=$true }
    if ($pth -notmatch "(?m)^import site$")        { Add-Content -Path $PthFile -Value "import site"; $changed=$true }
    if ($changed) { Success "已修补 python311._pth" } else { Info "python311._pth 已正确" }
  }

  # 4) 调整 PATH（仅当前会话）与 UV 绑定的 Python
  $Env:Path = "$ScriptsDir;$PyDir;$Env:Path"
  $Env:UV_PYTHON = $PyExe

  # 5) 下载 uv 二进制至嵌入式 Scripts
  if (-not (Test-Path $UvExe)) {
    Info "下载 uv 二进制 ..."
    Invoke-WebRequestRetry -Uri $UvZipUrl -OutFile $UvZip
    Expand-Archive -Path $UvZip -DestinationPath $ScriptsDir -Force

    if (-not (Test-Path $UvExe)) {
      $UvAlt = Join-Path $ScriptsDir "uv"
      if (Test-Path $UvAlt) { Rename-Item -Path $UvAlt -NewName "uv.exe" -Force }
    }
  }
  & $UvExe --version | Out-Null
  Success "uv 就绪: $UvExe"

  # 7) 安装流程（使用魔改的 pyproject.toml + requirements-uv-windows.txt）
  $ReqFile = Join-Path $RuntimeDir "requirements-uv-windows.txt"

  if (-not (Test-Path $ReqFile -PathType Leaf)) {
    throw "未找到 $ReqFile（请确保 runtime/requirements-uv-windows.txt 存在）"
  }

  Info "使用 requirements 文件：$ReqFile"

  # 7.1 直接使用 uv pip install（-e . 会先安装魔改的 pyproject.toml，然后 requirements 覆盖具体版本）
  Push-Location $RuntimeDir
  Info "安装依赖（基于魔改的 pyproject.toml + requirements-uv-windows.txt）..."
  & $UvExe pip install --python "$PyExe" --link-mode=copy --index-strategy unsafe-best-match -r "requirements-uv-windows.txt"
  $code = $LASTEXITCODE
  Pop-Location

  if ($code -ne 0) { throw "uv pip install 失败 (exit=$code)" }


  # 8) 版本确认
  & $PyExe --version
  Success "🎉 完成：嵌入式 Python 目录 $PyDir（使用 cu128；以 overrides/req 为准；不重复下载）"


  exit 0
}
catch {
  Write-LogError "安装脚本执行失败：$($_.Exception.Message)"
  if ($_.ScriptStackTrace) { Write-Host $(& $C_DIM "Stack: $($_.ScriptStackTrace)") }
  exit 1
}
