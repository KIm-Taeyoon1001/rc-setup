import asyncio, json, time, base64, threading, socket, os, platform
import numpy as np
import mss as mss_lib
import cv2, requests, websockets
from pynput.mouse import Controller as MouseCtrl, Button, Listener as MouseListener
from pynput.keyboard import Controller as KeyCtrl, Key, Listener as KeyListener

OS = platform.system()

if OS == "Windows":
    DEVICE_NAME = os.environ.get("COMPUTERNAME", socket.gethostname())
else:
    DEVICE_NAME = socket.gethostname().replace(".local", "")

RELAY_URL = "wss://rc-setup-production.up.railway.app"
FPS = 12
JPEG_QUALITY = 45
SCALE = 0.6
FIREBASE_URL = "https://remote-ctrl-c3035-default-rtdb.firebaseio.com"

mouse_ctrl = MouseCtrl()
kbd_ctrl = KeyCtrl()
remote_active = False
kb_listener = None
ms_listener = None

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

def _suppress_key(key):
    return False if remote_active else None

def _suppress_mouse(*a):
    return False if remote_active else None

def start_blockers():
    global kb_listener, ms_listener
    try:
        kb_listener = KeyListener(suppress=False)
        ms_listener = MouseListener(suppress=False)
        kb_listener.start()
        ms_listener.start()
    except Exception as e:
        print(f"[agent] blocker start failed: {e}")

def set_control(active):
    global remote_active
    remote_active = active
    print(f"[agent] control = {active}")

def self_uninstall():
    import sys, shutil, subprocess
    print("[agent] uninstalling...")
    dir_path = os.path.dirname(os.path.abspath(__file__))
    if OS == "Windows":
        startup = os.path.join(os.environ.get("APPDATA",""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "RC_Agent.bat")
        try: os.remove(startup)
        except: pass
        subprocess.Popen(f'cmd /c timeout /t 2 && rmdir /s /q "{dir_path}"', shell=True)
    elif OS == "Darwin":
        plist = os.path.expanduser("~/Library/LaunchAgents/com.rc.agent.plist")
        subprocess.run(["launchctl", "unload", plist], capture_output=True)
        try: os.remove(plist)
        except: pass
        subprocess.Popen(f"sleep 2 && rm -rf '{dir_path}'", shell=True)
    fb_del(f"devices/{DEVICE_NAME}")
    sys.exit(0)

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
            try:
                img = np.array(sct.grab(mon))
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                img = cv2.resize(img, (0, 0), fx=SCALE, fy=SCALE)
                ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok:
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
            print(f"[agent] connecting... ({OS})")
            async with websockets.connect(
                RELAY_URL,
                ping_interval=None,
                close_timeout=5,
                max_size=None
            ) as ws:
                await ws.send(json.dumps({"role": "host", "id": DEVICE_NAME}))
                print(f"[agent] connected: {DEVICE_NAME}")

                existing = None
                try:
                    r = requests.get(f"{FIREBASE_URL}/devices/{DEVICE_NAME}/name.json", timeout=3)
                    existing = r.json()
                except:
                    pass
                fb_set(f"devices/{DEVICE_NAME}", {
                    "status": "online",
                    "name": existing if existing else DEVICE_NAME,
                    "os": OS,
                    "relay": RELAY_URL,
                    "ts": time.time()
                })

                stream_task = asyncio.create_task(stream_screen(ws))
                try:
                    async for msg in ws:
                        try:
                            ev = json.loads(msg)
                            if ev.get("t") == "toggle":
                                set_control(ev["active"])
                            elif ev.get("t") == "uninstall":
                                threading.Thread(target=self_uninstall, daemon=True).start()
                            else:
                                exec_input(ev, sw, sh)
                        except:
                            pass
                finally:
                    stream_task.cancel()
                    set_control(False)
        except Exception as e:
            print(f"[agent] error: {e}")
            set_control(False)

        fb_set(f"devices/{DEVICE_NAME}/status", "offline")
        print("[agent] reconnecting in 3s...")
        await asyncio.sleep(3)

if __name__ == "__main__":
    print(f"[agent] OS: {OS}, Device: {DEVICE_NAME}")
    try:
        asyncio.run(connect_relay())
    except KeyboardInterrupt:
        set_control(False)
        fb_del(f"devices/{DEVICE_NAME}")
        print("[agent] stopped")
