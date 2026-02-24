import sys
import json
import os
import time
import webbrowser
import zipfile
import urllib.request
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QCheckBox, QSystemTrayIcon, QMenu, QAction,
                             QMessageBox, QComboBox, QDialog)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSharedMemory
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor, QPixmap, QCursor, QPainter, QLinearGradient, QBrush, QPen
import keyboard
from pynput.mouse import Button, Listener as MouseListener

try:
    from vosk import Model, KaldiRecognizer
    import pyaudio
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

MACRO_HOTKEYS = [
    'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
    'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    'Shift', 'Ctrl', 'Alt', 'CapsLock', 'Tab', 'Esc', 'Backspace', 'Enter',
    'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'PageUp', 'PageDown',
    'Insert', 'Delete', 'Space', 'Pause',
    'Num0', 'Num1', 'Num2', 'Num3', 'Num4', 'Num5', 'Num6', 'Num7', 'Num8', 'Num9',
    'NumLock', 'Num/', 'Num*', 'Num-', 'Num+', 'NumEnter', 'NumDel',
    '-', '=', '[', ']', ';', "'", '`', ',', '.', '/', '\\', 'ScrollLock'
]

AIM_BUTTONS = [
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
    'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
    'Space', 'Shift', 'Ctrl', 'Alt', 'Tab', 'Enter', 'CapsLock',
    'Up', 'Down', 'Left', 'Right',
    'Num0', 'Num1', 'Num2', 'Num3', 'Num4', 'Num5', 'Num6', 'Num7', 'Num8', 'Num9',
    '-', '=', '[', ']', ';', "'", '`', ',', '.', '/', '\\',
    'Left Click', 'Right Click', 'Middle Click'
]

def get_microphone_list():
    mic_list = ['Default']
    try:
        if VOSK_AVAILABLE:
            import pyaudio
            p = pyaudio.PyAudio()
            for i in range(p.get_device_count()):
                try:
                    device = p.get_device_info_by_index(i)
                    if device['maxInputChannels'] > 0:
                        name = device['name'][:40].strip()
                        if name:
                            mic_list.append(f"{i}: {name}")
                except:
                    continue
            p.terminate()
    except:
        pass
    return mic_list

