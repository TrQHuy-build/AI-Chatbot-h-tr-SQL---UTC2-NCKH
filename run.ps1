# ============================================================
# run.ps1 - Script tự động setup và chạy toàn bộ dự án
# SQL Chatbot AI - Phi-3 Fine-tuning
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   SQL Chatbot AI - Khởi động dự án    " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---- 1. Kiểm tra Python ----
Write-Host "`n[1/6] Kiểm tra Python..." -ForegroundColor Yellow
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $pythonCmd = $cmd
            Write-Host "  ✅ Tìm thấy $ver" -ForegroundColor Green
            break
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Host "  ❌ Không tìm thấy Python 3. Vui lòng cài đặt Python 3.10+" -ForegroundColor Red
    exit 1
}

# ---- 2. Tạo và kích hoạt virtual environment ----
Write-Host "`n[2/6] Thiết lập Virtual Environment..." -ForegroundColor Yellow
$venvPath = ".\.venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "  Đang tạo venv..." -ForegroundColor Gray
    & $pythonCmd -m venv $venvPath
}
$pipCmd  = "$venvPath\Scripts\pip.exe"
$pyCmd   = "$venvPath\Scripts\python.exe"
Write-Host "  ✅ Virtual environment sẵn sàng" -ForegroundColor Green

# ---- 3. Cài đặt Python dependencies ----
Write-Host "`n[3/6] Cài đặt Python dependencies..." -ForegroundColor Yellow
& $pipCmd install --upgrade pip -q
& $pipCmd install -r deployment_package\requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Lỗi cài đặt Python packages" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Python dependencies đã được cài đặt" -ForegroundColor Green

# ---- 4. Chuẩn bị dữ liệu ----
Write-Host "`n[4/6] Chuẩn bị dữ liệu..." -ForegroundColor Yellow
& $pyCmd datasets\data_preprocessing.py
Write-Host "  ✅ Dữ liệu đã được chuẩn bị" -ForegroundColor Green

# ---- 5. Kiểm tra các module ----
Write-Host "`n[5/6] Kiểm tra các module..." -ForegroundColor Yellow

Write-Host "  Kiểm tra SQL Execution module..." -ForegroundColor Gray
& $pyCmd deployment_package\sql_execution.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ SQL Execution module OK" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  SQL Execution module có lỗi" -ForegroundColor Yellow
}

Write-Host "  Kiểm tra RAG Integration module..." -ForegroundColor Gray
& $pyCmd deployment_package\rag_integration.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ RAG Integration module OK" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  RAG Integration module có lỗi" -ForegroundColor Yellow
}

# ---- 6. Khởi động Backend API ----
Write-Host "`n[6/6] Khởi động Backend API..." -ForegroundColor Yellow
Write-Host "  Backend chạy tại: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Docs API tại:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Nhấn Ctrl+C để dừng`n" -ForegroundColor Gray

Set-Location deployment_package
& $pyCmd -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
