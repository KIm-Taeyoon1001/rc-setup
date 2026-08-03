import asyncio
import json
import time
import base64
import threading
import socket
import numpy as np
import mss as mss_lib
import cv2
import requests
import websockets
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key
from pynput import keyboard as pkb, mouse as pms

# ★ 기기마다 이 두 줄만 수정
DEVICE_NAME = "PC_1"
WS_PORT = 8889

# 설정
FPS = 15
JPEG_QUALITY = 60
SCALE = 0.75
FIREBASE_URL = "https://remote-ctrl-c3035-default-rtdb.firebaseio.com"

mouse_ctrl = MouseCtrl()
kbd_ctrl = KeyCtrl()
remote_active = False
blocker = None
connected = set()

# ── Firebase REST ──────────────────────────
def fb_set(path, data):
    try:
        requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=5)
    except:
        pass

def fb_del(path):
    try:
        requests.delete(f"{FIREBASE_URL}/{path}.json", timeout=5)
    except:
        pass

# ── 로컬 IP ────────────────────────────────
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ── 입력 실행 ──────────────────────────────
def exec_input(ev, sw, sh):
    if not remote_active:
        return
    t = ev.get("t")
    try:
        if t == "move":
            mouse_ctrl.position = (int(ev["x"] * sw), int(ev["y"] * sh))
        elif t == "click":
            mouse_ctrl.position = (int(ev["x"] * sw), int(ev["y"] * sh))
            btn = Button.left if ev["btn"] == "l" else Button.right
            (mouse_ctrl.press if ev["down"] else mouse_ctrl.release)(btn)
        elif t == "scroll":
            mouse_ctrl.scroll(0, ev["dy"])
        elif t == "key":
            k = ev["key"]
            try:
                key_obj = getattr(Key, k) if len(k) > 1 else k
            except AttributeError:
                key_obj = k
            (kbd_ctrl.press if ev["down"] else kbd_ctrl.release)(key_obj)
    except:
        pass

# ── 로컬 입력 차단 ─────────────────────────
class InputBlocker:
    def __init__(self):
        self._kb = pkb.Listener(
            suppress=True,
            on_press=lambda k: None,
            on_release=lambda k: None
        )
        self._ms = pms.Listener(
            suppress=True,
            on_click=lambda *a: None,
            on_move=lambda *a: None,
            on_scroll=lambda *a: None
        )
        self._kb.start()
        self._ms.start()

    def stop(self):
        self._kb.stop()
        self._ms.stop()

def set_control(active):
    global remote_active, blocker
    remote_active = active
    if active and blocker is None:
        try:
            blocker = InputBlocker()
            print("[agent] 로컬 입력 차단 ON")
        except Exception as e:
            print(f"[agent] 차단 실패 (관리자 권한 필요): {e}")
    elif not active and blocker:
        blocker.stop()
        blocker = None
        print("[agent] 로컬 입력 차단 OFF")

# ── 화면 캡처 스트리밍 ──────────────────────
async def stream_screen(ws, mon):
    interval = 1.0 / FPS
    with mss_lib.MSS() as sct:
        while True:
            t0 = time.time()
            img = np.array(sct.grab(mon))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            img = cv2.resize(img, (0, 0), fx=SCALE, fy=SCALE)
            ok, enc = cv2.imencode(
                ".jpg", img,
                [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            if ok:
                try:
                    await ws.send(json.dumps({
                        "t": "frame",
                        "d": base64.b64encode(enc.tobytes()).decode()
                    }))
                except:
                    break
            await asyncio.sleep(max(0, interval - (time.time() - t0)))

# ── WebSocket 핸들러 ───────────────────────
async def handler(ws):
    global connected
    connected.add(ws)
    print(f"[agent] viewer 접속: {ws.remote_address}")
    fb_set(f"devices/{DEVICE_NAME}/viewers", len(connected))

    with mss_lib.MSS() as sct:
        mon = sct.monitors[0]
        sw, sh = mon["width"], mon["height"]

    stream = asyncio.create_task(stream_screen(ws, mon))

    try:
        async for msg in ws:
            ev = json.loads(msg)
            if ev.get("t") == "toggle":
                threading.Thread(
                    target=set_control, args=(ev["active"],), daemon=True
                ).start()
            else:
                exec_input(ev, sw, sh)
    except:
        pass
    finally:
        stream.cancel()
        connected.discard(ws)
        if not connected:
            threading.Thread(target=set_control, args=(False,), daemon=True).start()
        fb_set(f"devices/{DEVICE_NAME}/viewers", len(connected))
        print(f"[agent] viewer 끊김")

# ── heartbeat ──────────────────────────────
async def heartbeat():
    while True:
        await asyncio.sleep(30)
        fb_set(f"devices/{DEVICE_NAME}/ts", time.time())

# ── 메인 ───────────────────────────────────
async def main():
    ip = get_ip()
    fb_set(f"devices/{DEVICE_NAME}", {
        "status": "online",
        "ip": ip,
        "port": WS_PORT,
        "ts": time.time(),
        "viewers": 0
    })
    print(f"[agent] {DEVICE_NAME} 등록 ({ip}:{WS_PORT})")

    async with websockets.serve(handler, "0.0.0.0", WS_PORT):
        print(f"[agent] 대기중... (같은 네트워크에서 연결 가능)")
        asyncio.create_task(heartbeat())
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        fb_del(f"devices/{DEVICE_NAME}")
        print("[agent] 종료")
