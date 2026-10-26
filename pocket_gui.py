#!/usr/bin/env python3
"""
PocketController GUI - Aplicación Gráfica Nativa en GTK4 y Libadwaita
Mando virtual para PC controlado desde teléfonos móviles (Wi-Fi / Tailscale)
con Probador y Visualizador de Control Real Completo (Xbox 360).
"""

import math
import os
import sys
import tempfile
import subprocess
import threading
import time

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Pango

# Importar motor backend
from pocket_backend import (
    PocketBackend,
    get_local_ip,
    get_tailscale_ip,
    HTTP_PORT_DEFAULT,
    WS_PORT_DEFAULT,
    MAX_PLAYERS,
    BASE_DIR
)

APP_ID = "com.streamzone.pocketcontroller"
APP_NAME = "Pocket Controller"

CSS_STYLES = """
/* Estilos modernos y tema gaming para Pocket Controller */
.main-window {
    background-color: @window_bg_color;
}

.status-badge {
    padding: 4px 10px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.5px;
}
.status-badge.online {
    background-color: rgba(46, 213, 115, 0.2);
    color: #2ed573;
    border: 1px solid rgba(46, 213, 115, 0.4);
}
.status-badge.offline {
    background-color: rgba(255, 71, 87, 0.15);
    color: #ff4757;
    border: 1px solid rgba(255, 71, 87, 0.3);
}

.card-box {
    background: alpha(@card_bg_color, 0.7);
    border: 1px solid alpha(@borders, 0.5);
    border-radius: 12px;
    padding: 16px;
}

/* Chasis del control real */
.controller-body {
    background: radial-gradient(circle at 50% 30%, #1e293b, #0f172a);
    border: 2px solid #334155;
    border-radius: 28px;
    padding: 24px 32px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
}

/* Bumpers LB y RB */
.bumper-btn {
    min-width: 130px;
    min-height: 38px;
    border-radius: 8px;
    font-weight: 800;
    font-size: 13px;
    background: #1e293b;
    color: #cbd5e1;
    border: 1px solid #475569;
}
.bumper-btn.pressed {
    background: #0284c7;
    color: #ffffff;
    border-color: #38bdf8;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.7);
}

/* Gatillos analógicos LT y RT */
.trigger-box {
    min-width: 130px;
    padding: 6px 10px;
    background: rgba(15, 23, 42, 0.8);
    border-radius: 8px;
    border: 1px solid #334155;
}
.trigger-bar progress {
    background-color: #10b981;
    border-radius: 4px;
}
.trigger-bar trough {
    background-color: #334155;
    border-radius: 4px;
    min-height: 8px;
}

/* Botones centrales */
.center-btn {
    min-width: 42px;
    min-height: 28px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: bold;
    background: #1e293b;
    color: #94a3b8;
    border: 1px solid #475569;
}
.center-btn.pressed {
    background: #0284c7;
    color: #ffffff;
    border-color: #38bdf8;
}

.xbox-guide {
    min-width: 52px;
    min-height: 52px;
    border-radius: 9999px;
    font-size: 18px;
    font-weight: 900;
    background: #0f172a;
    color: #94a3b8;
    border: 2px solid #475569;
}
.xbox-guide.pressed {
    background: #10b981;
    color: #ffffff;
    border-color: #34d399;
    box-shadow: 0 0 16px rgba(16, 185, 129, 0.8);
}

/* Cruceta D-Pad */
.dpad-btn {
    min-width: 36px;
    min-height: 36px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: bold;
    background: #1e293b;
    color: #94a3b8;
    border: 1px solid #475569;
}
.dpad-btn.pressed {
    background: #0284c7;
    color: #ffffff;
    border-color: #38bdf8;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.7);
}
.dpad-center {
    min-width: 24px;
    min-height: 24px;
    border-radius: 4px;
    background: #0f172a;
}

/* Botones ABXY */
.abxy-round-btn {
    min-width: 44px;
    min-height: 44px;
    border-radius: 9999px;
    font-size: 16px;
    font-weight: 900;
    border: 2px solid rgba(255, 255, 255, 0.15);
}
.abxy-round-btn.btn-a {
    background: #064e3b;
    color: #34d399;
    border-color: #059669;
}
.abxy-round-btn.btn-a.pressed {
    background: #10b981;
    color: #ffffff;
    border-color: #6ee7b7;
    box-shadow: 0 0 16px #10b981;
}

.abxy-round-btn.btn-b {
    background: #7f1d1d;
    color: #f87171;
    border-color: #dc2626;
}
.abxy-round-btn.btn-b.pressed {
    background: #ef4444;
    color: #ffffff;
    border-color: #fca5a5;
    box-shadow: 0 0 16px #ef4444;
}

.abxy-round-btn.btn-x {
    background: #1e3a8a;
    color: #60a5fa;
    border-color: #2563eb;
}
.abxy-round-btn.btn-x.pressed {
    background: #3b82f6;
    color: #ffffff;
    border-color: #93c5fd;
    box-shadow: 0 0 16px #3b82f6;
}

.abxy-round-btn.btn-y {
    background: #713f12;
    color: #facc15;
    border-color: #ca8a04;
}
.abxy-round-btn.btn-y.pressed {
    background: #eab308;
    color: #ffffff;
    border-color: #fde047;
    box-shadow: 0 0 16px #eab308;
}

/* Botones L3 y R3 */
.stick-btn {
    min-width: 32px;
    min-height: 24px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    background: #1e293b;
    color: #94a3b8;
    border: 1px solid #475569;
}
.stick-btn.pressed {
    background: #0284c7;
    color: #ffffff;
    border-color: #38bdf8;
}

.log-view {
    font-family: monospace;
    font-size: 11px;
    background-color: rgba(0, 0, 0, 0.4);
    color: #a0aec0;
    padding: 10px;
    border-radius: 8px;
}
"""

class PocketControllerWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_title(APP_NAME)
        self.set_default_size(900, 720)
        self.add_css_class("main-window")

        # Iniciar backend
        self.backend = PocketBackend()
        self.backend.on_log = self._on_backend_log
        self.backend.on_status_change = self._on_backend_status_change
        self.backend.on_player_connect = self._on_backend_player_connect
        self.backend.on_player_disconnect = self._on_backend_player_disconnect

        self.qr_temp_path = os.path.join(tempfile.gettempdir(), "pocket_gui_qr.png")

        # Jugador seleccionado para el probador interactivo (1..4)
        self.active_test_player = 1

        # Construir Interfaz Gráfica
        self._build_ui()

        # Iniciar timer para telemetría visual de botones y sticks (30 Hz)
        GLib.timeout_add(33, self._update_inputs_telemetry)

        # Iniciar servidor por defecto
        self._start_server()

    def _build_ui(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root_box)

        # HeaderBar de Libadwaita
        header = Adw.HeaderBar()
        self.title_widget = Adw.WindowTitle(
            title="🎮 " + APP_NAME,
            subtitle="Probador y Servidor de Mando Xbox 360"
        )
        header.set_title_widget(self.title_widget)

        # Badge indicador en Header
        self.header_status_badge = Gtk.Label(label="ACTIVO")
        self.header_status_badge.add_css_class("status-badge")
        self.header_status_badge.add_css_class("online")
        header.pack_start(self.header_status_badge)

        # Botón switch en Header (Iniciar / Detener)
        self.server_toggle_btn = Gtk.Button(label="Detener")
        self.server_toggle_btn.add_css_class("destructive-action")
        self.server_toggle_btn.connect("clicked", self._on_toggle_server_clicked)
        header.pack_end(self.server_toggle_btn)

        root_box.append(header)

        # ViewStack (Pestañas)
        self.view_stack = Adw.ViewStack()
        self.view_stack.set_vexpand(True)

        # Switcher superior integrado
        view_switcher = Adw.ViewSwitcher()
        view_switcher.set_stack(self.view_stack)
        view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        
        switcher_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        switcher_box.set_halign(Gtk.Align.CENTER)
        switcher_box.set_margin_top(8)
        switcher_box.set_margin_bottom(8)
        switcher_box.append(view_switcher)
        root_box.append(switcher_box)

        root_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Agregar pestañas (¡El Control Real Completo al frente!)
        self._build_tab_full_controller()
        self._build_tab_connection()
        self._build_tab_players()
        self._build_tab_profiles()
        self._build_tab_logs()

        root_box.append(self.view_stack)

    # -------------------------------------------------------------
    # PESTAÑA 1: PROBADOR DE CONTROL REAL COMPLETO (XBOX 360)
    # -------------------------------------------------------------
    def _build_tab_full_controller(self):
        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(14)
        content.set_margin_bottom(20)
        page.set_child(content)

        # Barra Superior de Control del Probador
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        lbl_select = Gtk.Label(label="Mando a Probar:")
        lbl_select.add_css_class("heading")
        top_bar.append(lbl_select)

        self.player_selector_combo = Gtk.DropDown.new_from_strings([
            "🎮 Jugador 1 (/dev/input/js0)",
            "🎮 Jugador 2 (/dev/input/js1)",
            "🎮 Jugador 3 (/dev/input/js2)",
            "🎮 Jugador 4 (/dev/input/js3)"
        ])
        self.player_selector_combo.connect("notify::selected", self._on_test_player_changed)
        top_bar.append(self.player_selector_combo)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_bar.append(spacer)

        btn_auto_test = Gtk.Button(label="⚡ Auto-Test Completo")
        btn_auto_test.add_css_class("suggested-action")
        btn_auto_test.connect("clicked", lambda b: self.backend.run_auto_test(self.active_test_player))
        top_bar.append(btn_auto_test)

        btn_reset_pad = Gtk.Button(label="🔄 Reset Mando")
        btn_reset_pad.connect("clicked", lambda b: self.backend.reset_device(self.active_test_player))
        top_bar.append(btn_reset_pad)

        content.append(top_bar)

        # =========================================================
        # CHASIS DEL CONTROL REAL XBOX 360
        # =========================================================
        chassis = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        chassis.add_css_class("controller-body")
        content.append(chassis)

        # 1. FILA SUPERIOR: GATILLOS Y BUMPERS (LT, LB, RB, RT)
        top_triggers_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        top_triggers_box.set_halign(Gtk.Align.CENTER)

        # Lado Izquierdo Superior: LT y LB
        left_triggers_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        # LT (Gatillo Analógico Izquierdo)
        lt_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lt_card.add_css_class("trigger-box")
        lt_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lt_header.append(Gtk.Label(label="LT"))
        self.lt_val_label = Gtk.Label(label="0")
        self.lt_val_label.set_hexpand(True)
        self.lt_val_label.set_halign(Gtk.Align.END)
        self.lt_val_label.add_css_class("dim-label")
        lt_header.append(self.lt_val_label)
        lt_card.append(lt_header)

        self.lt_progress = Gtk.ProgressBar()
        self.lt_progress.add_css_class("trigger-bar")
        self.lt_progress.set_fraction(0.0)
        lt_card.append(self.lt_progress)
        left_triggers_box.append(lt_card)

        # LB (Bumper Izquierdo)
        self.btn_lb = Gtk.Button(label="LB")
        self.btn_lb.add_css_class("bumper-btn")
        self._bind_button_click(self.btn_lb, "L")
        left_triggers_box.append(self.btn_lb)
        top_triggers_box.append(left_triggers_box)

        # Separador central superior
        center_spacer = Gtk.Box()
        center_spacer.set_hexpand(True)
        top_triggers_box.append(center_spacer)

        # Lado Derecho Superior: RB y RT
        right_triggers_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        # RB (Bumper Derecho)
        self.btn_rb = Gtk.Button(label="RB")
        self.btn_rb.add_css_class("bumper-btn")
        self._bind_button_click(self.btn_rb, "R")
        right_triggers_box.append(self.btn_rb)

        # RT (Gatillo Analógico Derecho)
        rt_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rt_card.add_css_class("trigger-box")
        rt_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        rt_header.append(Gtk.Label(label="RT"))
        self.rt_val_label = Gtk.Label(label="0")
        self.rt_val_label.set_hexpand(True)
        self.rt_val_label.set_halign(Gtk.Align.END)
        self.rt_val_label.add_css_class("dim-label")
        rt_header.append(self.rt_val_label)
        rt_card.append(rt_header)

        self.rt_progress = Gtk.ProgressBar()
        self.rt_progress.add_css_class("trigger-bar")
        self.rt_progress.set_fraction(0.0)
        rt_card.append(self.rt_progress)
        right_triggers_box.append(rt_card)

        top_triggers_box.append(right_triggers_box)
        chassis.append(top_triggers_box)

        # 2. FILA MEDIA CENTRAL: NAVEGACIÓN Y GUÍA (BACK, GUÍA XBOX, START)
        center_nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        center_nav_box.set_halign(Gtk.Align.CENTER)

        self.btn_back = Gtk.Button(label="◀ BACK")
        self.btn_back.add_css_class("center-btn")
        self._bind_button_click(self.btn_back, "MINUS")
        center_nav_box.append(self.btn_back)

        self.btn_guide = Gtk.Button(label="✜")
        self.btn_guide.add_css_class("xbox-guide")
        self._bind_button_click(self.btn_guide, "HOME")
        center_nav_box.append(self.btn_guide)

        self.btn_start = Gtk.Button(label="START ▶")
        self.btn_start.add_css_class("center-btn")
        self._bind_button_click(self.btn_start, "PLUS")
        center_nav_box.append(self.btn_start)

        chassis.append(center_nav_box)

        # 3. CUERPO PRINCIPAL DEL MANDO (STICKS, CRUCETA Y BOTONES ABXY)
        main_pad_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)
        main_pad_box.set_halign(Gtk.Align.CENTER)

        # --- SECTOR IZQUIERDO: STICK IZQUIERDO (SUPERIOR) Y CRUCETA D-PAD (INFERIOR) ---
        left_sector = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        left_sector.set_halign(Gtk.Align.CENTER)

        # Stick Izquierdo (LS)
        ls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ls_box.set_halign(Gtk.Align.CENTER)
        
        self.ls_drawing = Gtk.DrawingArea()
        self.ls_drawing.set_content_width(110)
        self.ls_drawing.set_content_height(110)
        self.ls_drawing.set_draw_func(self._draw_left_stick)
        ls_box.append(self.ls_drawing)

        ls_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ls_controls.set_halign(Gtk.Align.CENTER)
        self.btn_l3 = Gtk.Button(label="L3")
        self.btn_l3.add_css_class("stick-btn")
        self._bind_button_click(self.btn_l3, "L3")
        ls_controls.append(self.btn_l3)

        self.ls_coord_label = Gtk.Label(label="(0, 0)")
        self.ls_coord_label.add_css_class("dim-label")
        ls_controls.append(self.ls_coord_label)
        ls_box.append(ls_controls)
        left_sector.append(ls_box)

        # Cruceta D-Pad
        dpad_box = Gtk.Grid(column_spacing=4, row_spacing=4)
        dpad_box.set_halign(Gtk.Align.CENTER)

        self.btn_dpad_up = Gtk.Button(label="▲")
        self.btn_dpad_up.add_css_class("dpad-btn")
        self._bind_dpad_click(self.btn_dpad_up, 0, -1)
        dpad_box.attach(self.btn_dpad_up, 1, 0, 1, 1)

        self.btn_dpad_left = Gtk.Button(label="◀")
        self.btn_dpad_left.add_css_class("dpad-btn")
        self._bind_dpad_click(self.btn_dpad_left, -1, 0)
        dpad_box.attach(self.btn_dpad_left, 0, 1, 1, 1)

        dpad_center_indicator = Gtk.Label(label="•")
        dpad_center_indicator.add_css_class("dpad-center")
        dpad_box.attach(dpad_center_indicator, 1, 1, 1, 1)

        self.btn_dpad_right = Gtk.Button(label="▶")
        self.btn_dpad_right.add_css_class("dpad-btn")
        self._bind_dpad_click(self.btn_dpad_right, 1, 0)
        dpad_box.attach(self.btn_dpad_right, 2, 1, 1, 1)

        self.btn_dpad_down = Gtk.Button(label="▼")
        self.btn_dpad_down.add_css_class("dpad-btn")
        self._bind_dpad_click(self.btn_dpad_down, 0, 1)
        dpad_box.attach(self.btn_dpad_down, 1, 2, 1, 1)

        left_sector.append(dpad_box)
        main_pad_box.append(left_sector)

        # --- SECTOR DERECHO: BOTONES ABXY (SUPERIOR) Y STICK DERECHO (INFERIOR) ---
        right_sector = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        right_sector.set_halign(Gtk.Align.CENTER)

        # Cluster ABXY en Diamante
        abxy_grid = Gtk.Grid(column_spacing=6, row_spacing=6)
        abxy_grid.set_halign(Gtk.Align.CENTER)

        # Y (Arriba, Amarillo)
        self.btn_y = Gtk.Button(label="Y")
        self.btn_y.add_css_class("abxy-round-btn")
        self.btn_y.add_css_class("btn-y")
        self._bind_button_click(self.btn_y, "Y")
        abxy_grid.attach(self.btn_y, 1, 0, 1, 1)

        # X (Izquierda, Azul)
        self.btn_x = Gtk.Button(label="X")
        self.btn_x.add_css_class("abxy-round-btn")
        self.btn_x.add_css_class("btn-x")
        self._bind_button_click(self.btn_x, "X")
        abxy_grid.attach(self.btn_x, 0, 1, 1, 1)

        # B (Derecha, Rojo)
        self.btn_b = Gtk.Button(label="B")
        self.btn_b.add_css_class("abxy-round-btn")
        self.btn_b.add_css_class("btn-b")
        self._bind_button_click(self.btn_b, "B")
        abxy_grid.attach(self.btn_b, 2, 1, 1, 1)

        # A (Abajo, Verde)
        self.btn_a = Gtk.Button(label="A")
        self.btn_a.add_css_class("abxy-round-btn")
        self.btn_a.add_css_class("btn-a")
        self._bind_button_click(self.btn_a, "A")
        abxy_grid.attach(self.btn_a, 1, 2, 1, 1)

        right_sector.append(abxy_grid)

        # Stick Derecho (RS)
        rs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rs_box.set_halign(Gtk.Align.CENTER)

        self.rs_drawing = Gtk.DrawingArea()
        self.rs_drawing.set_content_width(110)
        self.rs_drawing.set_content_height(110)
        self.rs_drawing.set_draw_func(self._draw_right_stick)
        rs_box.append(self.rs_drawing)

        rs_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        rs_controls.set_halign(Gtk.Align.CENTER)
        self.btn_r3 = Gtk.Button(label="R3")
        self.btn_r3.add_css_class("stick-btn")
        self._bind_button_click(self.btn_r3, "R3")
        rs_controls.append(self.btn_r3)

        self.rs_coord_label = Gtk.Label(label="(0, 0)")
        self.rs_coord_label.add_css_class("dim-label")
        rs_controls.append(self.rs_coord_label)
        rs_box.append(rs_controls)

        right_sector.append(rs_box)
        main_pad_box.append(right_sector)

        chassis.append(main_pad_box)

        # Mensaje de ayuda / interactividad
        help_hint = Gtk.Label(
            label="💡 Puedes probar presionando los botones en tu teléfono o haciendo clic sobre ellos en esta pantalla para probarlos en Linux."
        )
        help_hint.set_wrap(True)
        help_hint.set_justify(Gtk.Justification.CENTER)
        help_hint.add_css_class("dim-label")
        content.append(help_hint)

        self.view_stack.add_titled(page, "full_controller", "🎯 Control Real")

    # -------------------------------------------------------------
    # BINDINGS INTERACTIVOS PARA TEST CON EL RATÓN / PANTALLA
    # -------------------------------------------------------------
    def _bind_button_click(self, button, code_name):
        def _on_pressed(btn):
            self.backend.inject_button(self.active_test_player, code_name, True)
        def _on_released(btn):
            self.backend.inject_button(self.active_test_player, code_name, False)
        
        click = Gtk.GestureClick()
        click.connect("pressed", lambda g, n, x, y: _on_pressed(button))
        click.connect("released", lambda g, n, x, y: _on_released(button))
        button.add_controller(click)

    def _bind_dpad_click(self, button, hat_x, hat_y):
        def _on_pressed(btn):
            self.backend.inject_dpad(self.active_test_player, hat_x, hat_y)
        def _on_released(btn):
            self.backend.inject_dpad(self.active_test_player, 0, 0)

        click = Gtk.GestureClick()
        click.connect("pressed", lambda g, n, x, y: _on_pressed(button))
        click.connect("released", lambda g, n, x, y: _on_released(button))
        button.add_controller(click)

    def _on_test_player_changed(self, widget, pspec):
        self.active_test_player = widget.get_selected() + 1
        self.backend.log(f"🎯 Probador enfocado en Jugador {self.active_test_player}")

    # -------------------------------------------------------------
    # DIBUJO DE STICKS ANALÓGICOS EN 2D CON CAIRO
    # -------------------------------------------------------------
    def _draw_left_stick(self, area, cr, width, height):
        state = self.backend.player_states[self.active_test_player]
        lx = state.get("lx", 0)
        ly = state.get("ly", 0)
        l3 = bool(state.get("buttons", {}).get("L3", 0))
        self._render_stick_radar(cr, width, height, lx, ly, l3)

    def _draw_right_stick(self, area, cr, width, height):
        state = self.backend.player_states[self.active_test_player]
        rx = state.get("rx", 0)
        ry = state.get("ry", 0)
        r3 = bool(state.get("buttons", {}).get("R3", 0))
        self._render_stick_radar(cr, width, height, rx, ry, r3)

    def _render_stick_radar(self, cr, width, height, x_val, y_val, is_clicked):
        cx = width / 2.0
        cy = height / 2.0
        radius = min(cx, cy) - 6.0

        # Fondo del pozo del stick
        cr.set_source_rgb(0.08, 0.11, 0.16)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.fill()

        # Borde exterior cian
        cr.set_source_rgb(0.22, 0.74, 0.97)
        cr.set_line_width(2.0)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.stroke()

        # Ejes en cruz tenue
        cr.set_source_rgba(1, 1, 1, 0.12)
        cr.set_line_width(1.0)
        cr.move_to(cx - radius + 4, cy)
        cr.line_to(cx + radius - 4, cy)
        cr.move_to(cx, cy - radius + 4)
        cr.line_to(cx, cy + radius - 4)
        cr.stroke()

        # Posición normalizada (-32768 a 32767)
        norm_x = max(-1.0, min(1.0, x_val / 32768.0))
        norm_y = max(-1.0, min(1.0, y_val / 32768.0))

        stick_radius = radius * 0.38
        max_travel = radius - stick_radius - 2.0
        sx = cx + norm_x * max_travel
        sy = cy + norm_y * max_travel

        # Puck / Sombrilla del stick
        if is_clicked:
            cr.set_source_rgb(0.01, 0.52, 0.78)
        else:
            cr.set_source_rgb(0.18, 0.24, 0.32)
        cr.arc(sx, sy, stick_radius, 0, 2 * math.pi)
        cr.fill()

        # Borde del puck
        cr.set_source_rgb(0.58, 0.64, 0.72)
        cr.set_line_width(1.5)
        cr.arc(sx, sy, stick_radius, 0, 2 * math.pi)
        cr.stroke()

        # Centro luminoso
        cr.set_source_rgb(0.22, 0.74, 0.97)
        cr.arc(sx, sy, 3.5, 0, 2 * math.pi)
        cr.fill()

    # -------------------------------------------------------------
    # PESTAÑA 2: CONEXIÓN & CÓDIGO QR
    # -------------------------------------------------------------
    def _build_tab_connection(self):
        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(16)
        content.set_margin_bottom(24)
        page.set_child(content)

        grid = Gtk.Grid(column_spacing=20, row_spacing=16)
        grid.set_column_homogeneous(True)
        content.append(grid)

        # Columna Izquierda: Tarjetas de Enlaces
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        grid.attach(left_box, 0, 0, 1, 1)

        # Tarjeta Wi-Fi Local
        local_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        local_card.add_css_class("card-box")

        local_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        local_icon = Gtk.Label(label="📶")
        local_title = Gtk.Label(label="Red Local Wi-Fi (Mismo Hogar)")
        local_title.add_css_class("heading")
        local_header.append(local_icon)
        local_header.append(local_title)
        local_card.append(local_header)

        self.local_url_label = Gtk.Label()
        self.local_url_label.set_halign(Gtk.Align.START)
        self.local_url_label.set_selectable(True)
        self.local_url_label.add_css_class("accent")
        local_card.append(self.local_url_label)

        btn_row_local = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_copy_local = Gtk.Button(label="📋 Copiar Enlace")
        btn_copy_local.connect("clicked", lambda b: self._copy_to_clipboard(self.local_url))
        btn_open_local = Gtk.Button(label="🌐 Probar en PC")
        btn_open_local.connect("clicked", lambda b: subprocess.run(["xdg-open", self.local_url]))
        btn_row_local.append(btn_copy_local)
        btn_row_local.append(btn_open_local)
        local_card.append(btn_row_local)
        left_box.append(local_card)

        # Tarjeta Tailscale (Amigos a distancia)
        ts_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        ts_card.add_css_class("card-box")

        ts_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ts_icon = Gtk.Label(label="🌐")
        ts_title = Gtk.Label(label="Tailscale VPN (Para Amigos a Distancia)")
        ts_title.add_css_class("heading")
        ts_header.append(ts_icon)
        ts_header.append(ts_title)
        ts_card.append(ts_header)

        self.ts_url_label = Gtk.Label()
        self.ts_url_label.set_halign(Gtk.Align.START)
        self.ts_url_label.set_selectable(True)
        ts_card.append(self.ts_url_label)

        btn_copy_ts = Gtk.Button(label="📋 Copiar Enlace Amigos")
        btn_copy_ts.connect("clicked", lambda b: self._copy_to_clipboard(self.ts_url))
        ts_card.append(btn_copy_ts)
        left_box.append(ts_card)

        # Tarjeta Descarga APK Nativo
        apk_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        apk_card.add_css_class("card-box")
        apk_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        apk_header.append(Gtk.Label(label="📱"))
        apk_title = Gtk.Label(label="App Nativa Android (Gatillos de Volumen)")
        apk_title.add_css_class("heading")
        apk_header.append(apk_title)
        apk_card.append(apk_header)

        apk_desc = Gtk.Label(label="Usa los botones físicos de volumen del celular como botones L/R.")
        apk_desc.set_halign(Gtk.Align.START)
        apk_desc.add_css_class("dim-label")
        apk_card.append(apk_desc)

        btn_copy_apk = Gtk.Button(label="📥 Copiar Enlace Descarga APK")
        btn_copy_apk.connect("clicked", lambda b: self._copy_to_clipboard(f"{self.local_url}/PocketController.apk"))
        apk_card.append(btn_copy_apk)
        left_box.append(apk_card)

        # Columna Derecha: Tarjeta con Código QR
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        grid.attach(right_box, 1, 0, 1, 1)

        qr_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        qr_card.add_css_class("card-box")

        qr_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        qr_header.append(Gtk.Label(label="📷"))
        qr_title = Gtk.Label(label="Escanear Código QR")
        qr_title.add_css_class("heading")
        qr_header.append(qr_title)
        qr_card.append(qr_header)

        qr_source_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        qr_source_box.append(Gtk.Label(label="Dirección del QR:"))
        self.qr_network_combo = Gtk.DropDown.new_from_strings(["Red Local Wi-Fi", "Tailscale VPN"])
        self.qr_network_combo.connect("notify::selected", self._on_qr_network_changed)
        qr_source_box.append(self.qr_network_combo)
        qr_card.append(qr_source_box)

        self.qr_picture = Gtk.Picture()
        self.qr_picture.set_can_shrink(True)
        self.qr_picture.set_size_request(240, 240)
        self.qr_picture.set_halign(Gtk.Align.CENTER)
        qr_card.append(self.qr_picture)

        qr_hint = Gtk.Label(label="Apunta la cámara del celular para abrir el mando al instante.")
        qr_hint.set_wrap(True)
        qr_hint.set_justify(Gtk.Justification.CENTER)
        qr_hint.add_css_class("dim-label")
        qr_card.append(qr_hint)

        right_box.append(qr_card)

        self._refresh_network_urls()
        self.view_stack.add_titled(page, "connection", "🌐 Conexión")

    # -------------------------------------------------------------
    # PESTAÑA 3: MANDOS Y JUGADORES (1 A 4)
    # -------------------------------------------------------------
    def _build_tab_players(self):
        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(16)
        content.set_margin_bottom(24)
        page.set_child(content)

        players_intro = Gtk.Label(
            label="Monitorea y prueba en tiempo real los mandos virtuales Xbox 360 conectados a Linux."
        )
        players_intro.set_halign(Gtk.Align.START)
        players_intro.add_css_class("dim-label")
        content.append(players_intro)

        # 4 Tarjetas de Jugadores en Grid 2x2
        grid = Gtk.Grid(column_spacing=16, row_spacing=16)
        grid.set_column_homogeneous(True)
        content.append(grid)

        self.player_widgets = {}

        positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
        for p in range(1, MAX_PLAYERS + 1):
            col, row = positions[p - 1]
            p_card, p_w = self._create_player_card(p)
            self.player_widgets[p] = p_w
            grid.attach(p_card, col, row, 1, 1)

        self.view_stack.add_titled(page, "players", "👥 Jugadores")

    def _create_player_card(self, player_id):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("player-card")

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label=f"🎮 Jugador {player_id}")
        title.add_css_class("heading")
        top_row.append(title)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_row.append(spacer)

        badge = Gtk.Label(label="EN ESPERA")
        badge.add_css_class("status-badge")
        badge.add_css_class("offline")
        top_row.append(badge)

        card.append(top_row)

        info_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ip_label = Gtk.Label(label="Dispositivo: Desconectado")
        ip_label.set_halign(Gtk.Align.START)
        ip_label.add_css_class("dim-label")
        dev_label = Gtk.Label(label=f"Linux: Microsoft X-Box 360 pad (P{player_id})")
        dev_label.set_halign(Gtk.Align.START)
        dev_label.add_css_class("dim-label")
        info_row.append(ip_label)
        info_row.append(dev_label)
        card.append(info_row)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Botones de acción rápida por jugador
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_test = Gtk.Button(label="🎯 Probar")
        btn_test.connect("clicked", lambda b, pid=player_id: self._switch_to_test_player(pid))
        btn_box.append(btn_test)

        btn_reset = Gtk.Button(label="🔄 Reset")
        btn_reset.connect("clicked", lambda b: self.backend.reset_device(player_id))
        btn_box.append(btn_reset)
        card.append(btn_box)

        widgets = {
            "card": card,
            "badge": badge,
            "ip_label": ip_label,
            "dev_label": dev_label
        }
        return card, widgets

    def _switch_to_test_player(self, player_id):
        self.player_selector_combo.set_selected(player_id - 1)
        self.view_stack.set_visible_child_name("full_controller")

    # -------------------------------------------------------------
    # PESTAÑA 4: PERFILES & MARIO KART
    # -------------------------------------------------------------
    def _build_tab_profiles(self):
        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(16)
        content.set_margin_bottom(24)
        page.set_child(content)

        pref_group = Adw.PreferencesGroup()
        pref_group.set_title("Perfiles y Asignaciones Ergonómicas")
        pref_group.set_description("Configuraciones predeterminadas listas para usar con emuladores y juegos nativos.")
        content.append(pref_group)

        row_mk = Adw.ActionRow()
        row_mk.set_title("🏎️ Mario Kart Pro (Switch / Yuzu / Ryujinx)")
        row_mk.set_subtitle("A: Acelerar | B: Freno | R / Vol-: Derrape | L / Vol+: Objetos | Stick Izquierdo")
        btn_mk = Gtk.Button(label="Activar")
        btn_mk.connect("clicked", lambda b: self._notify_profile("Mario Kart Pro"))
        row_mk.add_suffix(btn_mk)
        pref_group.add(row_mk)

        row_xbox = Adw.ActionRow()
        row_xbox.set_title("🎮 Xbox 360 Clásico (Steam / Lutris / GamePass)")
        row_xbox.set_subtitle("Cruceta completa, ABXY, Gatillos analógicos LT/RT, Start/Select y Guía")
        btn_xbox = Gtk.Button(label="Activar")
        btn_xbox.connect("clicked", lambda b: self._notify_profile("Xbox 360 Clásico"))
        row_xbox.add_suffix(btn_xbox)
        pref_group.add(row_xbox)

        row_arc = Adw.ActionRow()
        row_arc.set_title("🕹️ Retro Arcade / Lucha")
        row_arc.set_subtitle("Disposición arcade con botones sobredimensionados")
        btn_arc = Gtk.Button(label="Activar")
        btn_arc.connect("clicked", lambda b: self._notify_profile("Retro Arcade"))
        row_arc.add_suffix(btn_arc)
        pref_group.add(row_arc)

        tools_group = Adw.PreferencesGroup()
        tools_group.set_title("Herramientas del Ecosistema")
        content.append(tools_group)

        row_web = Adw.ActionRow()
        row_web.set_title("🌐 Abrir Interfaz Web en el Navegador")
        row_web.set_subtitle("Permite probar el mando táctil o personalizar layouts en el PC.")
        btn_open = Gtk.Button(label="Abrir")
        btn_open.connect("clicked", lambda b: subprocess.run(["xdg-open", self.local_url]))
        row_web.add_suffix(btn_open)
        tools_group.add(row_web)

        row_dir = Adw.ActionRow()
        row_dir.set_title("📁 Carpeta del Proyecto")
        row_dir.set_subtitle(BASE_DIR)
        btn_dir = Gtk.Button(label="Explorar")
        btn_dir.connect("clicked", lambda b: subprocess.run(["xdg-open", BASE_DIR]))
        row_dir.add_suffix(btn_dir)
        tools_group.add(row_dir)

        self.view_stack.add_titled(page, "profiles", "🏎️ Perfiles")

    # -------------------------------------------------------------
    # PESTAÑA 5: REGISTRO EN VIVO & DIAGNÓSTICO
    # -------------------------------------------------------------
    def _build_tab_logs(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(16)
        page.set_margin_bottom(24)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title = Gtk.Label(label="Consola de Eventos y Diagnóstico")
        title.add_css_class("heading")
        top_bar.append(title)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_bar.append(spacer)

        btn_clear = Gtk.Button(label="🗑️ Limpiar")
        btn_clear.connect("clicked", self._on_clear_logs)
        top_bar.append(btn_clear)

        page.append(top_bar)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.log_text_view = Gtk.TextView()
        self.log_text_view.set_editable(False)
        self.log_text_view.set_cursor_visible(False)
        self.log_text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_text_view.add_css_class("log-view")
        self.log_buffer = self.log_text_view.get_buffer()

        scroller.set_child(self.log_text_view)
        page.append(scroller)

        self.view_stack.add_titled(page, "logs", "📜 Registro")

    # -------------------------------------------------------------
    # CONTROL DE ESTADO Y TELEMETRÍA EN TIEMPO REAL (30 FPS)
    # -------------------------------------------------------------
    def _update_inputs_telemetry(self):
        """Timer de 30 FPS para actualizar visualmente el mando real completo"""
        # 1. Actualizar el Probador de Control Real Completo
        state = self.backend.player_states[self.active_test_player]
        buttons = state.get("buttons", {})

        # Actualizar botones ABXY
        self._set_btn_active(self.btn_a, buttons.get("A", 0))
        self._set_btn_active(self.btn_b, buttons.get("B", 0))
        self._set_btn_active(self.btn_x, buttons.get("X", 0))
        self._set_btn_active(self.btn_y, buttons.get("Y", 0))

        # Actualizar bumpers y centro
        self._set_btn_active(self.btn_lb, buttons.get("L", 0))
        self._set_btn_active(self.btn_rb, buttons.get("R", 0))
        self._set_btn_active(self.btn_back, buttons.get("MINUS", 0))
        self._set_btn_active(self.btn_start, buttons.get("PLUS", 0))
        self._set_btn_active(self.btn_guide, buttons.get("HOME", 0))

        # Actualizar L3 y R3
        self._set_btn_active(self.btn_l3, buttons.get("L3", 0))
        self._set_btn_active(self.btn_r3, buttons.get("R3", 0))

        # Actualizar D-Pad
        hatX = state.get("hatX", 0)
        hatY = state.get("hatY", 0)
        self._set_btn_active(self.btn_dpad_up, hatY < 0)
        self._set_btn_active(self.btn_dpad_down, hatY > 0)
        self._set_btn_active(self.btn_dpad_left, hatX < 0)
        self._set_btn_active(self.btn_dpad_right, hatX > 0)

        # Actualizar gatillos analógicos
        lt_val = state.get("lt_val", 255 if state.get("zl") else 0)
        rt_val = state.get("rt_val", 255 if state.get("zr") else 0)
        self.lt_progress.set_fraction(max(0.0, min(1.0, lt_val / 255.0)))
        self.rt_progress.set_fraction(max(0.0, min(1.0, rt_val / 255.0)))
        self.lt_val_label.set_text(str(lt_val))
        self.rt_val_label.set_text(str(rt_val))

        # Actualizar etiquetas de coordenadas
        lx = state.get("lx", 0)
        ly = state.get("ly", 0)
        rx = state.get("rx", 0)
        ry = state.get("ry", 0)
        self.ls_coord_label.set_text(f"({lx}, {ly})")
        self.rs_coord_label.set_text(f"({rx}, {ry})")

        # Redibujar los DrawingArea de los sticks analógicos
        self.ls_drawing.queue_draw()
        self.rs_drawing.queue_draw()

        return True

    def _set_btn_active(self, widget, is_active):
        if is_active:
            widget.add_css_class("pressed")
        else:
            widget.remove_css_class("pressed")

    def _refresh_network_urls(self):
        ip = get_local_ip()
        ts = get_tailscale_ip()

        self.local_url = f"http://{ip}:{HTTP_PORT_DEFAULT}"
        self.local_url_label.set_text(self.local_url)

        if ts:
            self.ts_url = f"http://{ts}:{HTTP_PORT_DEFAULT}"
            self.ts_url_label.set_text(self.ts_url)
        else:
            self.ts_url = self.local_url
            self.ts_url_label.set_text("Tailscale inactivo o desconectado")

        self._regenerate_qr()

    def _regenerate_qr(self):
        selected = self.qr_network_combo.get_selected()
        target_url = self.local_url if selected == 0 else self.ts_url

        try:
            subprocess.run(
                ["qrencode", "-o", self.qr_temp_path, "-s", "6", "-m", "2", target_url],
                check=True,
                capture_output=True
            )
            self.qr_picture.set_filename(self.qr_temp_path)
        except Exception as ex:
            print(f"Error generando QR: {ex}")

    def _on_qr_network_changed(self, widget, pspec):
        self._regenerate_qr()

    def _copy_to_clipboard(self, text):
        display = Gdk.Display.get_default()
        if display:
            clipboard = display.get_clipboard()
            clipboard.set(text)
            self.backend.log(f"📋 Copiado al portapapeles: {text}")

    def _notify_profile(self, name):
        self.backend.log(f"🏎️ Perfil seleccionado: {name}")

    def _on_toggle_server_clicked(self, button):
        if self.backend.is_running:
            self.backend.stop()
        else:
            self.backend.start()

    def _start_server(self):
        if not self.backend.is_running:
            self.backend.start()

    def _on_backend_status_change(self, running):
        GLib.idle_add(self._update_server_status_ui, running)

    def _update_server_status_ui(self, running):
        if running:
            self.header_status_badge.set_text("ACTIVO")
            self.header_status_badge.remove_css_class("offline")
            self.header_status_badge.add_css_class("online")

            self.server_toggle_btn.set_label("Detener")
            self.server_toggle_btn.remove_css_class("suggested-action")
            self.server_toggle_btn.add_css_class("destructive-action")
            self._refresh_network_urls()
        else:
            self.header_status_badge.set_text("DETENIDO")
            self.header_status_badge.remove_css_class("online")
            self.header_status_badge.add_css_class("offline")

            self.server_toggle_btn.set_label("Iniciar")
            self.server_toggle_btn.remove_css_class("destructive-action")
            self.server_toggle_btn.add_css_class("suggested-action")

    def _on_backend_player_connect(self, player_id, client_ip):
        GLib.idle_add(self._update_player_connect_ui, player_id, client_ip)

    def _update_player_connect_ui(self, player_id, client_ip):
        w = self.player_widgets.get(player_id)
        if w:
            w["badge"].set_text("CONECTADO")
            w["badge"].remove_css_class("offline")
            w["badge"].add_css_class("online")
            w["ip_label"].set_text(f"Dispositivo: {client_ip}")
            w["card"].add_css_class("active")

    def _on_backend_player_disconnect(self, player_id):
        GLib.idle_add(self._update_player_disconnect_ui, player_id)

    def _update_player_disconnect_ui(self, player_id):
        w = self.player_widgets.get(player_id)
        if w:
            w["badge"].set_text("EN ESPERA")
            w["badge"].remove_css_class("online")
            w["badge"].add_css_class("offline")
            w["ip_label"].set_text("Dispositivo: Desconectado")
            w["card"].remove_css_class("active")

    def _on_backend_log(self, formatted_msg):
        GLib.idle_add(self._append_log_ui, formatted_msg)

    def _append_log_ui(self, msg):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, msg + "\n")
        mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
        self.log_text_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _on_clear_logs(self, button):
        self.log_buffer.set_text("")


class PocketControllerApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=0
        )

    def do_startup(self):
        Adw.Application.do_startup(self)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CSS_STYLES.encode('utf-8'))
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = PocketControllerWindow(application=self)
        win.present()

    def do_shutdown(self):
        win = self.props.active_window
        if win and hasattr(win, 'backend'):
            win.backend.stop()
        Adw.Application.do_shutdown(self)


def main():
    app = PocketControllerApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
