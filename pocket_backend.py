#!/usr/bin/env python3
"""
PocketController Backend Engine
Maneja servidores HTTP, WebSockets y dispositivos UInput (Xbox 360) para hasta 4 jugadores.
"""

import asyncio
import http.server
import json
import os
import socket
import socketserver
import subprocess
import threading
import time
import evdev
from evdev import UInput, ecodes as e
import websockets

HTTP_PORT_DEFAULT = 5500
WS_PORT_DEFAULT = 5501
MAX_PLAYERS = 4
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_tailscale_ip():
    try:
        res = subprocess.run(['tailscale', 'ip', '-4'], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            ip = res.stdout.strip()
            if ip:
                return ip
    except Exception:
        pass
    return None

# Configuración de ejes analógicos (Estándar Xbox 360)
abs_stick = evdev.AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)
abs_trigger = evdev.AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
abs_hat = evdev.AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)

BUTTON_MAP = {
    "A": e.BTN_SOUTH,      # 0x130 (A)
    "B": e.BTN_EAST,       # 0x131 (B)
    "X": e.BTN_NORTH,      # 0x133 (X)
    "Y": e.BTN_WEST,       # 0x134 (Y)
    "L": e.BTN_TL,         # 0x136 (LB / L)
    "R": e.BTN_TR,         # 0x137 (RB / R)
    "MINUS": e.BTN_SELECT, # 0x13a (Back / View)
    "PLUS": e.BTN_START,   # 0x13b (Start / Menu)
    "HOME": e.BTN_MODE,    # 0x13c (Guide / Xbox)
    "CAPTURE": e.BTN_MODE, # 0x13c
    "L3": e.BTN_THUMBL,    # 0x13d (Stick Izquierdo Click)
    "R3": e.BTN_THUMBR,    # 0x13e (Stick Derecho Click)
}

BUTTON_KEYS = list(set(BUTTON_MAP.values()))

CAPABILITIES = {
    e.EV_KEY: BUTTON_KEYS,
    e.EV_ABS: [
        (e.ABS_X, abs_stick),       # Axis 0: Left Stick X
        (e.ABS_Y, abs_stick),       # Axis 1: Left Stick Y
        (e.ABS_RX, abs_stick),      # Axis 3: Right Stick X
        (e.ABS_RY, abs_stick),      # Axis 4: Right Stick Y
        (e.ABS_Z, abs_trigger),     # Axis 2: Left Trigger (LT / ZL)
        (e.ABS_RZ, abs_trigger),    # Axis 5: Right Trigger (RT / ZR)
        (e.ABS_HAT0X, abs_hat),     # D-Pad X (-1, 0, 1)
        (e.ABS_HAT0Y, abs_hat),     # D-Pad Y (-1, 0, 1)
    ]
}

class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

class CustomHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        # Silenciar logs ruidosos de peticiones HTTP
        pass

