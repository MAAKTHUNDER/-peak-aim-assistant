import sys
import json
import os
import time
import webbrowser
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QCheckBox, QSystemTrayIcon, QMenu, QAction, QMessageBox, QComboBox, QDialog)
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
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Voice commands
ON_COMMANDS = ['on', 'active', 'turn on']
OFF_COMMANDS = ['off', 'inactive', 'turn off']

# Complete keyboard keys list
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

class VoiceThread(QThread):
    command_received = pyqtSignal(str)
    status_update = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.enabled = False
        self.recognizer = None
        self.microphone = None
    
    def initialize(self):
        """Initialize speech recognizer"""
        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.5
            self.microphone = sr.Microphone()
            
            # Calibrate microphone
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            return True
        except Exception as e:
            self.status_update.emit(f"Mic Error: {str(e)}")
            return False
    
    def run(self):
        """Main voice recognition loop"""
        if not SPEECH_AVAILABLE:
            self.status_update.emit("SpeechRecognition not installed!")
            return
        
        if not self.initialize():
            self.status_update.emit("Microphone not found!")
            return
        
        self.status_update.emit("🎤 Listening...")
        self.running = True
        
        while self.running:
            try:
                if not self.enabled:
                    time.sleep(0.2)
                    continue
                
                with self.microphone as source:
                    try:
                        audio = self.recognizer.listen(
                            source,
                            timeout=2,
                            phrase_time_limit=3
                        )
                    except sr.WaitTimeoutError:
                        continue
                
                try:
                    # Use Windows Speech (sphinx for offline)
                    text = self.recognizer.recognize_google(audio).lower()
                    self.status_update.emit(f"Heard: {text}")
                    
                    # Check commands
                    for cmd in ON_COMMANDS:
                        if cmd in text:
                            self.command_received.emit('on')
                            break
                    
                    for cmd in OFF_COMMANDS:
                        if cmd in text:
                            self.command_received.emit('off')
                            break
                            
                except sr.UnknownValueError:
                    pass
                except sr.RequestError:
                    # Fallback to Windows built-in speech
                    try:
                        text = self.recognizer.recognize_sphinx(audio).lower()
                        self.status_update.emit(f"Heard: {text}")
                        
                        for cmd in ON_COMMANDS:
                            if cmd in text:
                                self.command_received.emit('on')
                                break
                        
                        for cmd in OFF_COMMANDS:
                            if cmd in text:
                                self.command_received.emit('off')
                                break
                    except:
                        self.status_update.emit("🎤 Listening...")
                        
            except Exception as e:
                time.sleep(0.5)
                continue
    
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
        
        if show_bg:
            bg_color = "rgba(0, 0, 0, 180)"
        else:
            bg_color = "transparent"
            
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
                # Auto-reset scope after 10 seconds
                if self.scope_toggled:
                    if (time.time() - self.last_right_click_activity) > 10.0:
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
    def __init__(self, parent, current_hotkey, current_aim):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 200)
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        title = QLabel("⚙ Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # Macro Hotkey
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
        
        # Aim Button
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Apply & Save")
        save_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def get_values(self):
        return self.hotkey_combo.currentText(), self.aim_combo.currentText()

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
        self.load_settings()
        
        self.macro_thread = MacroThread(self.aim_button)
        self.macro_thread.status_update.connect(self.update_overlay_status)
        self.macro_thread.start()
        
        # Voice thread
        self.voice_thread = None
        
        self.init_ui()
        self.setup_tray()
        self.setup_overlay()
        
        self.register_hotkey(self.macro_hotkey)
        
        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self.watchdog_check)
        self.watchdog_timer.start(2000)
        
        self.set_window_icon()
        
        # Start voice if enabled
        if self.voice_enabled:
            self.start_voice()
        
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
                    self.is_first_run = False
            else:
                self.overlay_x = 1600
                self.overlay_y = 50
                self.overlay_bg = True
                self.start_minimized = False
                self.macro_hotkey = 'F8'
                self.aim_button = 'O'
                self.voice_enabled = False
                self.is_first_run = True
        except:
            self.overlay_x = 1600
            self.overlay_y = 50
            self.overlay_bg = True
            self.start_minimized = False
            self.macro_hotkey = 'F8'
            self.aim_button = 'O'
            self.voice_enabled = False
            self.is_first_run = True
    
    def save_settings(self):
        try:
            settings = {
                'overlay_x': self.overlay_x,
                'overlay_y': self.overlay_y,
                'overlay_bg': self.overlay_bg,
                'start_minimized': self.start_minimized,
                'macro_hotkey': self.macro_hotkey,
                'aim_button': self.aim_button,
                'voice_enabled': self.voice_enabled
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
    
    def start_voice(self):
        """Start voice recognition thread"""
        if not SPEECH_AVAILABLE:
            self.voice_status.setText("⚠ SpeechRecognition not installed!")
            self.voice_status.setStyleSheet("color: #FF8800; font-size: 8pt;")
            return
        
        if self.voice_thread and self.voice_thread.isRunning():
            self.voice_thread.enabled = True
            return
        
        self.voice_thread = VoiceThread()
        self.voice_thread.command_received.connect(self.on_voice_command)
        self.voice_thread.status_update.connect(self.on_voice_status)
        self.voice_thread.enabled = True
        self.voice_thread.start()
    
    def stop_voice(self):
        """Stop voice recognition"""
        if self.voice_thread:
            self.voice_thread.enabled = False
            self.voice_status.setText("🎤 Voice: Disabled")
            self.voice_status.setStyleSheet("color: #888888; font-size: 8pt;")
    
    def on_voice_command(self, command):
        """Handle received voice command"""
        if command == 'on':
            if not self.macro_thread.enabled:
                self.macro_thread.enabled = True
                self.voice_status.setText("🎤 Said: ON → Macro Enabled!")
                self.voice_status.setStyleSheet("color: #00FF00; font-size: 8pt;")
        elif command == 'off':
            if self.macro_thread.enabled:
                self.macro_thread.enabled = False
                self.voice_status.setText("🎤 Said: OFF → Macro Disabled!")
                self.voice_status.setStyleSheet("color: #FF0000; font-size: 8pt;")
    
    def on_voice_status(self, status):
        """Update voice status label"""
        self.voice_status.setText(f"🎤 {status}")
        if "Error" in status or "not" in status:
            self.voice_status.setStyleSheet("color: #FF8800; font-size: 8pt;")
        else:
            self.voice_status.setStyleSheet("color: #00BFFF; font-size: 8pt;")
    
    def toggle_voice(self):
        """Toggle voice control on/off"""
        self.voice_enabled = self.voice_check.isChecked()
        self.save_settings()
        
        if self.voice_enabled:
            self.start_voice()
        else:
            self.stop_voice()
    
    def show_settings(self):
        dialog = SettingsDialog(self, self.macro_hotkey, self.aim_button)
        
        if dialog.exec_() == QDialog.Accepted:
            new_hotkey, new_aim = dialog.get_values()
            
            if new_hotkey != self.macro_hotkey:
                self.macro_hotkey = new_hotkey
                self.register_hotkey(new_hotkey)
                self.toggle_btn.setText(f"Toggle Macro ({new_hotkey})")
            
            if new_aim != self.aim_button:
                self.aim_button = new_aim
                self.macro_thread.set_aim_button(new_aim)
            
            self.save_settings()
            QMessageBox.information(self, "Success", "Settings saved successfully!")
    
    def init_ui(self):
        self.setWindowTitle("Peak & Aim Assistant v1.0")
        self.setFixedSize(400, 700)
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Title section
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # Toggle & Settings buttons
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
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
        
        # Checkboxes
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
        
        tip_label = QLabel("Tip: Scope auto-resets after 10s inactivity")
        tip_label.setStyleSheet("color: #00FF00; font-size: 8pt;")
        layout.addWidget(tip_label)
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # Voice Control Section
        voice_label = QLabel("🎤 Voice Control:")
        voice_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(voice_label)
        
        self.voice_check = QCheckBox("Enable Voice Commands")
        self.voice_check.setStyleSheet("color: white;")
        self.voice_check.setChecked(self.voice_enabled)
        self.voice_check.stateChanged.connect(self.toggle_voice)
        layout.addWidget(self.voice_check)
        
        # Voice status label
        self.voice_status = QLabel("🎤 Voice: Disabled")
        self.voice_status.setStyleSheet("color: #888888; font-size: 8pt;")
        layout.addWidget(self.voice_status)
        
        # Voice commands hint
        voice_hint = QLabel('Say: "On" / "Active" / "Turn On"\n     "Off" / "Inactive" / "Turn Off"')
        voice_hint.setStyleSheet("color: #888888; font-size: 8pt;")
        layout.addWidget(voice_hint)
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # How it Works
        how_label = QLabel("How it Works:")
        how_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(how_label)
        
        hotkey_text = QLabel(f"{self.macro_hotkey} - Toggle Macro ON/OFF (Default)")
        hotkey_text.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(hotkey_text)
        
        spacer = QLabel("")
        spacer.setFixedHeight(5)
        layout.addWidget(spacer)
        
        peak_text = QLabel("Q/E - Peak with Auto-Aim")
        peak_text.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(peak_text)
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
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
        
        layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        footer = QLabel("Made for GameLoop | v1.0")
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
  
