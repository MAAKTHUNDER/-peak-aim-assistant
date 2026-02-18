import sys
import json
import os
import time
import webbrowser
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QCheckBox, QSystemTrayIcon, QMenu, QAction,
                             QMessageBox, QComboBox, QDialog, QSlider,
                             QSizePolicy, QSpinBox)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSharedMemory
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor, QPixmap, QCursor
import keyboard
from pynput.mouse import Button, Listener as MouseListener

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ON_COMMANDS  = ['turn on', 'activate', 'active', 'enable', 'start', ' on ']
OFF_COMMANDS = ['turn off', 'deactivate', 'inactive', 'disable', 'stop', ' off ']

MACRO_HOTKEYS = [
    'F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11','F12',
    '1','2','3','4','5','6','7','8','9','0',
    'A','B','C','D','E','F','G','H','I','J','K','L','M',
    'N','O','P','Q','R','S','T','U','V','W','X','Y','Z',
    'Shift','Ctrl','Alt','CapsLock','Tab','Esc','Backspace','Enter',
    'Up','Down','Left','Right','Home','End','PageUp','PageDown',
    'Insert','Delete','Space','Pause',
    'Num0','Num1','Num2','Num3','Num4','Num5','Num6','Num7','Num8','Num9',
    'NumLock','Num/','Num*','Num-','Num+','NumEnter','NumDel',
    '-','=','[',']',';',"'",'`',',','.','/','\\',' ScrollLock'
]

AIM_BUTTONS = [
    'A','B','C','D','E','F','G','H','I','J','K','L','M',
    'N','O','P','Q','R','S','T','U','V','W','X','Y','Z',
    '1','2','3','4','5','6','7','8','9','0',
    'Space','Shift','Ctrl','Alt','Tab','Enter','CapsLock',
    'Up','Down','Left','Right',
    'Num0','Num1','Num2','Num3','Num4','Num5','Num6','Num7','Num8','Num9',
    '-','=','[',']',';',"'",'`',',','.','/','\\',' ',
    'Left Click','Right Click','Middle Click'
]

def get_microphone_list():
    mic_list = ['Default']
    try:
        if SPEECH_AVAILABLE:
            import pyaudio
            p = pyaudio.PyAudio()
            seen = set()
            for i in range(p.get_device_count()):
                try:
                    device = p.get_device_info_by_index(i)
                    if device['maxInputChannels'] < 1:
                        continue
                    name = device['name'].strip()
                    name_lower = name.lower()
                    if any(x in name_lower for x in [
                        'output','loopback','stereo mix','what u hear',
                        'wave out','speaker','hdmi output','display audio',
                        'digital output','spdif output','playback'
                    ]):
                        continue
                    if name_lower in seen:
                        continue
                    seen.add(name_lower)
                    mic_list.append(f"{i}: {name[:50].strip()}")
                except Exception:
                    continue
            p.terminate()
    except Exception:
        pass
    return mic_list


