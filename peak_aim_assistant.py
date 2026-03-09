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
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor, QPixmap, QCursor
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
    """Get ONLY real input microphone devices"""
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
    """Get Vosk model path - check bundled location first"""
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
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    input_device_index=self.mic_index,
                    frames_per_buffer=2000
                )
            else:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=2000
                )
            
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
                            self.process_exact_words(result['result'])
                
                except Exception:
                    continue
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            self.status_update.emit(f"Audio Error: {str(e)[:40]}")
    
    def process_exact_words(self, words):
        """Process ONLY exact command words with 90%+ confidence"""
        
        if time.time() - self.last_command_time < 1.0:
            return
        
        found_words = {}
        for word_info in words:
            word = word_info.get('word', '').lower().strip()
            confidence = word_info.get('conf', 0)
            
            if word in ['on', 'active', 'turn']:
                 if confidence >= 0.90:  # Strict for "on"
                      found_words[word] = confidence
            elif word in ['off', 'of', 'inactive']:
                if confidence >= 0.85:  # Easier for "off"
                     found_words[word] = confidence
        
        if 'turn' in found_words and ('off' in found_words or 'of' in found_words):
            avg_conf = (found_words['turn'] + found_words.get('off', found_words.get('of', 0))) / 2
            if avg_conf >= 0.85:
                self.command_received.emit('off')
                self.status_update.emit(f"→ OFF ({int(avg_conf*100)}%)")
                self.last_command_time = time.time()
                return
        
        if 'turn' in found_words and 'on' in found_words:
            avg_conf = (found_words['turn'] + found_words['on']) / 2
            if avg_conf >= 0.90:
                self.command_received.emit('on')
                self.status_update.emit(f"→ ON ({int(avg_conf*100)}%)")
                self.last_command_time = time.time()
                return
        
        if 'off' in found_words or 'of' in found_words or 'inactive' in found_words:
            conf = found_words.get('off', found_words.get('of', found_words.get('inactive', 0)))
            if conf >= 0.85:
                self.command_received.emit('off')
                self.status_update.emit(f"→ OFF ({int(conf*100)}%)")
                self.last_command_time = time.time()
                return
        
        if 'on' in found_words or 'active' in found_words:
            conf = found_words.get('on', found_words.get('active', 0))
            if conf >= 0.90:
                self.command_received.emit('on')
                self.status_update.emit(f"→ ON ({int(conf*100)}%)")
                self.last_command_time = time.time()
                return
    
    def stop(self):
        self.running = False
        self.enabled = False

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

