import asyncio
import websockets

clients = {}

async def handler(ws):
    device_id = None
    try:
        msg = await ws.recv()
        import json
        data = json.loads(msg)
        device_id = data.get("id")
        role = data.get("role")
        
        if role == "host":
            clients[device_id] = {"host": ws, "viewer": None}
            print(f"[relay] host: {device_id}")
            await ws.send(json.dumps({"status": "waiting"}))
            await ws.wait_closed()
        elif role == "viewer":
            if device_id in clients and clients[device_id]["host"]:
                clients[device_id]["viewer"] = ws
                host = clients[device_id]["host"]
                print(f"[relay] viewer joined: {device_id}")
                async def forward(src, dst):
                    try:
                        async for msg in src:
                            await dst.send(msg)
                    except:
                        pass
                await asyncio.gather(
                    forward(ws, host),
                    forward(host, ws)
                )
    except Exception as e:
        print(f"[relay] error: {e}")
    finally:
        if device_id and device_id in clients:
            if clients[device_id].get("host") == ws:
                del clients[device_id]
                print(f"[relay] host left: {device_id}")

async def main():
    port = int(__import__("os").environ.get("PORT", 8080))
    print(f"[relay] starting on :{port}")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()

asyncio.run(main())
