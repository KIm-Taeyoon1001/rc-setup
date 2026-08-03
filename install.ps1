$dir = "$env:APPDATA\RemoteControl"
$pyUrl = "https://raw.githubusercontent.com/너유저명/리포명/main/server.py"
$pyPath = "$dir\server.py"

# 폴더 생성
New-Item -ItemType Directory -Path $dir -Force | Out-Null

# Python 설치 여부 확인
$hasPy = $null -ne (Get-Command python -ErrorAction SilentlyContinue)

if (-not $hasPy) {
    $inst = "$env:TEMP\py_setup.exe"
    Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $inst
    Start-Process $inst -ArgumentList "/quiet PrependPath=1" -Wait
    # PATH 갱신
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 라이브러리 설치
python -m pip install mss pynput opencv-python numpy --quiet --user

# server.py 다운로드
Invoke-WebRequest $pyUrl -OutFile $pyPath

# 작업 스케줄러 등록 (로그인 시 자동 실행, 창 없이)
$action   = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "`"$pyPath`""
$trigger  = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "RC_Server" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

# 지금 바로 실행
Start-Process "pythonw.exe" -ArgumentList "`"$pyPath`"" -WindowStyle Hidden

Write-Host "설치 완료" -ForegroundColor Green