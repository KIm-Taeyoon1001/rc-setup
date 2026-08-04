import asyncio, json, os
import websockets

host_connections = {}
viewer_connections = {}

async def handler(ws):
    device_id = None
    role = None
    try:
        msg = await ws.recv()
        data = json.loads(msg)
        device_id = data["id"]
        role = data["role"]

        if role == "host":
            host_connections[device_id] = ws
            print(f"[relay] HOST online: {device_id}", flush=True)
            async for frame in ws:
                v = viewer_connections.get(device_id)
                if v:
                    try:
                        await v.send(frame)
                    except:
                        viewer_connections.pop(device_id, None)

        elif role == "viewer":
            viewer_connections[device_id] = ws
            print(f"[relay] VIEWER joined: {device_id}", flush=True)
            host = host_connections.get(device_id)
            if not host:
                print(f"[relay] no host for {device_id}", flush=True)
                return
            async for msg in ws:
                print(f"[relay] viewer->host: {msg[:50]}", flush=True)
                try:
                    await host.send(msg)
                except Exception as e:
                    print(f"[relay] send to host failed: {e}", flush=True)
                    break

    except Exception as e:
        print(f"[relay] error: {e}", flush=True)
    finally:
        if role == "host" and device_id:
            host_connections.pop(device_id, None)
            print(f"[relay] HOST offline: {device_id}", flush=True)
        elif role == "viewer" and device_id:
            viewer_connections.pop(device_id, None)
            print(f"[relay] VIEWER left: {device_id}", flush=True)

async def main():
    port = int(os.environ.get("PORT", 8080))
    print(f"[relay] port {port}", flush=True)
    async with websockets.serve(handler, "0.0.0.0", port, max_size=10*1024*1024):
        await asyncio.Future()

asyncio.run(main())