# ── Voice Thread ───────────────────────────────────────────────────────────────
class VoiceThread(QThread):
    command_received = pyqtSignal(str)
    status_update    = pyqtSignal(str)

    def __init__(self, mic_index=None, energy_threshold=1500):
        super().__init__()
        self.running          = False
        self.enabled          = False
        self.recognizer       = None
        self.microphone       = None
        self.mic_index        = mic_index
        self.energy_threshold = energy_threshold

    def initialize(self):
        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold        = self.energy_threshold
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.pause_threshold          = 0.2   # faster end-of-speech detection
            self.recognizer.non_speaking_duration    = 0.1   # quicker silence cutoff
            self.microphone = (
                sr.Microphone(device_index=self.mic_index)
                if self.mic_index is not None else sr.Microphone()
            )
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            return True
        except Exception as e:
            self.status_update.emit(f"Mic Error: {str(e)[:40]}")
            return False

    def run(self):
        if not SPEECH_AVAILABLE:
            self.status_update.emit("Not installed!")
            return
        if not self.initialize():
            return
        self.status_update.emit("Listening...")
        self.running = True
        while self.running:
            try:
                if not self.enabled:
                    time.sleep(0.2)
                    continue
                with self.microphone as source:
                    try:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=1.5)
                    except sr.WaitTimeoutError:
                        continue
                try:
                    text = ' ' + self.recognizer.recognize_google(audio).lower().strip() + ' '
                    self.status_update.emit(f"Heard: {text.strip()}")
                    matched = False
                    for cmd in OFF_COMMANDS:
                        if cmd in text:
                            self.command_received.emit('off')
                            matched = True
                            break
                    if not matched:
                        for cmd in ON_COMMANDS:
                            if cmd in text:
                                self.command_received.emit('on')
                                break
                    # No sleep — resume listening immediately for fast on/off switching
                    if self.running and self.enabled:
                        self.status_update.emit("Listening...")
                except sr.UnknownValueError:
                    self.status_update.emit("Listening...")
                except sr.RequestError:
                    self.status_update.emit("No internet!")
                    time.sleep(2)
                    self.status_update.emit("Listening...")
            except Exception:
                time.sleep(0.5)

    def stop(self):
        self.running = False
        self.enabled = False


