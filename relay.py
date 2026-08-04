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
            print(f"[relay] host online: {device_id}")
            async for frame in ws:
                if device_id in viewer_connections:
                    try:
                        await viewer_connections[device_id].send(frame)
                    except:
                        viewer_connections.pop(device_id, None)

        elif role == "viewer":
            viewer_connections[device_id] = ws
            print(f"[relay] viewer: {device_id}")
            if device_id not in host_connections:
                await ws.send(json.dumps({"error": "host not found"}))
                return
            host = host_connections[device_id]
            async for msg in ws:
                try:
                    await host.send(msg)
                except:
                    break

    except Exception as e:
        print(f"[relay] error: {e}")
    finally:
        if role == "host" and device_id:
            host_connections.pop(device_id, None)
            print(f"[relay] host offline: {device_id}")
        elif role == "viewer" and device_id:
            viewer_connections.pop(device_id, None)

async def main():
    port = int(os.environ.get("PORT", 8080))
    print(f"[relay] port {port}")
    async with websockets.serve(handler, "0.0.0.0", port, max_size=10*1024*1024):
        await asyncio.Future()

asyncio.run(main())
