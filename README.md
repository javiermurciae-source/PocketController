# PocketController

Convierte dispositivos móviles en mandos virtuales de juego (Xbox 360 / UInput) para Linux vía WebSockets y HTTP.

## Características
- Soporte para hasta 4 jugadores simultáneos.
- Emulación uinput de gamepads Xbox 360 en Linux.
- Backend en Python (`pocket_backend.py`) con WebSockets y servidor HTTP.
- Interfaz gráfica moderna en PyQt6 (`pocket_gui.py`).
- Cliente web táctil y APK incluida (`PocketController.apk`).

## Requisitos
```bash
pip install evdev websockets PyQt6
```

## Uso
Ejecutar la interfaz gráfica:
```bash
python pocket_gui.py
```
O correr únicamente el servidor backend:
```bash
python pocket_backend.py
```
