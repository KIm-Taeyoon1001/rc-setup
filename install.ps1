$dir = "$env:APPDATA\RemoteControl"
$agentUrl = "https://raw.githubusercontent.com/KIm-Taeyoon1001/rc-setup/main/agent.py"
$agentPath = "$dir\agent.py"

New-Item -ItemType Directory -Path $dir -Force | Out-Null

# Python 확인/설치
$hasPy = $null -ne (Get-Command python -ErrorAction SilentlyContinue)
if (-not $hasPy) {
    $inst = "$env:TEMP\py_setup.exe"
    Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $inst
    Start-Process $inst -ArgumentList "/quiet PrependPath=1" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 라이브러리 설치
python -m pip install websockets mss pynput opencv-python numpy requests --quiet --user

# agent.py 다운로드
Invoke-WebRequest $agentUrl -OutFile $agentPath

# 기기 이름 = 컴퓨터 이름 (자동, 10대 각각 달라짐)
$hostname = $env:COMPUTERNAME
(Get-Content $agentPath) -replace 'DEVICE_NAME = "PC_1"', "DEVICE_NAME = `"$hostname`"" | Set-Content $agentPath

# 기존 스케줄러 제거 후 재등록
schtasks /delete /tn "RC_Agent" /f 2>$null
$action   = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "`"$agentPath`""
$trigger  = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "RC_Agent" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

# 창 없이 즉시 실행
Start-Process "pythonw.exe" -ArgumentList "`"$agentPath`"" -WindowStyle Hidden

Write-Host "설치 완료: $hostname" -ForegroundColor Green