class SettingsDialog(QDialog):
    def __init__(self, parent, current_hotkey, current_aim,
                 voice_enabled, current_mic, voice_status_text):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(480, 420)
        self.parent_window = parent
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 10, 15, 10)
        
        title = QLabel("⚙ Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        hotkey_layout = QHBoxLayout()
        hotkey_label = QLabel("Macro Hotkey:")
        hotkey_label.setStyleSheet("color: #CCCCCC;")
        hotkey_label.setFixedWidth(120)
        hotkey_layout.addWidget(hotkey_label)
        self.hotkey_combo = QComboBox()
        self.hotkey_combo.addItems(MACRO_HOTKEYS)
        self.hotkey_combo.setCurrentText(current_hotkey)
        self.hotkey_combo.setMaxVisibleItems(10)
        hotkey_layout.addWidget(self.hotkey_combo)
        layout.addLayout(hotkey_layout)
        
        aim_layout = QHBoxLayout()
        aim_label = QLabel("Aim Button:")
        aim_label.setStyleSheet("color: #CCCCCC;")
        aim_label.setFixedWidth(120)
        aim_layout.addWidget(aim_label)
        self.aim_combo = QComboBox()
        self.aim_combo.addItems(AIM_BUTTONS)
        self.aim_combo.setCurrentText(current_aim)
        self.aim_combo.setMaxVisibleItems(10)
        aim_layout.addWidget(self.aim_combo)
        layout.addLayout(aim_layout)
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        voice_title = QLabel("🎤 Voice Control:")
        voice_title.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(voice_title)
        
        self.voice_check = QCheckBox("Enable Voice Commands")
        self.voice_check.setStyleSheet("color: white;")
        self.voice_check.setChecked(voice_enabled)
        self.voice_check.stateChanged.connect(self.on_voice_toggled)
        layout.addWidget(self.voice_check)
        
        mic_layout = QHBoxLayout()
        mic_label = QLabel("Microphone:")
        mic_label.setStyleSheet("color: #CCCCCC;")
        mic_label.setFixedWidth(120)
        mic_layout.addWidget(mic_label)
        self.mic_combo = QComboBox()
        self.mic_list = get_microphone_list()
        self.mic_combo.addItems(self.mic_list)
        if current_mic in self.mic_list:
            self.mic_combo.setCurrentText(current_mic)
        else:
            self.mic_combo.setCurrentIndex(0)
        self.mic_combo.setMaxVisibleItems(5)
        mic_layout.addWidget(self.mic_combo)
        layout.addLayout(mic_layout)
        
        note = QLabel("Note: Exact word matching (90%+ confidence)")
        note.setStyleSheet("color: #00FF00; font-size: 8pt;")
        layout.addWidget(note)
        
        self.voice_status = QLabel(f"🎤 {voice_status_text}")
        color = "#00FF00" if "Listening" in voice_status_text else "#888888"
        self.voice_status.setStyleSheet(f"color: {color}; font-size: 8pt;")
        layout.addWidget(self.voice_status)
        
        hint = QLabel('Say clearly: "On" / "Off" / "Active" / "Inactive"\n'
                      '                     "Turn On" / "Turn Off"')
        hint.setStyleSheet("color: #888888; font-size: 8pt;")
        layout.addWidget(hint)
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        button_layout = QHBoxLayout()
        save_btn = QPushButton("✔ Apply & Save")
        save_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        save_btn.setFixedHeight(35)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0099CC;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #00BBEE;
            }
        """)
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)
        
        close_btn = QPushButton("✖ Close")
        close_btn.setFixedHeight(35)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_voice_toggled(self):
        enabled = self.voice_check.isChecked()
        if enabled:
            self.voice_status.setText("🎤 Starting...")
            self.voice_status.setStyleSheet("color: #FF8800; font-size: 8pt;")
            mic_index = self.mic_combo.currentIndex()
            actual_index = mic_index - 1 if mic_index > 0 else None
            self.parent_window.start_voice(actual_index)
        else:
            self.voice_status.setText("🎤 Disabled")
            self.voice_status.setStyleSheet("color: #888888; font-size: 8pt;")
            self.parent_window.stop_voice()
    
    def update_voice_status(self, status):
        self.voice_status.setText(f"🎤 {status}")
        if "Listening" in status:
            self.voice_status.setStyleSheet("color: #00FF00; font-size: 8pt;")
        elif "Error" in status or "not" in status.lower() or "failed" in status.lower():
            self.voice_status.setStyleSheet("color: #FF0000; font-size: 8pt;")
        elif "→" in status or "%" in status:
            self.voice_status.setStyleSheet("color: #00BFFF; font-size: 8pt;")
        else:
            self.voice_status.setStyleSheet("color: #888888; font-size: 8pt;")
    
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

class ClickableLabel(QLabel):
    def __init__(self, text, url, parent=None):
        super().__init__(text, parent)
        self.url = url
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
    def mousePressEvent(self, event):
        webbrowser.open(self.url)

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
        
    def set_window_icon(self):
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(0, 255, 0))
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
        self.voice_label.setText("🎤 Voice: Disabled")
        self.voice_label.setStyleSheet("color: #888888; font-size: 8pt;")
    
    def on_voice_command(self, command):
        if command == 'on':
            if not self.macro_thread.enabled:
                self.macro_thread.enabled = True
        elif command == 'off':
            if self.macro_thread.enabled:
                self.macro_thread.enabled = False
    
    def on_voice_status(self, status):
        if "Listening" in status:
            self.voice_label.setText("🎤 Voice: Listening...")
            self.voice_label.setStyleSheet("color: #00FF00; font-size: 8pt;")
        elif "→" in status or "%" in status:
            self.voice_label.setText(f"🎤 {status}")
            self.voice_label.setStyleSheet("color: #00BFFF; font-size: 8pt;")
        elif "Error" in status or "not" in status.lower() or "failed" in status.lower():
            self.voice_label.setText(f"🎤 {status}")
            self.voice_label.setStyleSheet("color: #FF0000; font-size: 8pt;")
        else:
            self.voice_label.setText(f"🎤 {status}")
            self.voice_label.setStyleSheet("color: #FF8800; font-size: 8pt;")
        
        if self.settings_dialog:
            self.settings_dialog.update_voice_status(status)
    
    def show_settings(self):
        voice_status = "Listening..." if (
            self.voice_thread and
            self.voice_thread.isRunning() and
            self.voice_thread.enabled
        ) else "Disabled"
        
        self.settings_dialog = SettingsDialog(
            self,
            self.macro_hotkey,
            self.aim_button,
            self.voice_enabled,
            self.mic_name,
            voice_status
        )
        
        if self.settings_dialog.exec_() == QDialog.Accepted:
            new_hotkey, new_aim, new_voice, new_mic_name, new_mic_index = \
                self.settings_dialog.get_values()
            
            if new_hotkey != self.macro_hotkey:
                self.macro_hotkey = new_hotkey
                self.register_hotkey(new_hotkey)
                self.toggle_btn.setText(f"Toggle Macro ({new_hotkey})")
            
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
    
    def init_ui(self):
        self.setWindowTitle("Peak & Aim Assistant v2.0")
        self.setFixedSize(400, 680)
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        self.toggle_btn = QPushButton(f"Toggle Macro ({self.macro_hotkey})")
        self.toggle_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.toggle_btn.setFixedHeight(40)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #0099CC;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #00BBEE;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_macro)
        layout.addWidget(self.toggle_btn)
        
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        settings_btn.setFixedHeight(40)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #0099CC;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #00BBEE;
            }
        """)
        settings_btn.clicked.connect(self.show_settings)
        layout.addWidget(settings_btn)
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        footer = QLabel("Made for GameLoop | v2.0")
        footer.setStyleSheet("color: #888888;")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)
        
        central_widget.setLayout(layout)
        
        if self.is_first_run or not self.start_minimized:
            self.show()
        else:
            self.hide()
    
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Peak & Aim Assistant - MAAKTHUNDER")
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(0, 255, 0))
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
    
    def update_overlay_status(self, active, scope_open):
        self.overlay.update_status(active, scope_open, self.overlay_bg)
        if active:
            self.status_dot.setStyleSheet("color: #00FF00;")
            self.status_text.setStyleSheet("color: #00FF00;")
            self.status_text.setText("ACTIVE")
        else:
            self.status_dot.setStyleSheet("color: #FF0000;")
            self.status_text.setStyleSheet("color: #FF0000;")
            self.status_text.setText("INACTIVE")
    
    def toggle_macro(self):
        self.macro_thread.enabled = not self.macro_thread.enabled
    
    def apply_position(self):
        try:
            self.overlay_x = int(self.x_input.text())
            self.overlay_y = int(self.y_input.text())
            self.overlay.move(self.overlay_x, self.overlay_y)
            self.save_settings()
            QMessageBox.information(self, "Success", f"Position saved: X={self.overlay_x}, Y={self.overlay_y}")
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
