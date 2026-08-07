#!/bin/bash
set -e

DIR="$HOME/Library/Application Support/RemoteControl"
AGENT_URL="https://raw.githubusercontent.com/KIm-Taeyoon1001/rc-setup/main/agent.py"
PLIST="$HOME/Library/LaunchAgents/com.rc.agent.plist"

mkdir -p "$DIR"

# Python3 확인
if ! command -v python3 &> /dev/null; then
    echo "Python3 없음. https://python.org 에서 설치 후 다시 실행하세요."
    exit 1
fi

# 패키지 설치
python3 -m pip install websockets mss pynput opencv-python numpy requests --quiet --user

# agent.py 다운로드
curl -s "$AGENT_URL" -o "$DIR/agent.py"

# LaunchAgent 등록 (로그인 시 자동 시작)
cat > "$PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rc.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which python3)</string>
        <string>$DIR/agent.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/rc_agent.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/rc_agent_err.log</string>
</dict>
</plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "설치 완료: $(hostname)"
