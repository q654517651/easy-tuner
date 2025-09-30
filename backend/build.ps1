Set-Location $PSScriptRoot

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }
if (Test-Path EasyTunerBackend.spec) { Remove-Item EasyTunerBackend.spec -Force }

$py = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"

& $py -m PyInstaller `
  --noconfirm --clean `
  --name EasyTunerBackend `
  --onefile --console `
  --paths . `
  --collect-submodules app `
  --collect-submodules google.protobuf `
  --hidden-import google.protobuf.internal `
  serve.py

Write-Host "`n打包完成：$(Join-Path (Get-Location) 'dist/EasyTunerBackend.exe')"
