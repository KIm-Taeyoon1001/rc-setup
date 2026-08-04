import asyncio, json, time, base64, threading, socket, os
import numpy as np
import mss as mss_lib
import cv2, requests, websockets
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key

DEVICE_NAME = os.environ.get("COMPUTERNAME", socket.gethostname())
RELAY_URL = "wss://rc-setup-production.up.railway.app"
FPS = 15
JPEG_QUALITY = 60
SCALE = 0.75
FIREBASE_URL = "https://remote-ctrl-c3035-default-rtdb.firebaseio.com"

mouse_ctrl = MouseCtrl()
kbd_ctrl = KeyCtrl()

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

def exec_input(ev, sw, sh):
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
            print(f"[agent] connecting...")
            async with websockets.connect(RELAY_URL, ping_interval=20, ping_timeout=10) as ws:
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
                            if ev.get("t") != "toggle":
                                exec_input(ev, sw, sh)
                        except:
                            pass
                except:
                    pass
                finally:
                    stream_task.cancel()

        except Exception as e:
            print(f"[agent] error: {e}")

        fb_set(f"devices/{DEVICE_NAME}/status", "offline")
        print("[agent] reconnecting in 5s...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(connect_relay())
    except KeyboardInterrupt:
        fb_del(f"devices/{DEVICE_NAME}")
        print("[agent] stopped")
