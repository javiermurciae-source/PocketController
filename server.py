#!/usr/bin/env python3
"""
PocketController Server CLI
Mantiene compatibilidad con ejecuciones directas por consola usando el motor pocket_backend.
"""

import time
import sys
from pocket_backend import PocketBackend, get_local_ip, get_tailscale_ip, HTTP_PORT_DEFAULT, MAX_PLAYERS

def main():
    backend = PocketBackend()
    backend.start()

    ip = get_local_ip()
    ts_ip = get_tailscale_ip()

    print("=" * 65)
    print(" 🎮 POCKET CONTROLLER MULTI-JUGADOR PRO (XBOX / SWITCH / PS)")
    print("=" * 65)
    print(f" 🌐 Conecta tus celulares abriendo: 👉 http://{ip}:{HTTP_PORT_DEFAULT}")
    if ts_ip:
        print(f" 🌐 Tailscale (amigos a distancia): 👉 http://{ts_ip}:{HTTP_PORT_DEFAULT}")
    print(f" 👥 Soporta hasta {MAX_PLAYERS} celulares simultáneos (Jugadores 1 a 4)")
    print(" 💡 Presiona Ctrl+C para detener el servidor")
    print("=" * 65)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
    finally:
        backend.stop()

if __name__ == "__main__":
    main()