# ── Overlay ────────────────────────────────────────────────────────────────────
class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint |
            Qt.Tool | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        layout = QHBoxLayout()
        self.label = QLabel("● INACTIVE | Scope: CLOSED")
        self.label.setFont(QFont("Consolas", 10, QFont.Bold))
        self.update_status(False, False, True)
        layout.addWidget(self.label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def update_status(self, active, scope_open, show_bg):
        color  = "#00FF00" if active else "#FF0000"
        status = "ACTIVE"  if active else "INACTIVE"
        scope  = "OPEN"    if scope_open else "CLOSED"
        bg     = "rgba(0,0,0,180)" if show_bg else "transparent"
        self.label.setStyleSheet(f"color:{color}; background-color:{bg}; padding:5px;")
        self.label.setText(f"● {status} | Scope: {scope}")
        self.adjustSize()


# ── Macro Thread ───────────────────────────────────────────────────────────────
class MacroThread(QThread):
    status_update = pyqtSignal(bool, bool)

    def __init__(self, aim_button='o'):
        super().__init__()
        self.enabled               = False
        self.scope_toggled         = False
        self.aim_held              = False
        self.right_click_time      = 0
        self.last_right_click_activity = 0
        self.running               = True
        self.right_click_pressed   = False
        self.aim_button            = aim_button.lower()

    def set_aim_button(self, button):
        self.aim_button = button.lower()

    def run(self):
        def on_click(x, y, button, pressed):
            if button == Button.right:
                if pressed:
                    self.right_click_time          = time.time()
                    self.last_right_click_activity = time.time()
                    self.right_click_pressed       = True
                else:
                    self.right_click_pressed = False
                    if (time.time() - self.right_click_time) * 1000 < 300:
                        self.scope_toggled = not self.scope_toggled
                        self.last_right_click_activity = time.time()

        mouse_listener = MouseListener(on_click=on_click)
        mouse_listener.start()

        while self.running:
            try:
                if self.scope_toggled:
                    if (time.time() - self.last_right_click_activity) > 30.0:
                        self.scope_toggled = False

                if self.enabled:
                    e_pressed    = keyboard.is_pressed('e')
                    q_pressed    = keyboard.is_pressed('q')
                    scope_active = self.scope_toggled or self.right_click_pressed
                    should_hold  = (e_pressed or q_pressed) and not scope_active

                    if should_hold and not self.aim_held:
                        try:
                            keyboard.press(self.aim_button)
                            self.aim_held = True
                        except Exception:
                            self.aim_held = False
                    elif not should_hold and self.aim_held:
                        try:
                            keyboard.release(self.aim_button)
                            self.aim_held = False
                        except Exception:
                            self.aim_held = False
                    self.status_update.emit(True, scope_active)
                else:
                    if self.aim_held:
                        try:
                            keyboard.release(self.aim_button)
                            self.aim_held = False
                        except Exception:
                            self.aim_held = False
                    self.status_update.emit(False, self.scope_toggled)

                time.sleep(0.05 if self.enabled else 0.2)
            except Exception:
                if self.aim_held:
                    try:
                        keyboard.release(self.aim_button)
                    except Exception:
                        pass
                    self.aim_held = False
                time.sleep(0.1)

    def stop(self):
        self.running = False
        if self.aim_held:
            try:
                keyboard.release(self.aim_button)
            except Exception:
                pass


# ── ComboBox style ─────────────────────────────────────────────────────────────
COMBO_STYLE = """
QComboBox {
    background-color: #2a2a2a;
    color: white;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 28px;
    font-size: 10pt;
}
QComboBox QAbstractItemView {
    background-color: #2a2a2a;
    color: white;
    selection-background-color: #00BFFF;
    border: 1px solid #555555;
    min-width: 380px;
}
QComboBox::drop-down { border: none; width: 24px; }
"""


# ── Settings Dialog — fixed size, no scrollbar ─────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, parent, current_hotkey, current_aim,
                 voice_enabled, current_mic, voice_status_text,
                 energy_threshold=1500):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        # Wide enough that dropdown popup won't overflow; tall enough for all content
        self.setFixedSize(480, 570)
        self.parent_window = parent

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)

        layout = QVBoxLayout(self)
        layout.setSpacing(7)
        layout.setContentsMargins(20, 12, 20, 12)

        # Title
        title = QLabel("⚙ Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addWidget(self._sep())

        # Macro Hotkey
        layout.addWidget(self._lbl("Macro Hotkey:"))
        self.hotkey_combo = QComboBox()
        self.hotkey_combo.addItems(MACRO_HOTKEYS)
        self.hotkey_combo.setCurrentText(current_hotkey)
        self.hotkey_combo.setMaxVisibleItems(12)
        self.hotkey_combo.setStyleSheet(COMBO_STYLE)
        self.hotkey_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.hotkey_combo)

        # Aim Button
        layout.addWidget(self._lbl("Aim Button:"))
        self.aim_combo = QComboBox()
        self.aim_combo.addItems(AIM_BUTTONS)
        self.aim_combo.setCurrentText(current_aim)
        self.aim_combo.setMaxVisibleItems(12)
        self.aim_combo.setStyleSheet(COMBO_STYLE)
        self.aim_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.aim_combo)

        layout.addWidget(self._sep())

        # Voice Control header
        vc_lbl = QLabel("🎤 Voice Control:")
        vc_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 11pt;")
        layout.addWidget(vc_lbl)

        self.voice_check = QCheckBox("Enable Voice Commands")
        self.voice_check.setStyleSheet("color: white; font-size: 10pt;")
        self.voice_check.setChecked(voice_enabled)
        self.voice_check.stateChanged.connect(self.on_voice_toggled)
        layout.addWidget(self.voice_check)

        # Microphone
        layout.addWidget(self._lbl("Microphone:"))
        self.mic_combo = QComboBox()
        self.mic_list  = get_microphone_list()
        self.mic_combo.addItems(self.mic_list)
        if current_mic in self.mic_list:
            self.mic_combo.setCurrentText(current_mic)
        else:
            self.mic_combo.setCurrentIndex(0)
        self.mic_combo.setMaxVisibleItems(8)
        self.mic_combo.setStyleSheet(COMBO_STYLE)
        self.mic_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.mic_combo)

        # Sensitivity
        layout.addWidget(self._lbl("Sensitivity (0 – 4000):"))

        slider_row = QHBoxLayout()
        q_lbl = QLabel("Quiet")
        q_lbl.setStyleSheet("color: #888888; font-size: 8pt;")
        slider_row.addWidget(q_lbl)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(4000)
        self.slider.setValue(energy_threshold)
        self.slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { background:#444444; height:6px; border-radius:3px; }
            QSlider::handle:horizontal {
                background:#00BFFF; width:16px; height:16px;
                margin:-5px 0; border-radius:8px;
            }
            QSlider::sub-page:horizontal { background:#00BFFF; border-radius:3px; }
        """)
        slider_row.addWidget(self.slider)

        l_lbl = QLabel("Loud")
        l_lbl.setStyleSheet("color: #888888; font-size: 8pt;")
        slider_row.addWidget(l_lbl)
        layout.addLayout(slider_row)

        # Editable value spinbox
        spin_row = QHBoxLayout()
        val_lbl = QLabel("Value:")
        val_lbl.setStyleSheet("color: #CCCCCC;")
        spin_row.addWidget(val_lbl)
        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(0)
        self.spinbox.setMaximum(4000)
        self.spinbox.setValue(energy_threshold)
        self.spinbox.setFixedWidth(110)
        self.spinbox.setStyleSheet("""
            QSpinBox {
                background:#2a2a2a; color:#00BFFF;
                border:1px solid #555555; border-radius:4px;
                padding:3px 6px; font-size:10pt;
            }
        """)
        spin_row.addWidget(self.spinbox)
        spin_row.addStretch()
        layout.addLayout(spin_row)

        # Sync slider ↔ spinbox
        self.slider.valueChanged.connect(self.spinbox.setValue)
        self.spinbox.valueChanged.connect(self.slider.setValue)

        # Voice status + hint
        color = "#00FF00" if "Listening" in voice_status_text else "#888888"
        self.voice_status = QLabel(f"🎤 {voice_status_text}")
        self.voice_status.setStyleSheet(f"color:{color}; font-size:9pt;")
        layout.addWidget(self.voice_status)

        hint = QLabel('Commands: "On" / "Active" / "Activate" / "Enable"\n'
                      '                  "Off" / "Inactive" / "Deactivate" / "Disable"')
        hint.setStyleSheet("color:#888888; font-size:8pt;")
        layout.addWidget(hint)

        layout.addStretch()
        layout.addWidget(self._sep())

        # Buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("✔ Apply & Save")
        save_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        save_btn.setFixedHeight(38)
        save_btn.setStyleSheet("""
            QPushButton { background:#00BFFF; color:black; border-radius:5px; border:none; }
            QPushButton:hover { background:#33CCFF; }
        """)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        close_btn = QPushButton("✖ Close")
        close_btn.setFixedHeight(38)
        close_btn.setStyleSheet("""
            QPushButton { background:#444444; color:white; border-radius:5px; border:none; }
            QPushButton:hover { background:#555555; }
        """)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _sep(self):
        lbl = QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lbl.setStyleSheet("color: #444444;")
        return lbl

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet("color: #CCCCCC; font-size: 9pt;")
        return l

    def on_voice_toggled(self):
        enabled    = self.voice_check.isChecked()
        mic_index  = self.mic_combo.currentIndex()
        actual_idx = mic_index - 1 if mic_index > 0 else None
        if enabled:
            self.voice_status.setText("🎤 Starting...")
            self.voice_status.setStyleSheet("color:#FF8800; font-size:9pt;")
            self.parent_window.start_voice(actual_idx, self.spinbox.value())
        else:
            self.voice_status.setText("🎤 Disabled")
            self.voice_status.setStyleSheet("color:#888888; font-size:9pt;")
            self.parent_window.stop_voice()

    def update_voice_status(self, status):
        self.voice_status.setText(f"🎤 {status}")
        if "Listening" in status:
            color = "#00FF00"
        elif "Error" in status or "not" in status.lower() or "No internet" in status:
            color = "#FF0000"
        elif "Heard" in status:
            color = "#00BFFF"
        else:
            color = "#888888"
        self.voice_status.setStyleSheet(f"color:{color}; font-size:9pt;")

    def get_values(self):
        mic_index  = self.mic_combo.currentIndex()
        actual_idx = mic_index - 1 if mic_index > 0 else None
        return (
            self.hotkey_combo.currentText(),
            self.aim_combo.currentText(),
            self.voice_check.isChecked(),
            self.mic_combo.currentText(),
            actual_idx,
            self.spinbox.value()
        )


# ── Clickable link label ───────────────────────────────────────────────────────
class ClickableLabel(QLabel):
    def __init__(self, text, url, parent=None):
        super().__init__(text, parent)
        self.url = url
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def mousePressEvent(self, event):
        webbrowser.open(self.url)


# ── Main Window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_file   = "settings.json"
        self.current_hotkey  = None
        self.voice_thread    = None
        self.settings_dialog = None
        self.load_settings()

        self.macro_thread = MacroThread(self.aim_button)
        self.macro_thread.status_update.connect(self.update_overlay_status)
        self.macro_thread.start()

        self.init_ui()
        self.setup_tray()
        self.setup_overlay()
        self.register_hotkey(self.macro_hotkey)

        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self.watchdog_check)
        self.watchdog_timer.start(2000)

        self.set_window_icon()

        if self.voice_enabled:
            self.start_voice(self.mic_index, self.energy_threshold)

    def set_window_icon(self):
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            px = QPixmap(32, 32)
            px.fill(QColor(0, 255, 0))
            self.setWindowIcon(QIcon(px))

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    s = json.load(f)
                self.overlay_x        = s.get('overlay_x', 1600)
                self.overlay_y        = s.get('overlay_y', 50)
                self.overlay_bg       = s.get('overlay_bg', True)
                self.start_minimized  = s.get('start_minimized', False)
                self.macro_hotkey     = s.get('macro_hotkey', 'F8')
                self.aim_button       = s.get('aim_button', 'O')
                self.voice_enabled    = s.get('voice_enabled', False)
                self.mic_name         = s.get('mic_name', 'Default')
                self.mic_index        = s.get('mic_index', None)
                self.energy_threshold = s.get('energy_threshold', 1500)
                self.is_first_run     = False
            else:
                self.set_defaults()
                self.is_first_run = True
        except Exception:
            self.set_defaults()
            self.is_first_run = True

    def set_defaults(self):
        self.overlay_x        = 1600
        self.overlay_y        = 50
        self.overlay_bg       = True
        self.start_minimized  = False
        self.macro_hotkey     = 'F8'
        self.aim_button       = 'O'
        self.voice_enabled    = False
        self.mic_name         = 'Default'
        self.mic_index        = None
        self.energy_threshold = 1500

    def save_settings(self):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump({
                    'overlay_x': self.overlay_x, 'overlay_y': self.overlay_y,
                    'overlay_bg': self.overlay_bg, 'start_minimized': self.start_minimized,
                    'macro_hotkey': self.macro_hotkey, 'aim_button': self.aim_button,
                    'voice_enabled': self.voice_enabled, 'mic_name': self.mic_name,
                    'mic_index': self.mic_index, 'energy_threshold': self.energy_threshold
                }, f)
        except Exception:
            pass

    def register_hotkey(self, key):
        try:
            if self.current_hotkey:
                keyboard.remove_hotkey(self.current_hotkey)
        except Exception:
            pass
        try:
            self.current_hotkey = keyboard.add_hotkey(key.lower(), self.toggle_macro)
        except Exception:
            pass

    def start_voice(self, mic_index=None, energy_threshold=1500):
        if not SPEECH_AVAILABLE:
            return
        if self.voice_thread and self.voice_thread.isRunning():
            self.voice_thread.stop()
            self.voice_thread.wait()
        self.voice_thread = VoiceThread(mic_index=mic_index, energy_threshold=energy_threshold)
        self.voice_thread.command_received.connect(self.on_voice_command)
        self.voice_thread.status_update.connect(self.on_voice_status)
        self.voice_thread.enabled = True
        self.voice_thread.start()

    def stop_voice(self):
        if self.voice_thread:
            self.voice_thread.stop()
        self.voice_label.setText("🎤 Voice: Disabled")
        self.voice_label.setStyleSheet("color: #888888; font-size: 8pt;")

    def on_voice_command(self, command):
        if command == 'on' and not self.macro_thread.enabled:
            self.macro_thread.enabled = True
        elif command == 'off' and self.macro_thread.enabled:
            self.macro_thread.enabled = False

    def on_voice_status(self, status):
        if "Listening" in status:
            self.voice_label.setText("🎤 Voice: Listening...")
            self.voice_label.setStyleSheet("color: #00FF00; font-size: 8pt;")
        elif "Heard" in status:
            self.voice_label.setText(f"🎤 {status}")
            self.voice_label.setStyleSheet("color: #00BFFF; font-size: 8pt;")
        elif "Error" in status or "not" in status.lower():
            self.voice_label.setText(f"🎤 {status}")
            self.voice_label.setStyleSheet("color: #FF0000; font-size: 8pt;")
        else:
            self.voice_label.setText(f"🎤 {status}")
            self.voice_label.setStyleSheet("color: #FF8800; font-size: 8pt;")
        if self.settings_dialog:
            self.settings_dialog.update_voice_status(status)

    def show_settings(self):
        voice_status = (
            "Listening..."
            if (self.voice_thread and self.voice_thread.isRunning() and self.voice_thread.enabled)
            else "Disabled"
        )
        self.settings_dialog = SettingsDialog(
            self, self.macro_hotkey, self.aim_button,
            self.voice_enabled, self.mic_name, voice_status,
            self.energy_threshold
        )
        if self.settings_dialog.exec_() == QDialog.Accepted:
            new_hotkey, new_aim, new_voice, new_mic_name, new_mic_index, new_threshold = \
                self.settings_dialog.get_values()

            if new_hotkey != self.macro_hotkey:
                self.macro_hotkey = new_hotkey
                self.register_hotkey(new_hotkey)
                self.toggle_btn.setText(f"Toggle Macro ({new_hotkey})")

            if new_aim != self.aim_button:
                self.aim_button = new_aim
                self.macro_thread.set_aim_button(new_aim)

            self.voice_enabled    = new_voice
            self.mic_name         = new_mic_name
            self.mic_index        = new_mic_index
            self.energy_threshold = new_threshold

            if new_voice:
                self.start_voice(new_mic_index, new_threshold)
            else:
                self.stop_voice()

            self.save_settings()
            QMessageBox.information(self, "Success", "Settings saved successfully!")

        self.settings_dialog = None

    # ── UI — original style restored exactly ──────────────────────────────────
    def init_ui(self):
        self.setWindowTitle("Peak & Aim Assistant v1.0")
        self.setFixedSize(400, 680)

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 5, 12, 10)

        # Title — exactly as original
        title_container = QHBoxLayout()
        title_container.addStretch()
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            logo_pixmap = QPixmap(logo_path)
            logo_label.setPixmap(logo_pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            title_container.addWidget(logo_label)
        title_text_layout = QVBoxLayout()
        title_text_layout.setSpacing(0)
        title = QLabel("Peak & Aim Assistant")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: white;")
        title_text_layout.addWidget(title)
        title_container.addLayout(title_text_layout)
        title_container.addStretch()
        layout.addLayout(title_container)

        creator = QLabel("Created by MAAKTHUNDER")
        creator.setFont(QFont("Segoe UI", 9))
        creator.setStyleSheet("color: #AAAAAA;")
        creator.setAlignment(Qt.AlignCenter)
        layout.addWidget(creator)

        layout.addWidget(self._sep())

        # Status
        status_layout = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Segoe UI", 14))
        self.status_dot.setStyleSheet("color: #FF0000;")
        self.status_text = QLabel("INACTIVE")
        self.status_text.setFont(QFont("Segoe UI", 10))
        self.status_text.setStyleSheet("color: #FF0000;")
        status_layout.addStretch()
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        layout.addWidget(self._sep())

        # Buttons
        self.toggle_btn = QPushButton(f"Toggle Macro ({self.macro_hotkey})")
        self.toggle_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.toggle_btn.setFixedHeight(40)
        self.toggle_btn.clicked.connect(self.toggle_macro)
        layout.addWidget(self.toggle_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        settings_btn.setFixedHeight(40)
        settings_btn.clicked.connect(self.show_settings)
        layout.addWidget(settings_btn)

        layout.addWidget(self._sep())

        # Overlay position
        pos_label = QLabel("Overlay Position:")
        pos_label.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(pos_label)

        pos_layout = QHBoxLayout()
        x_label = QLabel("X:")
        x_label.setStyleSheet("color: white;")
        pos_layout.addWidget(x_label)
        self.x_input = QLineEdit(str(self.overlay_x))
        self.x_input.setFixedWidth(80)
        pos_layout.addWidget(self.x_input)
        y_label = QLabel("Y:")
        y_label.setStyleSheet("color: white;")
        pos_layout.addWidget(y_label)
        self.y_input = QLineEdit(str(self.overlay_y))
        self.y_input.setFixedWidth(80)
        pos_layout.addWidget(self.y_input)
        apply_btn = QPushButton("Apply & Save")
        apply_btn.clicked.connect(self.apply_position)
        pos_layout.addWidget(apply_btn)
        layout.addLayout(pos_layout)

        self.bg_check = QCheckBox("Show Background (Semi-transparent)")
        self.bg_check.setStyleSheet("color: white;")
        self.bg_check.setChecked(self.overlay_bg)
        self.bg_check.stateChanged.connect(self.toggle_background)
        layout.addWidget(self.bg_check)

        self.minimize_check = QCheckBox("Start Minimized to Tray")
        self.minimize_check.setStyleSheet("color: white;")
        self.minimize_check.setChecked(self.start_minimized)
        self.minimize_check.stateChanged.connect(self.toggle_minimize)
        layout.addWidget(self.minimize_check)

        self.voice_label = QLabel("🎤 Voice: Disabled")
        self.voice_label.setStyleSheet("color: #888888; font-size: 8pt;")
        layout.addWidget(self.voice_label)

        tip_label = QLabel("Tip: Scope auto-resets after 30s inactivity")
        tip_label.setStyleSheet("color: #00FF00; font-size: 8pt;")
        layout.addWidget(tip_label)

        layout.addWidget(self._sep())

        # How it Works
        how_label = QLabel("How it Works:")
        how_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(how_label)

        hotkey_text = QLabel(f"{self.macro_hotkey} - Toggle Macro ON/OFF (Default)")
        hotkey_text.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(hotkey_text)

        layout.addWidget(QLabel(""))

        peak_text = QLabel("Q/E - Peak with Auto-Aim")
        peak_text.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(peak_text)

        layout.addWidget(self._sep())

        # Social links
        youtube_layout = QHBoxLayout()
        youtube_layout.setSpacing(10)
        yt_icon_path = resource_path("youtube.png")
        if os.path.exists(yt_icon_path):
            yt_icon = QLabel()
            yt_pixmap = QPixmap(yt_icon_path)
            yt_icon.setPixmap(yt_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            youtube_layout.addWidget(yt_icon)
        yt_link = ClickableLabel("WWW.YOUTUBE.COM/@MAAKTHUNDER", "https://www.youtube.com/@MAAKTHUNDER")
        yt_link.setFont(QFont("Segoe UI", 10))
        yt_link.setStyleSheet("color: #00BFFF; text-decoration: underline;")
        youtube_layout.addWidget(yt_link)
        youtube_layout.addStretch()
        layout.addLayout(youtube_layout)

        tiktok_layout = QHBoxLayout()
        tiktok_layout.setSpacing(10)
        tt_icon_path = resource_path("tiktok.png")
        if os.path.exists(tt_icon_path):
            tt_icon = QLabel()
            tt_pixmap = QPixmap(tt_icon_path)
            tt_icon.setPixmap(tt_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            tiktok_layout.addWidget(tt_icon)
        tt_link = ClickableLabel("WWW.TIKTOK.COM/@MAAKTHUNDER", "https://www.tiktok.com/@maakthunder")
        tt_link.setFont(QFont("Segoe UI", 10))
        tt_link.setStyleSheet("color: #00BFFF; text-decoration: underline;")
        tiktok_layout.addWidget(tt_link)
        tiktok_layout.addStretch()
        layout.addLayout(tiktok_layout)

        layout.addWidget(self._sep())

        footer = QLabel("Made for GameLoop | v1.0")
        footer.setStyleSheet("color: #888888;")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        central_widget.setLayout(layout)

        if self.is_first_run or not self.start_minimized:
            self.show()
        else:
            self.hide()

    def _sep(self):
        """Original white ━━━ separator — exactly as in original code."""
        lbl = QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lbl.setStyleSheet("color: white;")
        return lbl

    # ── Tray ──────────────────────────────────────────────────────────────────
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Peak & Aim Assistant - MAAKTHUNDER")
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            px = QPixmap(16, 16)
            px.fill(QColor(0, 255, 0))
            self.tray_icon.setIcon(QIcon(px))
        tray_menu = QMenu()
        show_action = QAction("Show GUI", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        toggle_action = QAction(f"Toggle Macro ({self.macro_hotkey})", self)
        toggle_action.triggered.connect(self.toggle_macro)
        tray_menu.addAction(toggle_action)
        tray_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_clicked)
        self.tray_icon.show()

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()

    # ── Overlay ───────────────────────────────────────────────────────────────
    def setup_overlay(self):
        self.overlay = OverlayWindow()
        self.overlay.move(self.overlay_x, self.overlay_y)
        self.overlay.update_status(False, False, self.overlay_bg)
        self.overlay.show()
        self.overlay_timer = QTimer()
        self.overlay_timer.timeout.connect(self.update_overlay_display)
        self.overlay_timer.start(300)

    def update_overlay_display(self):
        pass

    def update_overlay_status(self, active, scope_open):
        self.overlay.update_status(active, scope_open, self.overlay_bg)
        color = "#00FF00" if active else "#FF0000"
        text  = "ACTIVE"  if active else "INACTIVE"
        self.status_dot.setStyleSheet(f"color: {color};")
        self.status_text.setStyleSheet(f"color: {color};")
        self.status_text.setText(text)

    def toggle_macro(self):
        self.macro_thread.enabled = not self.macro_thread.enabled

    def apply_position(self):
        try:
            self.overlay_x = int(self.x_input.text())
            self.overlay_y = int(self.y_input.text())
            self.overlay.move(self.overlay_x, self.overlay_y)
            self.save_settings()
            QMessageBox.information(self, "Success",
                f"Position saved: X={self.overlay_x}, Y={self.overlay_y}")
        except Exception:
            QMessageBox.warning(self, "Error", "Invalid position values!")

    def toggle_background(self):
        self.overlay_bg = self.bg_check.isChecked()
        self.save_settings()

    def toggle_minimize(self):
        self.start_minimized = self.minimize_check.isChecked()
        self.save_settings()

    def watchdog_check(self):
        if self.macro_thread.aim_held:
            if not keyboard.is_pressed('e') and not keyboard.is_pressed('q'):
                try:
                    keyboard.release(self.macro_thread.aim_button)
                    self.macro_thread.aim_held = False
                except Exception:
                    pass

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def quit_app(self):
        if self.voice_thread:
            self.voice_thread.stop()
            self.voice_thread.wait()
        self.macro_thread.stop()
        self.macro_thread.wait()
        QApplication.quit()


# ── Entry ──────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    shared_mem = QSharedMemory("PeakAimAssistantUniqueName")
    if not shared_mem.create(1):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Already Running")
        msg.setText("Peak & Aim Assistant is already running!")
        msg.setInformativeText("Check your system tray.")
        msg.exec_()
        sys.exit(0)
    window = MainWindow()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
