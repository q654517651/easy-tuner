# install-embed-uv-final.ps1
# Fully portable embedded Python + uv installer (Windows)
# - Installs Python embeddable locally
# - Patches python311._pth to enable site-packages
# - Bootstraps pip only to install uv into embedded env
# - Then uses embedded uv (Scripts\uv.exe) for all package installs

param(
    [switch]$UseChinaMirror,  # 是否使用国内镜像源
    [switch]$Help             # 显示帮助信息
)

if ($Help) {
    Write-Host "用法: setup_portable_uv.ps1 [-UseChinaMirror] [-Help]"
    Write-Host ""
    Write-Host "参数说明:"
    Write-Host "  -UseChinaMirror  : 使用国内镜像源 (清华大学源)"
    Write-Host "  -Help            : 显示此帮助信息"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\setup_portable_uv.ps1                # 使用默认国际源"
    Write-Host "  .\setup_portable_uv.ps1 -UseChinaMirror # 使用国内源"
    exit 0
}

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# =================== Config ===================
$PythonVersion = "3.11.9"
$EmbedZipUrl   = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$GetPipUrl     = "https://bootstrap.pypa.io/get-pip.py"

# 目标安装路径选择策略：
# 1) 如果已存在 runtime\python\python.exe -> 用 runtime\python
# 2) 否则若存在 runtime 目录 -> 也安装到 runtime\python
# 3) 否则使用 .\python
$RuntimeDirCand = Join-Path (Get-Location) "runtime"
$PyDir =
    if (Test-Path (Join-Path $RuntimeDirCand "python\python.exe")) { Join-Path $RuntimeDirCand "python" }
    elseif (Test-Path $RuntimeDirCand)                              { Join-Path $RuntimeDirCand "python" }
    else                                                            { Join-Path (Get-Location) "python" }

$PyExe      = Join-Path $PyDir "python.exe"
$PthFile    = Join-Path $PyDir  "python311._pth"
$ScriptsDir = Join-Path $PyDir  "Scripts"
$EmbedZip   = Join-Path (Get-Location) "python-embed.zip"
$GetPipPath = Join-Path (Get-Location) "get-pip.py"
$UvExe      = Join-Path $ScriptsDir "uv.exe"

# requirements 文件优先级
$ReqFiles = @("requirements-uv-windows-new.txt", "requirements-uv-windows.txt")

# =================== Environment ===================
$Env:HF_HOME = "huggingface"
$Env:PIP_DISABLE_PIP_VERSION_CHECK = 1
$Env:PIP_NO_CACHE_DIR = 1

# 根据参数决定是否使用国内镜像源
if ($UseChinaMirror) {
    Info "使用国内镜像源 (清华大学源)"
    $Env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple/"
} else {
    Info "使用默认国际源"
    # 不设置 PIP_INDEX_URL，使用默认的 pypi.org
}

# PyTorch CUDA 轮子额外源（保留）
$Env:PIP_EXTRA_INDEX_URL = "https://download.pytorch.org/whl/cu128"

# uv 行为（即便 uv 在嵌入式中，这些 env 仍然适用）
$Env:UV_EXTRA_INDEX_URL = "https://download.pytorch.org/whl/cu128"
$Env:UV_CACHE_DIR = "${env:LOCALAPPDATA}/uv/cache"
$Env:UV_NO_BUILD_ISOLATION = 1
$Env:UV_NO_CACHE = 0
$Env:UV_LINK_MODE = "symlink"

$Env:GIT_LFS_SKIP_SMUDGE = 1
$Env:CUDA_HOME = "${env:CUDA_PATH}"
$Env:HF_HUB_ENABLE_HF_TRANSFER = 0

# =================== Helpers ===================
function Info($m){ Write-Host "▶ $m" }
function Ok($m){ Write-Host "✅ $m" }
function Fail($m){ Write-Host "❌ $m"; exit 1 }

function Invoke-WebRequestRetry {
    param([string]$Uri,[string]$OutFile,[int]$Retries=3,[int]$DelaySec=2)
    for ($i=1; $i -le $Retries; $i++) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $OutFile -TimeoutSec 180
            if (Test-Path $OutFile -PathType Leaf) { return }
        } catch {
            if ($i -eq $Retries) { throw }
            Start-Sleep -Seconds $DelaySec
        }
    }
}

function Ensure-Dir($p){ if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null } }