def download_vosk_model():
    model_name = "vosk-model-small-en-us-0.15"
    bundled_path = resource_path(model_name)
    if os.path.exists(bundled_path):
        return bundled_path
    if os.path.exists(model_name):
        return model_name
    model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    zip_path = "vosk-model.zip"
    try:
        print("Downloading Vosk model...")
        urllib.request.urlretrieve(model_url, zip_path)
        print("Extracting model...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(".")
        os.remove(zip_path)
        print("Model ready!")
        return model_name
    except Exception as e:
        print(f"Model download failed: {e}")
        return None

# ─────────────────────────────────────────────────────────
#  Colour palette  (only edit this section for re-theming)
# ─────────────────────────────────────────────────────────
C_BG      = "#030A14"
C_BG2     = "#060F1E"
C_BG3     = "#040C18"
C_BORDER  = "#0D2240"
C_BORDER2 = "#1A3A5C"
C_CYAN    = "#00CFFF"
C_BLUE    = "#0077FF"
C_GREEN   = "#00FF88"
C_RED     = "#FF3333"
C_YELLOW  = "#FFB800"
C_TEXT    = "#C8E0F4"
C_DIM     = "#6A9ABB"
C_MUT     = "#2A4A66"

# ─────────────────────────────────────────────────────────
#  Shared stylesheet snippets
# ─────────────────────────────────────────────────────────
def _combo_ss():
    return f"""
        QComboBox {{
            background: {C_BG3};
            border: 1px solid {C_BORDER2};
            color: {C_CYAN};
            font-family: "Courier New";
            font-size: 12px;
            padding: 5px 10px;
            min-width: 100px;
        }}
        QComboBox:focus {{ border: 1px solid {C_CYAN}; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox::down-arrow {{
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {C_BLUE};
            margin-right: 6px;
        }}
        QComboBox QAbstractItemView {{
            background: {C_BG3};
            border: 1px solid {C_BORDER2};
            color: {C_TEXT};
            selection-background-color: {C_BORDER2};
            outline: none;
            font-size: 12px;
        }}
    """

def _input_ss():
    return f"""
        QLineEdit {{
            background: {C_BG3};
            border: 1px solid {C_BORDER};
            border-bottom: 2px solid {C_BLUE}55;
            color: {C_CYAN};
            font-family: "Courier New";
            font-size: 12px;
            padding: 5px 8px;
        }}
        QLineEdit:focus {{ border-bottom: 2px solid {C_CYAN}; }}
    """

def _check_ss():
    return f"""
        QCheckBox {{
            color: {C_TEXT};
            font-family: "Courier New";
            font-size: 11px;
            spacing: 8px;
            letter-spacing: 1px;
        }}
        QCheckBox::indicator {{
            width: 15px; height: 15px;
            border: 1px solid {C_BORDER2};
            background: {C_BG3};
        }}
        QCheckBox::indicator:checked {{
            background: {C_BLUE};
            border: 1px solid {C_CYAN};
        }}
    """

# ─────────────────────────────────────────────────────────
#  Small helper widgets (UI only)
# ─────────────────────────────────────────────────────────
class _TopBar(QWidget):
    """Animated flowing gradient bar at top of window."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._off = 0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(28)

    def _tick(self):
        self._off = (self._off + 2) % 300
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        w = self.width()
        g = QLinearGradient(0, 0, w, 0)
        stops = [(0.0, "#003399"), (0.25, "#00CFFF"),
                 (0.5, "#00FFEE"), (0.75, "#00CFFF"), (1.0, "#003399")]
        for pos, col in stops:
            g.setColorAt((pos + self._off / 300) % 1.0, QColor(col))
        p.fillRect(0, 0, w, 4, QBrush(g))


class _Divider(QWidget):
    """Glowing horizontal divider with centre dot."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)

    def paintEvent(self, e):
        p = QPainter(self)
        w, mid = self.width(), self.height() // 2
        g = QLinearGradient(0, mid, w, mid)
        g.setColorAt(0.0,  QColor(0, 0, 0, 0))
        g.setColorAt(0.35, QColor(0, 102, 255, 90))
        g.setColorAt(0.5,  QColor(0, 207, 255, 150))
        g.setColorAt(0.65, QColor(0, 102, 255, 90))
        g.setColorAt(1.0,  QColor(0, 0, 0, 0))
        p.setPen(QPen(QBrush(g), 1))
        p.drawLine(0, mid, w, mid)
        p.setBrush(QColor(C_CYAN))
        p.setPen(Qt.NoPen)
        p.drawEllipse(w // 2 - 3, mid - 3, 6, 6)


# =============================================================
#  VoiceThread  — ORIGINAL, UNTOUCHED
# =============================================================
class VoiceThread(QThread):
    command_received = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, mic_index=None):
        super().__init__()
        self.running = False
        self.enabled = False
        self.model = None
        self.recognizer = None
        self.mic_index = mic_index
        self.last_command_time = 0

    def initialize(self):
        try:
            model_dir = download_vosk_model()
            if not model_dir:
                self.status_update.emit("Model download failed!")
                return False
            self.model = Model(model_dir)
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.recognizer.SetWords(True)
            self.recognizer.SetGrammar('["on", "off", "active", "inactive", "turn"]')
            return True
        except Exception as e:
            self.status_update.emit(f"Init Error: {str(e)[:40]}")
            return False

    def run(self):
        if not VOSK_AVAILABLE:
            self.status_update.emit("Vosk not installed!")
            return
        if not self.initialize():
            return
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            if self.mic_index is not None:
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                                input=True, input_device_index=self.mic_index,
                                frames_per_buffer=2000)
            else:
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                                input=True, frames_per_buffer=2000)
            stream.start_stream()
            self.status_update.emit("Listening...")
            self.running = True
            while self.running:
                try:
                    if not self.enabled:
                        time.sleep(0.05)
                        continue
                    data = stream.read(2000, exception_on_overflow=False)
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        if 'result' in result and len(result['result']) > 0:
                            self.process_with_confidence(result['result'])
                except Exception:
                    continue
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            self.status_update.emit(f"Audio Error: {str(e)[:40]}")

    def process_with_confidence(self, words):
        if time.time() - self.last_command_time < 0.5:
            return
        detected_words = {}
        for word_info in words:
            word = word_info.get('word', '').lower()
            confidence = word_info.get('conf', 0)
            if confidence >= 0.90:
                detected_words[word] = confidence
        if 'turn' in detected_words and 'off' in detected_words:
            avg_conf = (detected_words['turn'] + detected_words['off']) / 2
            self.command_received.emit('off')
            self.status_update.emit(f"→ OFF ({int(avg_conf*100)}%)")
            self.last_command_time = time.time()
            return
        if 'turn' in detected_words and 'on' in detected_words:
            avg_conf = (detected_words['turn'] + detected_words['on']) / 2
            self.command_received.emit('on')
            self.status_update.emit(f"→ ON ({int(avg_conf*100)}%)")
            self.last_command_time = time.time()
            return
        if 'off' in detected_words or 'inactive' in detected_words:
            conf = detected_words.get('off', detected_words.get('inactive', 0))
            self.command_received.emit('off')
            self.status_update.emit(f"→ OFF ({int(conf*100)}%)")
            self.last_command_time = time.time()
            return
        if 'on' in detected_words or 'active' in detected_words:
            conf = detected_words.get('on', detected_words.get('active', 0))
            self.command_received.emit('on')
            self.status_update.emit(f"→ ON ({int(conf*100)}%)")
            self.last_command_time = time.time()
            return

    def stop(self):
        self.running = False
        self.enabled = False


# =============================================================
#  OverlayWindow  — ORIGINAL, UNTOUCHED
# =============================================================
class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
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
        color = "#00FF00" if active else "#FF0000"
        status = "ACTIVE" if active else "INACTIVE"
        scope = "OPEN" if scope_open else "CLOSED"
        text = f"● {status} | Scope: {scope}"
        bg_color = "rgba(0, 0, 0, 180)" if show_bg else "transparent"
        self.label.setStyleSheet(f"color: {color}; background-color: {bg_color}; padding: 5px;")
        self.label.setText(text)
        self.adjustSize()