class PocketBackend:
    def __init__(self, http_port=HTTP_PORT_DEFAULT, ws_port=WS_PORT_DEFAULT):
        self.http_port = http_port
        self.ws_port = ws_port
        self.is_running = False

        # Virtual gamepads
        self.player_devices = {}
        self.client_slots = {} # websocket -> player_id
        self.slot_lock = threading.Lock()

        # Telemetría de estado por jugador (hilo-seguro para lectura de la GUI)
        self.player_states = {
            p: {
                "connected": False,
                "client_ip": None,
                "device_path": None,
                "buttons": {},
                "lx": 0, "ly": 0,
                "rx": 0, "ry": 0,
                "hatX": 0, "hatY": 0,
                "zl": False, "zr": False,
                "lt_val": 0, "rt_val": 0,
                "last_seen": 0
            } for p in range(1, MAX_PLAYERS + 1)
        }

        # Subprocesos / hilos
        self._httpd = None
        self._http_thread = None
        self._ws_loop = None
        self._ws_server = None
        self._ws_thread = None

        # Callbacks (inyectables por la GUI)
        self.on_log = None
        self.on_status_change = None
        self.on_player_connect = None
        self.on_player_disconnect = None

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {msg}"
        print(formatted)
        if self.on_log:
            try:
                self.on_log(formatted)
            except Exception:
                pass

    def get_or_create_device(self, player_id):
        if player_id not in self.player_devices:
            dev_name = f"Microsoft X-Box 360 pad (Player {player_id})"
            try:
                dev = UInput(
                    CAPABILITIES,
                    name=dev_name,
                    vendor=0x045e,
                    product=0x028e,
                    version=0x0114,
                    bustype=e.BUS_USB
                )
                self.player_devices[player_id] = dev
                dev_path = getattr(dev.device, 'path', f'/dev/input/js{player_id-1}')
                self.player_states[player_id]["device_path"] = dev_path
                self.log(f"🎮 [P{player_id}] Mando virtual activado en {dev_path}")
            except Exception as err:
                self.log(f"❌ Error creando UInput para Jugador {player_id}: {err}")
                return None
        return self.player_devices.get(player_id)

    def reset_device(self, player_id):
        dev = self.player_devices.get(player_id)
        if dev:
            try:
                for code in BUTTON_KEYS:
                    dev.write(e.EV_KEY, code, 0)
                dev.write(e.EV_ABS, e.ABS_X, 0)
                dev.write(e.EV_ABS, e.ABS_Y, 0)
                dev.write(e.EV_ABS, e.ABS_RX, 0)
                dev.write(e.EV_ABS, e.ABS_RY, 0)
                dev.write(e.EV_ABS, e.ABS_Z, 0)
                dev.write(e.EV_ABS, e.ABS_RZ, 0)
                dev.write(e.EV_ABS, e.ABS_HAT0X, 0)
                dev.write(e.EV_ABS, e.ABS_HAT0Y, 0)
                dev.syn()
            except Exception:
                pass
        
        # Reset local telemetry
        state = self.player_states[player_id]
        state["buttons"] = {}
        state["lx"] = 0
        state["ly"] = 0
        state["rx"] = 0
        state["ry"] = 0
        state["hatX"] = 0
        state["hatY"] = 0
        state["zl"] = False
        state["zr"] = False
        state["lt_val"] = 0
        state["rt_val"] = 0

    def _start_http(self):
        try:
            self._httpd = ThreadingHTTPServer(("", self.http_port), CustomHTTPHandler)
            self._httpd.serve_forever()
        except Exception as ex:
            self.log(f"❌ Error en servidor HTTP (puerto {self.http_port}): {ex}")

    async def _ws_handler(self, websocket):
        assigned_slot = 1
        with self.slot_lock:
            occupied = set(self.client_slots.values())
            for s in range(1, MAX_PLAYERS + 1):
                if s not in occupied:
                    assigned_slot = s
                    break
            self.client_slots[websocket] = assigned_slot

        dev = self.get_or_create_device(assigned_slot)
        client_ip = websocket.remote_address[0] if websocket.remote_address else "Móvil"
        
        state = self.player_states[assigned_slot]
        state["connected"] = True
        state["client_ip"] = client_ip
        state["last_seen"] = time.time()

        self.log(f"📱 [+] {client_ip} conectado -> JUGADOR {assigned_slot}")
        if self.on_player_connect:
            try:
                self.on_player_connect(assigned_slot, client_ip)
            except Exception:
                pass

        try:
            await websocket.send(json.dumps({
                "type": "assigned",
                "player": assigned_slot,
                "max_players": MAX_PLAYERS
            }))

            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "input")

                    # Cambio manual de jugador
                    if msg_type == "change_player":
                        req_slot = int(data.get("player", assigned_slot))
                        if 1 <= req_slot <= MAX_PLAYERS:
                            with self.slot_lock:
                                occupied = {s for ws, s in self.client_slots.items() if ws != websocket}
                                if req_slot not in occupied:
                                    self.reset_device(assigned_slot)
                                    self.player_states[assigned_slot]["connected"] = False
                                    self.player_states[assigned_slot]["client_ip"] = None
                                    
                                    assigned_slot = req_slot
                                    self.client_slots[websocket] = assigned_slot
                                    dev = self.get_or_create_device(assigned_slot)
                                    
                                    self.player_states[assigned_slot]["connected"] = True
                                    self.player_states[assigned_slot]["client_ip"] = client_ip
                                    self.log(f"🔄 {client_ip} cambió a -> JUGADOR {assigned_slot}")
                                    await websocket.send(json.dumps({"type": "assigned", "player": assigned_slot}))
                                else:
                                    await websocket.send(json.dumps({"type": "error", "message": f"Jugador {req_slot} ocupado"}))
                        continue

                    if not dev:
                        continue

                    # Entrada analógica y digital
                    buttons = data.get("buttons", {})
                    zl_pressed = bool(buttons.get("ZL", 0) or buttons.get("LT", 0))
                    zr_pressed = bool(buttons.get("ZR", 0) or buttons.get("RT", 0))
                    lx = int(data.get("lx", 0))
                    ly = int(data.get("ly", 0))
                    rx = int(data.get("rx", 0))
                    ry = int(data.get("ry", 0))
                    hatX = int(data.get("hatX", 0))
                    hatY = int(data.get("hatY", 0))

                    lt_val = int(data.get("lt", 255 if zl_pressed else 0))
                    rt_val = int(data.get("rt", 255 if zr_pressed else 0))

                    # Actualizar estado para la GUI
                    state["buttons"] = buttons
                    state["zl"] = zl_pressed
                    state["zr"] = zr_pressed
                    state["lt_val"] = lt_val
                    state["rt_val"] = rt_val
                    state["lx"] = lx
                    state["ly"] = ly
                    state["rx"] = rx
                    state["ry"] = ry
                    state["hatX"] = hatX
                    state["hatY"] = hatY
                    state["last_seen"] = time.time()

                    # Transmitir a UInput Xbox 360
                    for name, code in BUTTON_MAP.items():
                        val = buttons.get(name, 0)
                        dev.write(e.EV_KEY, code, 1 if val else 0)

                    dev.write(e.EV_ABS, e.ABS_Z, 255 if zl_pressed else 0)
                    dev.write(e.EV_ABS, e.ABS_RZ, 255 if zr_pressed else 0)
                    dev.write(e.EV_ABS, e.ABS_X, lx)
                    dev.write(e.EV_ABS, e.ABS_Y, ly)
                    dev.write(e.EV_ABS, e.ABS_RX, rx)
                    dev.write(e.EV_ABS, e.ABS_RY, ry)
                    dev.write(e.EV_ABS, e.ABS_HAT0X, hatX)
                    dev.write(e.EV_ABS, e.ABS_HAT0Y, hatY)
                    dev.syn()

                except Exception:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            with self.slot_lock:
                if websocket in self.client_slots:
                    p_freed = self.client_slots.pop(websocket)
                    self.reset_device(p_freed)
                    self.player_states[p_freed]["connected"] = False
                    self.player_states[p_freed]["client_ip"] = None
                    self.log(f"📱 [-] {client_ip} desconectado (Liberado Jugador {p_freed})")
                    if self.on_player_disconnect:
                        try:
                            self.on_player_disconnect(p_freed)
                        except Exception:
                            pass

    def _run_ws_loop(self):
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)

        async def run_server():
            async with websockets.serve(self._ws_handler, "0.0.0.0", self.ws_port):
                self._ws_stop_event = asyncio.Event()
                await self._ws_stop_event.wait()

        try:
            self._ws_loop.run_until_complete(run_server())
        except Exception as ex:
            if self.is_running:
                self.log(f"❌ Error en bucle WebSocket: {ex}")
        finally:
            try:
                self._ws_loop.close()
            except Exception:
                pass

    def start(self):
        if self.is_running:
            return

        self.log(f"🚀 Iniciando servidor PocketController (HTTP :{self.http_port}, WS :{self.ws_port})...")
        
        # Pre-crear mando 1
        self.get_or_create_device(1)

        # Iniciar HTTP
        self._http_thread = threading.Thread(target=self._start_http, daemon=True)
        self._http_thread.start()

        # Iniciar WebSockets
        self._ws_thread = threading.Thread(target=self._run_ws_loop, daemon=True)
        self._ws_thread.start()

        self.is_running = True
        local_ip = get_local_ip()
        ts_ip = get_tailscale_ip()
        self.log(f"✅ Servidor activo en http://{local_ip}:{self.http_port}")
        if ts_ip:
            self.log(f"🌐 Tailscale activo en http://{ts_ip}:{self.http_port}")

        if self.on_status_change:
            try:
                self.on_status_change(True)
            except Exception:
                pass

    def stop(self):
        if not self.is_running:
            return

        self.log("🛑 Deteniendo servidores y liberando dispositivos uinput...")
        self.is_running = False

        # Detener HTTP
        if self._httpd:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None

        # Detener WebSockets
        if self._ws_loop and hasattr(self, '_ws_stop_event'):
            try:
                self._ws_loop.call_soon_threadsafe(self._ws_stop_event.set)
            except Exception:
                pass

        # Reset y cerrar dispositivos
        for p in range(1, MAX_PLAYERS + 1):
            self.reset_device(p)
            self.player_states[p]["connected"] = False
            self.player_states[p]["client_ip"] = None

        for dev in list(self.player_devices.values()):
            try:
                dev.close()
            except Exception:
                pass
        self.player_devices.clear()
        self.client_slots.clear()

        self.log("⏹️ Servidor detenido correctamente.")
        if self.on_status_change:
            try:
                self.on_status_change(False)
            except Exception:
                pass

    def restart(self):
        self.stop()
        time.sleep(0.5)
        self.start()

    def inject_button(self, player_id, button_name, pressed: bool):
        dev = self.get_or_create_device(player_id)
        if not dev:
            return
        code = BUTTON_MAP.get(button_name)
        if code is not None:
            dev.write(e.EV_KEY, code, 1 if pressed else 0)
            dev.syn()
            self.player_states[player_id]["buttons"][button_name] = 1 if pressed else 0

    def inject_trigger(self, player_id, trigger_name, value: int):
        dev = self.get_or_create_device(player_id)
        if not dev:
            return
        val = max(0, min(255, int(value)))
        if trigger_name in ("LT", "ZL"):
            dev.write(e.EV_ABS, e.ABS_Z, val)
            self.player_states[player_id]["zl"] = (val > 0)
            self.player_states[player_id]["lt_val"] = val
        elif trigger_name in ("RT", "ZR"):
            dev.write(e.EV_ABS, e.ABS_RZ, val)
            self.player_states[player_id]["zr"] = (val > 0)
            self.player_states[player_id]["rt_val"] = val
        dev.syn()

    def inject_stick(self, player_id, stick_name, x: int, y: int):
        dev = self.get_or_create_device(player_id)
        if not dev:
            return
        x = max(-32768, min(32767, int(x)))
        y = max(-32768, min(32767, int(y)))
        if stick_name == "left":
            dev.write(e.EV_ABS, e.ABS_X, x)
            dev.write(e.EV_ABS, e.ABS_Y, y)
            self.player_states[player_id]["lx"] = x
            self.player_states[player_id]["ly"] = y
        elif stick_name == "right":
            dev.write(e.EV_ABS, e.ABS_RX, x)
            dev.write(e.EV_ABS, e.ABS_RY, y)
            self.player_states[player_id]["rx"] = x
            self.player_states[player_id]["ry"] = y
        dev.syn()

    def inject_dpad(self, player_id, hatX: int, hatY: int):
        dev = self.get_or_create_device(player_id)
        if not dev:
            return
        dev.write(e.EV_ABS, e.ABS_HAT0X, hatX)
        dev.write(e.EV_ABS, e.ABS_HAT0Y, hatY)
        self.player_states[player_id]["hatX"] = hatX
        self.player_states[player_id]["hatY"] = hatY
        dev.syn()

    def run_auto_test(self, player_id):
        def _test():
            self.log(f"🧪 Iniciando Auto-Test del Mando (Jugador {player_id})...")
            # 1. Probar botones ABXY y frontales
            for btn in ["A", "B", "X", "Y", "L", "R", "MINUS", "PLUS", "HOME", "L3", "R3"]:
                self.inject_button(player_id, btn, True)
                time.sleep(0.12)
                self.inject_button(player_id, btn, False)
                time.sleep(0.05)

            # 2. Probar D-Pad en las 4 direcciones
            dpad_steps = [(0, -1), (1, 0), (0, 1), (-1, 0), (0, 0)]
            for (hx, hy) in dpad_steps:
                self.inject_dpad(player_id, hx, hy)
                time.sleep(0.12)

            # 3. Probar Gatillos Progresivos (LT y RT)
            for v in [64, 128, 255, 128, 0]:
                self.inject_trigger(player_id, "LT", v)
                self.inject_trigger(player_id, "RT", v)
                time.sleep(0.08)

            # 4. Probar giro orbital de los Sticks (360 grados)
            import math
            for angle in range(0, 360, 20):
                rad = math.radians(angle)
                sx = int(math.cos(rad) * 32000)
                sy = int(math.sin(rad) * 32000)
                self.inject_stick(player_id, "left", sx, sy)
                self.inject_stick(player_id, "right", -sx, -sy)
                time.sleep(0.03)

            self.inject_stick(player_id, "left", 0, 0)
            self.inject_stick(player_id, "right", 0, 0)
            self.reset_device(player_id)
            self.log(f"✅ Auto-Test del Mando (Jugador {player_id}) finalizado con éxito.")

        threading.Thread(target=_test, daemon=True).start()

if __name__ == "__main__":
    server = PocketBackend()
    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