# =================== 1) Ensure embedded Python ===================
if (-not (Test-Path $PyExe)) {
    Info "Downloading Python $PythonVersion embeddable to $PyDir ..."
    Invoke-WebRequestRetry -Uri $EmbedZipUrl -OutFile $EmbedZip
    Ensure-Dir $PyDir
    Expand-Archive -Path $EmbedZip -DestinationPath $PyDir -Force
    Remove-Item $EmbedZip -Force
    Ok "Embedded Python extracted: $PyExe"
} else {
    Info "Embedded Python found: $PyExe"
}

# =================== 2) Patch python311._pth ===================
if (-not (Test-Path $PthFile)) {
@"
python311.zip
.
Lib\site-packages
import site
"@ | Set-Content -Path $PthFile -Encoding UTF8
    Ok "Created python311._pth (site-packages enabled)"
} else {
    $pth = Get-Content $PthFile -Raw
    $changed = $false
    if ($pth -notmatch "(?m)^\.$")                 { Add-Content -Path $PthFile -Value "."; $changed=$true }
    if ($pth -notmatch "(?m)^Lib\\site-packages$") { Add-Content -Path $PthFile -Value "Lib\site-packages"; $changed=$true }
    if ($pth -notmatch "(?m)^import site$")        { Add-Content -Path $PthFile -Value "import site"; $changed=$true }
    if ($changed) { Ok "Patched python311._pth" } else { Info "python311._pth already OK" }
}

# 确保 Scripts 目录存在 + 将本会话 PATH 指向嵌入式
Ensure-Dir $ScriptsDir
$Env:Path = "$ScriptsDir;$PyDir;$Env:Path"
# 告诉 uv 一律用嵌入式 Python
$Env:UV_PYTHON = $PyExe

# =================== 3) Ensure embedded uv (no pip needed) ===================
# 直接把 uv 的 Windows 二进制放到嵌入式 Scripts 目录，完全不依赖 pip

Ensure-Dir $ScriptsDir  # 已有同名函数

# 预期 uv 可执行路径
$UvExe = Join-Path $ScriptsDir "uv.exe"

if (-not (Test-Path $UvExe)) {
    $UvZipUrl = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
    $UvZip    = Join-Path $env:TEMP "uv-windows.zip"

    Info "Downloading uv binary to embedded Scripts ..."
    Invoke-WebRequestRetry -Uri $UvZipUrl -OutFile $UvZip
    Expand-Archive -Force -Path $UvZip -DestinationPath $ScriptsDir
    Remove-Item $UvZip -Force
}

# 某些环境可能解压出 uv.exe/uv（无扩展名），做一次兜底
if (-not (Test-Path $UvExe)) {
    $UvAlt = Join-Path $ScriptsDir "uv"
    if (Test-Path $UvAlt) { $UvExe = $UvAlt }
}

# 校验 uv 是否可用
& $UvExe --version | Out-Null
Ok "uv ready: $UvExe"


# =================== 5) Use embedded uv to install packages ===================
Info "Installing base packages via embedded uv ..."
& $UvExe pip install --python "$PyExe" -U hatchling editables torch==2.8.0
if ($LASTEXITCODE -ne 0) { Fail "uv install base packages failed" }

# 依次尝试 requirements 文件
$ReqUsed = $null
foreach ($rf in $ReqFiles) {
    if (Test-Path (Join-Path (Get-Location) $rf)) { $ReqUsed = $rf; break }
}
if ($ReqUsed) {
    Info "Syncing requirements via embedded uv: $ReqUsed"
    & $UvExe pip install --python "$PyExe" --upgrade --link-mode=copy --index-strategy unsafe-best-match -r $ReqUsed
    if ($LASTEXITCODE -ne 0) { Fail "uv install $ReqUsed failed" }
} else {
    Info "No requirements file found (looked for: $($ReqFiles -join ', ')). Skip."
}

# =================== 6) Show versions & done ===================
& $PyExe --version
# （无需验证 pip）
Ok "🎉 Done. All packages installed into embedded env: $PyDir"

Write-Host ""
Write-Host "👉 运行示例："
Write-Host "   `"$($PyExe)`" -m your_module"
Write-Host "   `"$($PyExe)`" your_script.py"
Write-Host "（后续安装/同步依赖请使用嵌入式 uv：`"$($UvExe)`" ...）"
try { $null = Read-Host "完成。按 Enter 关闭窗口..." } catch {}
