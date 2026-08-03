import socket, struct, threading
import mss, cv2, numpy as np
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key

HOST = "0.0.0.0"
PORT = 9999
JPEG_QUALITY = 40   # 낮출수록 빠름/화질저하
SCALE = 0.6         # 화면 축소 비율 (전송량 감소)

mouse = MouseCtrl()
keyboard = KeyCtrl()

def send_msg(conn, data):
    conn.sendall(struct.pack(">I", len(data)) + data)

def recv_all(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def recv_msg(conn):
    raw = recv_all(conn, 4)
    if not raw:
        return None
    length = struct.unpack(">I", raw)[0]
    return recv_all(conn, length)

# 입력 재현 스레드
def input_handler(conn, sw, sh):
    import json
    while True:
        data = recv_msg(conn)
        if data is None:
            break
        try:
            ev = json.loads(data.decode())
        except:
            continue
        t = ev.get("t")
        if t == "move":
            mouse.position = (int(ev["x"] * sw), int(ev["y"] * sh))
        elif t == "click":
            mouse.position = (int(ev["x"] * sw), int(ev["y"] * sh))
            btn = Button.left if ev["btn"] == "l" else Button.right
            if ev["down"]:
                mouse.press(btn)
            else:
                mouse.release(btn)
        elif t == "scroll":
            mouse.scroll(0, ev["dy"])
        elif t == "key":
            k = ev["key"]
            try:
                key_obj = getattr(Key, k) if len(k) > 1 else k
            except AttributeError:
                key_obj = k
            if ev["down"]:
                keyboard.press(key_obj)
            else:
                keyboard.release(key_obj)

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    print(f"[server] 대기중 :{PORT}")

    while True:
        conn, addr = srv.accept()
        print(f"[server] 접속: {addr}")
        try:
            with mss.mss() as sct:
                mon = sct.monitors[1]
                sw, sh = mon["width"], mon["height"]
                # 화면 실제 해상도를 클라에 알림
                send_msg(conn, struct.pack(">II", sw, sh))
                # 입력 수신 스레드 시작
                threading.Thread(target=input_handler, args=(conn, sw, sh), daemon=True).start()

                while True:
                    img = np.array(sct.grab(mon))
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    img = cv2.resize(img, (0, 0), fx=SCALE, fy=SCALE)
                    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                    if ok:
                        send_msg(conn, enc.tobytes())
        except (ConnectionResetError, BrokenPipeError):
            print("[server] 연결 끊김")
        except Exception as e:
            print("[server] 오류:", e)
        finally:
            conn.close()

if __name__ == "__main__":
    main()