# =============================================================
#  MacroThread  — ORIGINAL, UNTOUCHED
# =============================================================
class MacroThread(QThread):
    status_update = pyqtSignal(bool, bool)

    def __init__(self, aim_button='o'):
        super().__init__()
        self.enabled = False
        self.scope_toggled = False
        self.aim_held = False
        self.right_click_time = 0
        self.last_right_click_activity = 0
        self.running = True
        self.right_click_pressed = False
        self.aim_button = aim_button.lower()

    def set_aim_button(self, button):
        self.aim_button = button.lower()

    def run(self):
        def on_click(x, y, button, pressed):
            if button == Button.right:
                if pressed:
                    self.right_click_time = time.time()
                    self.last_right_click_activity = time.time()
                    self.right_click_pressed = True
                else:
                    self.right_click_pressed = False
                    hold_duration = (time.time() - self.right_click_time) * 1000
                    if hold_duration < 300:
                        self.scope_toggled = not self.scope_toggled
                        self.last_right_click_activity = time.time()

        mouse_listener = MouseListener(on_click=on_click)
        mouse_listener.start()
        last_e_state = False
        last_q_state = False
        last_enabled = False

        while self.running:
            try:
                if self.scope_toggled:
                    if (time.time() - self.last_right_click_activity) > 30.0:
                        self.scope_toggled = False
                if self.enabled != last_enabled:
                    last_enabled = self.enabled
                if self.enabled:
                    e_pressed = keyboard.is_pressed('e')
                    q_pressed = keyboard.is_pressed('q')
                    if e_pressed != last_e_state:
                        last_e_state = e_pressed
                    if q_pressed != last_q_state:
                        last_q_state = q_pressed
                    scope_active = self.scope_toggled or self.right_click_pressed
                    should_hold = (e_pressed or q_pressed) and not scope_active
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
                    if last_e_state or last_q_state:
                        last_e_state = False
                        last_q_state = False
                    if self.aim_held:
                        try:
                            keyboard.release(self.aim_button)
                            self.aim_held = False
                        except Exception:
                            self.aim_held = False
                    self.status_update.emit(False, self.scope_toggled)
                if self.enabled:
                    time.sleep(0.05)
                else:
                    time.sleep(0.2)
            except Exception:
                if self.aim_held:
                    try:
                        keyboard.release(self.aim_button)
                    except:
                        pass
                    self.aim_held = False
                time.sleep(0.1)

    def stop(self):
        self.running = False
        if self.aim_held:
            try:
                keyboard.release(self.aim_button)
            except:
                pass


