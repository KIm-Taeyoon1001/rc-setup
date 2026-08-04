import asyncio, json, time, base64, threading, socket, os
import numpy as np
import mss as mss_lib
import cv2, requests, websockets
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key
from pynput import keyboard as pkb, mouse as pms

DEVICE_NAME = os.environ.get("COMPUTERNAME", socket.gethostname())
RELAY_URL = "wss://rc-setup-production.up.railway.app"
FPS = 12
JPEG_QUALITY = 45
SCALE = 0.6
FIREBASE_URL = "https://remote-ctrl-c3035-default-rtdb.firebaseio.com"

mouse_ctrl = MouseCtrl()
kbd_ctrl = KeyCtrl()
remote_active = False
blocker = None

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

class InputBlocker:
    def __init__(self):
        self._kb = pkb.Listener(suppress=True)
        self._ms = pms.Listener(suppress=True)
        self._kb.start()
        self._ms.start()
    def stop(self):
        try: self._kb.stop()
        except: pass
        try: self._ms.stop()
        except: pass

def set_control(active):
    global remote_active, blocker
    remote_active = active
    if active and blocker is None:
        try:
            blocker = InputBlocker()
            print("[agent] LOCAL INPUT BLOCKED")
        except Exception as e:
            print(f"[agent] block failed: {e}")
    elif not active and blocker:
        blocker.stop()
        blocker = None
        print("[agent] LOCAL INPUT UNBLOCKED")

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
            if ev["down"]:
                mouse_ctrl.press(btn)
            else:
                mouse_ctrl.release(btn)
        elif t == "scroll":
            mouse_ctrl.scroll(0, ev["dy"])
        elif t == "key":
            k = ev["key"]
            try:
                key_obj = getattr(Key, k) if len(k) > 1 else k
            except AttributeError:
                key_obj = k
            if ev["down"]:
                kbd_ctrl.press(key_obj)
            else:
                kbd_ctrl.release(key_obj)
    except Exception as e:
        print(f"[input] error: {e}")

async def stream_screen(ws):
    interval = 1.0 / FPS
    with mss_lib.MSS() as sct:
        mon = sct.monitors[0]
        while True:
            t0 = time.time()
            img = np.array(sct.grab(mon))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            img = cv2.resize(img, (0, 0), fx=SCALE, fy=SCALE)
            ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                try:
                    await ws.send(json.dumps({
                        "t": "frame",
                        "d": base64.b64encode(enc.tobytes()).decode()
                    }))
                except:
                    break
            await asyncio.sleep(max(0, interval - (time.time() - t0)))

async def connect_relay():
    with mss_lib.MSS() as sct:
        mon = sct.monitors[0]
        sw, sh = mon["width"], mon["height"]

    while True:
        try:
            print("[agent] connecting...")
            async with websockets.connect(RELAY_URL, ping_interval=15, ping_timeout=10, close_timeout=5) as ws:
                await ws.send(json.dumps({"role": "host", "id": DEVICE_NAME}))
                print(f"[agent] connected: {DEVICE_NAME}")
                fb_set(f"devices/{DEVICE_NAME}", {
                    "status": "online",
                    "relay": RELAY_URL,
                    "ts": time.time()
                })
                stream_task = asyncio.create_task(stream_screen(ws))
                try:
                    async for msg in ws:
                        try:
                            ev = json.loads(msg)
                            if ev.get("t") == "toggle":
                                threading.Thread(target=set_control, args=(ev["active"],), daemon=True).start()
                            else:
                                exec_input(ev, sw, sh)
                        except:
                            pass
                finally:
                    stream_task.cancel()
                    threading.Thread(target=set_control, args=(False,), daemon=True).start()
        except Exception as e:
            print(f"[agent] error: {e}")
            threading.Thread(target=set_control, args=(False,), daemon=True).start()

        fb_set(f"devices/{DEVICE_NAME}/status", "offline")
        print("[agent] reconnecting in 3s...")
        await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(connect_relay())
    except KeyboardInterrupt:
        set_control(False)
        fb_del(f"devices/{DEVICE_NAME}")
        print("[agent] stopped")