# =============================================================
#  SettingsDialog  — NEW SKIN, identical get_values() / signals
# =============================================================
class SettingsDialog(QDialog):
    def __init__(self, parent, current_hotkey, current_aim,
                 voice_enabled, current_mic, voice_status_text):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(490, 560)
        self.parent_window = parent
        self.setStyleSheet(f"QDialog {{ background: {C_BG}; }} QLabel {{ background: transparent; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # animated top bar
        root.addWidget(_TopBar())

        # header
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(18, 0, 18, 0)
        t = QLabel("⚙   SETTINGS")
        t.setFont(QFont("Arial Black", 12))
        t.setStyleSheet(f"color: {C_CYAN}; letter-spacing: 3px;")
        hl.addWidget(t)
        hl.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(30, 30)
        x_btn.setCursor(Qt.PointingHandCursor)
        x_btn.setStyleSheet(f"""
            QPushButton {{ background: #FF333318; border: 1px solid #FF333340;
                           color: {C_RED}; font-size: 13px; }}
            QPushButton:hover {{ background: #FF333340; border-color: {C_RED}; }}
        """)
        x_btn.clicked.connect(self.reject)
        hl.addWidget(x_btn)
        root.addWidget(hdr)

        # body
        body = QWidget()
        body.setStyleSheet(f"background: {C_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(18, 14, 18, 10)
        bl.setSpacing(0)

        def add_row(label_text, desc_text, widget):
            w = QWidget()
            w.setStyleSheet(f"border-bottom: 1px solid {C_BORDER};")
            rl = QHBoxLayout(w)
            rl.setContentsMargins(0, 10, 0, 10)
            info = QVBoxLayout(); info.setSpacing(2)
            lb = QLabel(label_text)
            lb.setFont(QFont("Segoe UI", 12, QFont.Bold))
            lb.setStyleSheet(f"color: {C_TEXT}; border: none;")
            dc = QLabel(desc_text)
            dc.setFont(QFont("Courier New", 9))
            dc.setStyleSheet(f"color: {C_MUT}; letter-spacing: 1px; border: none;")
            info.addWidget(lb); info.addWidget(dc)
            rl.addLayout(info); rl.addStretch(); rl.addWidget(widget)
            bl.addWidget(w)

        # Macro Hotkey
        self.hotkey_combo = QComboBox()
        self.hotkey_combo.addItems(MACRO_HOTKEYS)
        self.hotkey_combo.setCurrentText(current_hotkey)
        self.hotkey_combo.setMaxVisibleItems(10)
        self.hotkey_combo.setStyleSheet(_combo_ss())
        add_row("Macro Hotkey", "Key to toggle macro ON / OFF", self.hotkey_combo)

        # Aim Button
        self.aim_combo = QComboBox()
        self.aim_combo.addItems(AIM_BUTTONS)
        self.aim_combo.setCurrentText(current_aim)
        self.aim_combo.setMaxVisibleItems(10)
        self.aim_combo.setStyleSheet(_combo_ss())
        add_row("Aim Button", "Button auto-held while peeking (Q or E)", self.aim_combo)

        # Voice section header
        vc_lbl = QLabel("🎤   VOICE CONTROL")
        vc_lbl.setFont(QFont("Arial Black", 10))
        vc_lbl.setStyleSheet(f"color: {C_CYAN}; letter-spacing: 2px; padding: 10px 0 4px 0; border: none;")
        bl.addWidget(vc_lbl)

        # Voice enable
        self.voice_check = QCheckBox("Enable Voice Commands")
        self.voice_check.setChecked(voice_enabled)
        self.voice_check.setStyleSheet(_check_ss())
        self.voice_check.stateChanged.connect(self.on_voice_toggled)
        bl.addWidget(self.voice_check)

        # Microphone
        mic_row = QWidget(); mic_row.setStyleSheet("background: transparent; border: none;")
        mrl = QHBoxLayout(mic_row); mrl.setContentsMargins(0, 8, 0, 0); mrl.setSpacing(8)
        ml = QLabel("Microphone:")
        ml.setFont(QFont("Courier New", 10))
        ml.setStyleSheet(f"color: {C_DIM}; border: none;")
        ml.setFixedWidth(100)
        self.mic_combo = QComboBox()
        mic_list = get_microphone_list()
        self.mic_combo.addItems(mic_list)
        if current_mic in mic_list:
            self.mic_combo.setCurrentText(current_mic)
        else:
            self.mic_combo.setCurrentIndex(0)
        self.mic_combo.setMaxVisibleItems(5)
        self.mic_combo.setStyleSheet(_combo_ss())
        mrl.addWidget(ml); mrl.addWidget(self.mic_combo); mrl.addStretch()
        bl.addWidget(mic_row)

        # Note
        note = QLabel("Strict 90%+ confidence  ·  Say: On / Off / Turn On / Turn Off")
        note.setFont(QFont("Courier New", 9))
        note.setStyleSheet(f"color: {C_GREEN}; padding: 6px 0 2px 0; border: none; letter-spacing: 1px;")
        bl.addWidget(note)

        # Voice status
        self.voice_status = QLabel(f"🎤  {voice_status_text}")
        col = C_GREEN if "Listening" in voice_status_text else C_MUT
        self.voice_status.setFont(QFont("Courier New", 10))
        self.voice_status.setStyleSheet(f"color: {col}; border: none; letter-spacing: 1px;")
        bl.addWidget(self.voice_status)

        bl.addStretch()
        root.addWidget(body)

        # footer buttons
        foot = QWidget()
        foot.setStyleSheet(f"background: {C_BG3}; border-top: 1px solid {C_BORDER};")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(18, 12, 18, 12); fl.setSpacing(10)

        save_btn = QPushButton("✔   APPLY & SAVE")
        save_btn.setFixedHeight(40)
        save_btn.setFont(QFont("Arial Black", 10))
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #0A2A1E,stop:1 #051510);
                border: 1px solid {C_GREEN};
                color: {C_GREEN};
                letter-spacing: 2px;
            }}
            QPushButton:hover {{ background: #0D3524; }}
            QPushButton:pressed {{ background: #031008; }}
        """)
        save_btn.clicked.connect(self.accept)
        fl.addWidget(save_btn)

        close_btn = QPushButton("✕   CANCEL")
        close_btn.setFixedHeight(40)
        close_btn.setFixedWidth(130)
        close_btn.setFont(QFont("Arial Black", 10))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: #160808;
                border: 1px solid #FF333340;
                color: {C_RED};
                letter-spacing: 2px;
            }}
            QPushButton:hover {{ border-color: {C_RED}; background: #200D0D; }}
            QPushButton:pressed {{ background: #0A0505; }}
        """)
        close_btn.clicked.connect(self.reject)
        fl.addWidget(close_btn)
        root.addWidget(foot)

    # ── these three methods are identical to the original ─────────────────
    def on_voice_toggled(self):
        enabled = self.voice_check.isChecked()
        if enabled:
            self.voice_status.setText("🎤  Starting...")
            self.voice_status.setStyleSheet(f"color: {C_YELLOW}; border: none; letter-spacing: 1px;")
            mic_index = self.mic_combo.currentIndex()
            actual_index = mic_index - 1 if mic_index > 0 else None
            self.parent_window.start_voice(actual_index)
        else:
            self.voice_status.setText("🎤  Disabled")
            self.voice_status.setStyleSheet(f"color: {C_MUT}; border: none; letter-spacing: 1px;")
            self.parent_window.stop_voice()

    def update_voice_status(self, status):
        self.voice_status.setText(f"🎤  {status}")
        if "Listening" in status:
            col = C_GREEN
        elif "Error" in status or "not" in status.lower() or "failed" in status.lower():
            col = C_RED
        elif "→" in status or "%" in status:
            col = C_CYAN
        else:
            col = C_MUT
        self.voice_status.setStyleSheet(f"color: {col}; border: none; letter-spacing: 1px;")

    def get_values(self):
        mic_index = self.mic_combo.currentIndex()
        actual_index = mic_index - 1 if mic_index > 0 else None
        return (
            self.hotkey_combo.currentText(),
            self.aim_combo.currentText(),
            self.voice_check.isChecked(),
            self.mic_combo.currentText(),
            actual_index
        )


# =============================================================
#  ClickableLabel  — ORIGINAL, UNTOUCHED
# =============================================================
class ClickableLabel(QLabel):
    def __init__(self, text, url, parent=None):
        super().__init__(text, parent)
        self.url = url
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def mousePressEvent(self, event):
        webbrowser.open(self.url)


# =============================================================
#  MainWindow  — ALL LOGIC ORIGINAL / only init_ui() reskinned
# =============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_file = "settings.json"
        self.current_hotkey = None
        self.voice_thread = None
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
            self.start_voice(self.mic_index)

    # ── original methods — not a single character changed ─────────────────
    def set_window_icon(self):
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            logo_path = resource_path("logo.png")
            if os.path.exists(logo_path):
                self.setWindowIcon(QIcon(logo_path))
            else:
                pixmap = QPixmap(32, 32)
                pixmap.fill(QColor(0, 207, 255))
                self.setWindowIcon(QIcon(pixmap))

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.overlay_x = settings.get('overlay_x', 1600)
                    self.overlay_y = settings.get('overlay_y', 50)
                    self.overlay_bg = settings.get('overlay_bg', True)
                    self.start_minimized = settings.get('start_minimized', False)
                    self.macro_hotkey = settings.get('macro_hotkey', 'F8')
                    self.aim_button = settings.get('aim_button', 'O')
                    self.voice_enabled = settings.get('voice_enabled', False)
                    self.mic_name = settings.get('mic_name', 'Default')
                    self.mic_index = settings.get('mic_index', None)
                    self.is_first_run = False
            else:
                self.set_defaults()
                self.is_first_run = True
        except:
            self.set_defaults()
            self.is_first_run = True

    def set_defaults(self):
        self.overlay_x = 1600
        self.overlay_y = 50
        self.overlay_bg = True
        self.start_minimized = False
        self.macro_hotkey = 'F8'
        self.aim_button = 'O'
        self.voice_enabled = False
        self.mic_name = 'Default'
        self.mic_index = None

    def save_settings(self):
        try:
            settings = {
                'overlay_x': self.overlay_x,
                'overlay_y': self.overlay_y,
                'overlay_bg': self.overlay_bg,
                'start_minimized': self.start_minimized,
                'macro_hotkey': self.macro_hotkey,
                'aim_button': self.aim_button,
                'voice_enabled': self.voice_enabled,
                'mic_name': self.mic_name,
                'mic_index': self.mic_index
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
        except:
            pass

    def register_hotkey(self, key):
        try:
            if self.current_hotkey:
                keyboard.remove_hotkey(self.current_hotkey)
        except:
            pass
        try:
            self.current_hotkey = keyboard.add_hotkey(key.lower(), self.toggle_macro)
        except:
            pass

    def start_voice(self, mic_index=None):
        if not VOSK_AVAILABLE:
            return
        if self.voice_thread and self.voice_thread.isRunning():
            self.voice_thread.stop()
            self.voice_thread.wait()
        self.voice_thread = VoiceThread(mic_index=mic_index)
        self.voice_thread.command_received.connect(self.on_voice_command)
        self.voice_thread.status_update.connect(self.on_voice_status)
        self.voice_thread.enabled = True
        self.voice_thread.start()

    def stop_voice(self):
        if self.voice_thread:
            self.voice_thread.stop()
        self.voice_label.setText("🎤  Voice: Disabled")
        self.voice_label.setStyleSheet(
            f"color: {C_MUT}; font-size: 10px; font-family: 'Courier New'; letter-spacing: 1px;")

    def on_voice_command(self, command):
        if command == 'on':
            if not self.macro_thread.enabled:
                self.macro_thread.enabled = True
        elif command == 'off':
            if self.macro_thread.enabled:
                self.macro_thread.enabled = False

    def on_voice_status(self, status):
        if "Listening" in status:
            self.voice_label.setText("🎤  Voice: Listening...")
            self.voice_label.setStyleSheet(
                f"color: {C_GREEN}; font-size: 10px; font-family: 'Courier New'; letter-spacing: 1px;")
        elif "→" in status or "%" in status:
            self.voice_label.setText(f"🎤  {status}")
            self.voice_label.setStyleSheet(
                f"color: {C_CYAN}; font-size: 10px; font-family: 'Courier New'; letter-spacing: 1px;")
        elif "Error" in status or "not" in status.lower() or "failed" in status.lower():
            self.voice_label.setText(f"🎤  {status}")
            self.voice_label.setStyleSheet(
                f"color: {C_RED}; font-size: 10px; font-family: 'Courier New'; letter-spacing: 1px;")
        else:
            self.voice_label.setText(f"🎤  {status}")
            self.voice_label.setStyleSheet(
                f"color: {C_YELLOW}; font-size: 10px; font-family: 'Courier New'; letter-spacing: 1px;")
        if self.settings_dialog:
            self.settings_dialog.update_voice_status(status)

    def show_settings(self):
        voice_status = "Listening..." if (
            self.voice_thread and
            self.voice_thread.isRunning() and
            self.voice_thread.enabled
        ) else "Disabled"

        self.settings_dialog = SettingsDialog(
            self, self.macro_hotkey, self.aim_button,
            self.voice_enabled, self.mic_name, voice_status
        )

        if self.settings_dialog.exec_() == QDialog.Accepted:
            new_hotkey, new_aim, new_voice, new_mic_name, new_mic_index = \
                self.settings_dialog.get_values()

            if new_hotkey != self.macro_hotkey:
                self.macro_hotkey = new_hotkey
                self.register_hotkey(new_hotkey)
                self.toggle_btn.setText(f"  ⚡   Toggle Macro  [{new_hotkey}]")

            if new_aim != self.aim_button:
                self.aim_button = new_aim
                self.macro_thread.set_aim_button(new_aim)

            self.voice_enabled = new_voice
            self.mic_name = new_mic_name
            self.mic_index = new_mic_index

            if new_voice:
                self.start_voice(new_mic_index)
            else:
                self.stop_voice()

            self.save_settings()
            QMessageBox.information(self, "Success", "Settings saved successfully!")

        self.settings_dialog = None

    def update_overlay_status(self, active, scope_open):
        self.overlay.update_status(active, scope_open, self.overlay_bg)
        if active:
            self.status_dot.setStyleSheet(f"color: {C_GREEN}; font-size: 20px;")
            self.status_text.setText("ACTIVE")
            self.status_text.setStyleSheet(
                f"color: {C_GREEN}; font-size: 22px; font-family: 'Arial Black'; letter-spacing: 5px;")
            self.scope_text.setText(f"SCOPE: {'OPEN' if scope_open else 'CLOSED'}  ·  MACRO: ON")
            self.scope_text.setStyleSheet(
                f"color: {C_DIM}; font-family: 'Courier New'; font-size: 10px; letter-spacing: 2px;")
        else:
            self.status_dot.setStyleSheet(f"color: {C_RED}; font-size: 20px;")
            self.status_text.setText("INACTIVE")
            self.status_text.setStyleSheet(
                f"color: {C_RED}; font-size: 22px; font-family: 'Arial Black'; letter-spacing: 5px;")
            self.scope_text.setText(f"SCOPE: {'OPEN' if scope_open else 'CLOSED'}  ·  MACRO: OFF")
            self.scope_text.setStyleSheet(
                f"color: {C_MUT}; font-family: 'Courier New'; font-size: 10px; letter-spacing: 2px;")

    def toggle_macro(self):
        self.macro_thread.enabled = not self.macro_thread.enabled

    def apply_position(self):
        try:
            self.overlay_x = int(self.x_input.text())
            self.overlay_y = int(self.y_input.text())
            self.overlay.move(self.overlay_x, self.overlay_y)
            self.save_settings()
            QMessageBox.information(self, "Saved",
                                    f"Position saved: X={self.overlay_x}, Y={self.overlay_y}")
        except:
            QMessageBox.warning(self, "Error", "Invalid position values!")

    def toggle_background(self):
        self.overlay_bg = self.bg_check.isChecked()
        self.save_settings()

    def toggle_minimize(self):
        self.start_minimized = self.minimize_check.isChecked()
        self.save_settings()

    def watchdog_check(self):
        if self.macro_thread.aim_held:
            e_state = keyboard.is_pressed('e')
            q_state = keyboard.is_pressed('q')
            if not e_state and not q_state:
                try:
                    keyboard.release(self.macro_thread.aim_button)
                    self.macro_thread.aim_held = False
                except:
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

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Peak & Aim Assistant - MAAKTHUNDER")
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            logo_path = resource_path("logo.png")
            if os.path.exists(logo_path):
                self.tray_icon.setIcon(QIcon(logo_path))
            else:
                pixmap = QPixmap(16, 16)
                pixmap.fill(QColor(0, 207, 255))
                self.tray_icon.setIcon(QIcon(pixmap))
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

    # ══════════════════════════════════════════════════════════════════════
    #  init_ui  — NEW SKIN.  Every widget name & signal stays the same.
    # ══════════════════════════════════════════════════════════════════════
    def init_ui(self):
        self.setWindowTitle("Peak & Aim Assistant v2.0 — MAAKTHUNDER")
        self.setFixedSize(420, 700)

        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(C_BG))
        pal.setColor(QPalette.WindowText, QColor(C_TEXT))
        self.setPalette(pal)

        central = QWidget()
        central.setStyleSheet(f"background: {C_BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── animated top bar ──────────────────────────────────────────────
        root.addWidget(_TopBar())

        # ── HEADER ───────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0A1E3855, stop:1 {C_BG});
                border-bottom: 1px solid {C_BORDER};
            }}
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 12)
        hl.setSpacing(14)

        logo_lbl = QLabel()
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("⚡")
            logo_lbl.setFont(QFont("Arial", 36))
            logo_lbl.setStyleSheet(f"color: {C_CYAN};")
        logo_lbl.setFixedSize(72, 72)
        hl.addWidget(logo_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)

        title_lbl = QLabel("PEAK & AIM ASSISTANT")
        title_lbl.setFont(QFont("Arial Black", 12))
        title_lbl.setStyleSheet(f"color: {C_CYAN}; letter-spacing: 2px; background: transparent;")
        title_col.addWidget(title_lbl)

        sub_lbl = QLabel("GAMELOOP EDITION")
        sub_lbl.setFont(QFont("Courier New", 10))
        sub_lbl.setStyleSheet(f"color: {C_DIM}; letter-spacing: 3px; background: transparent;")
        title_col.addWidget(sub_lbl)

        creator_lbl = QLabel("// BY MAAKTHUNDER")
        creator_lbl.setFont(QFont("Courier New", 9))
        creator_lbl.setStyleSheet(f"color: {C_MUT}; letter-spacing: 2px; background: transparent;")
        title_col.addWidget(creator_lbl)

        hl.addLayout(title_col)
        hl.addStretch()

        ver_lbl = QLabel("V2.0")
        ver_lbl.setFont(QFont("Courier New", 10))
        ver_lbl.setStyleSheet(f"""
            color: {C_CYAN};
            background: #00CFFF15;
            border: 1px solid #00CFFF30;
            padding: 4px 10px;
            letter-spacing: 2px;
        """)
        ver_lbl.setAlignment(Qt.AlignTop | Qt.AlignRight)
        hl.addWidget(ver_lbl, alignment=Qt.AlignTop)
        root.addWidget(header)

        # ── BODY ─────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background: {C_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(14, 12, 14, 12)
        bl.setSpacing(8)

        # STATUS CARD
        status_card = QWidget()
        status_card.setMinimumHeight(76)
        status_card.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #081828, stop:1 #040C18);
                border: 1px solid {C_BORDER};
            }}
        """)
        sc = QHBoxLayout(status_card)
        sc.setContentsMargins(14, 12, 14, 12)
        sc.setSpacing(12)

        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Arial", 18))
        self.status_dot.setStyleSheet(f"color: {C_RED}; font-size: 20px;")
        self.status_dot.setFixedWidth(28)
        sc.addWidget(self.status_dot)

        st_col = QVBoxLayout(); st_col.setSpacing(3)
        self.status_text = QLabel("INACTIVE")
        self.status_text.setFont(QFont("Arial Black", 16))
        self.status_text.setStyleSheet(
            f"color: {C_RED}; font-size: 22px; font-family: 'Arial Black'; letter-spacing: 5px;")
        st_col.addWidget(self.status_text)
        self.scope_text = QLabel("SCOPE: CLOSED  ·  MACRO: OFF")
        self.scope_text.setFont(QFont("Courier New", 10))
        self.scope_text.setStyleSheet(
            f"color: {C_MUT}; font-family: 'Courier New'; font-size: 10px; letter-spacing: 2px;")
        st_col.addWidget(self.scope_text)
        sc.addLayout(st_col)
        sc.addStretch()
        bl.addWidget(status_card)

        # TOGGLE BUTTON
        self.toggle_btn = QPushButton(f"  ⚡   Toggle Macro  [{self.macro_hotkey}]")
        self.toggle_btn.setFixedHeight(46)
        self.toggle_btn.setFont(QFont("Arial Black", 10))
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #091A36, stop:1 #040C1C);
                border: 1px solid {C_BORDER};
                border-left: 3px solid {C_BLUE};
                color: {C_CYAN};
                letter-spacing: 2px;
                text-align: left;
                padding-left: 12px;
            }}
            QPushButton:hover {{
                border: 1px solid {C_BORDER2};
                border-left: 3px solid {C_CYAN};
                color: white;
                background: #0C2040;
            }}
            QPushButton:pressed {{ background: {C_BG3}; }}
        """)
        self.toggle_btn.clicked.connect(self.toggle_macro)
        bl.addWidget(self.toggle_btn)

        # SETTINGS BUTTON
        settings_btn = QPushButton("  ⚙   Settings")
        settings_btn.setFixedHeight(46)
        settings_btn.setFont(QFont("Arial Black", 10))
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #0A1628, stop:1 #060F1E);
                border: 1px solid {C_BORDER};
                border-left: 3px solid {C_MUT};
                color: {C_DIM};
                letter-spacing: 2px;
                text-align: left;
                padding-left: 12px;
            }}
            QPushButton:hover {{
                border: 1px solid {C_BORDER2};
                border-left: 3px solid {C_DIM};
                color: {C_TEXT};
                background: #0A1628;
            }}
            QPushButton:pressed {{ background: {C_BG3}; }}
        """)
        settings_btn.clicked.connect(self.show_settings)
        bl.addWidget(settings_btn)

        bl.addWidget(_Divider())

        # OVERLAY POSITION
        pos_lbl = QLabel("OVERLAY POSITION")
        pos_lbl.setFont(QFont("Courier New", 9))
        pos_lbl.setStyleSheet(f"color: {C_BLUE}; letter-spacing: 4px; background: transparent;")
        bl.addWidget(pos_lbl)

        pos_row = QHBoxLayout(); pos_row.setSpacing(8)
        for label_txt, default_val, attr_name in [
            ("X:", self.overlay_x, "x_input"),
            ("Y:", self.overlay_y, "y_input"),
        ]:
            lbl = QLabel(label_txt)
            lbl.setFont(QFont("Courier New", 11))
            lbl.setStyleSheet(f"color: {C_DIM}; background: transparent;")
            lbl.setFixedWidth(18)
            pos_row.addWidget(lbl)
            inp = QLineEdit(str(default_val))
            inp.setFixedWidth(72)
            inp.setStyleSheet(_input_ss())
            setattr(self, attr_name, inp)
            pos_row.addWidget(inp)

        apply_btn = QPushButton("Apply & Save")
        apply_btn.setFixedHeight(34)
        apply_btn.setFont(QFont("Courier New", 10))
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_BG3};
                border: 1px solid {C_BORDER2};
                color: {C_CYAN};
                padding: 0 12px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{ border-color: {C_CYAN}; color: white; }}
            QPushButton:pressed {{ background: {C_BG}; }}
        """)
        apply_btn.clicked.connect(self.apply_position)
        pos_row.addWidget(apply_btn)
        pos_row.addStretch()
        bl.addLayout(pos_row)

        # CHECKBOXES
        self.bg_check = QCheckBox("Show Overlay Background")
        self.bg_check.setChecked(self.overlay_bg)
        self.bg_check.setStyleSheet(_check_ss())
        self.bg_check.stateChanged.connect(self.toggle_background)
        bl.addWidget(self.bg_check)

        self.minimize_check = QCheckBox("Start Minimized to Tray")
        self.minimize_check.setChecked(self.start_minimized)
        self.minimize_check.setStyleSheet(_check_ss())
        self.minimize_check.stateChanged.connect(self.toggle_minimize)
        bl.addWidget(self.minimize_check)

        # VOICE STATUS LABEL
        self.voice_label = QLabel("🎤  Voice: Disabled")
        self.voice_label.setFont(QFont("Courier New", 10))
        self.voice_label.setStyleSheet(
            f"color: {C_MUT}; font-size: 10px; font-family: 'Courier New'; "
            f"letter-spacing: 1px; background: transparent;")
        bl.addWidget(self.voice_label)

        bl.addWidget(_Divider())

        # TIP
        tip = QLabel("⚡  Scope auto-resets after 30 seconds of inactivity")
        tip.setFont(QFont("Courier New", 9))
        tip.setWordWrap(True)
        tip.setStyleSheet(f"""
            color: #005588;
            background: #00CFFF05;
            border-left: 2px solid #005588;
            padding: 7px 10px;
            letter-spacing: 1px;
        """)
        bl.addWidget(tip)

        bl.addWidget(_Divider())

        # HOW IT WORKS
        how_lbl = QLabel("HOW IT WORKS")
        how_lbl.setFont(QFont("Courier New", 9))
        how_lbl.setStyleSheet(f"color: {C_BLUE}; letter-spacing: 4px; background: transparent;")
        bl.addWidget(how_lbl)

        for line in [
            f"[{self.macro_hotkey}]  Toggle Macro ON / OFF",
            "[Q / E]  Peak with Auto-Aim",
            "[Right Click]  Toggle Scope",
        ]:
            lbl = QLabel(line)
            lbl.setFont(QFont("Courier New", 10))
            lbl.setStyleSheet(f"color: {C_DIM}; letter-spacing: 1px; background: transparent;")
            bl.addWidget(lbl)

        bl.addWidget(_Divider())

        # SOCIAL LINKS
        yt_row = QHBoxLayout(); yt_row.setSpacing(8)
        yt_icon_path = resource_path("youtube.png")
        if os.path.exists(yt_icon_path):
            yi = QLabel()
            yi.setPixmap(QPixmap(yt_icon_path).scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            yt_row.addWidget(yi)
        yt_link = ClickableLabel("WWW.YOUTUBE.COM/@MAAKTHUNDER",
                                 "https://www.youtube.com/@MAAKTHUNDER")
        yt_link.setFont(QFont("Courier New", 10))
        yt_link.setStyleSheet(f"color: {C_BLUE}; text-decoration: underline; background: transparent;")
        yt_row.addWidget(yt_link); yt_row.addStretch()
        bl.addLayout(yt_row)

        tt_row = QHBoxLayout(); tt_row.setSpacing(8)
        tt_icon_path = resource_path("tiktok.png")
        if os.path.exists(tt_icon_path):
            ti = QLabel()
            ti.setPixmap(QPixmap(tt_icon_path).scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            tt_row.addWidget(ti)
        tt_link = ClickableLabel("WWW.TIKTOK.COM/@MAAKTHUNDER",
                                 "https://www.tiktok.com/@maakthunder")
        tt_link.setFont(QFont("Courier New", 10))
        tt_link.setStyleSheet(f"color: {C_BLUE}; text-decoration: underline; background: transparent;")
        tt_row.addWidget(tt_link); tt_row.addStretch()
        bl.addLayout(tt_row)

        bl.addStretch()
        root.addWidget(body)

        # ── FOOTER ───────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(34)
        footer.setStyleSheet(f"background: {C_BG3}; border-top: 1px solid {C_BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(14, 0, 14, 0)
        ft = QLabel("MADE FOR GAMELOOP  ·  MAAKTHUNDER  ·  V2.0")
        ft.setFont(QFont("Courier New", 8))
        ft.setStyleSheet(f"color: {C_MUT}; letter-spacing: 3px;")
        ft.setAlignment(Qt.AlignCenter)
        fl.addWidget(ft)
        root.addWidget(footer)

        # bottom accent bar
        bot = QWidget(); bot.setFixedHeight(3)
        bot.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 transparent,stop:0.5 {C_BLUE},stop:1 transparent);")
        root.addWidget(bot)

        if self.is_first_run or not self.start_minimized:
            self.show()
        else:
            self.hide()


# =============================================================
#  main()  — ORIGINAL, UNTOUCHED
# =============================================================
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
