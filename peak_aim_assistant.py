import sys
import json
import os
import time
import ctypes
import webbrowser
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QCheckBox, QSystemTrayIcon, QMenu, QAction, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor, QPixmap, QCursor
import keyboard
from pynput.mouse import Button, Listener as MouseListener

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
    
    def __init__(self):
        super().__init__()
        self.enabled = False
        self.scope_toggled = False
        self.o_held = False
        self.right_click_time = 0
        self.running = True
        self.right_click_pressed = False
        
    def is_gameloop_active(self):
        """Check if GameLoop window is currently focused/active"""
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            
            # Get the currently focused window
            hwnd = user32.GetForegroundWindow()
            
            if hwnd == 0:
                return False
            
            # Get process ID of the focused window
            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            
            # Open process to get its name
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            hProcess = kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 
                False, 
                process_id.value
            )
            
            if not hProcess:
                return False
            
            # Get process executable name
            MAX_PATH = 260
            process_name = ctypes.create_unicode_buffer(MAX_PATH)
            psapi.GetModuleBaseNameW(hProcess, None, process_name, MAX_PATH)
            kernel32.CloseHandle(hProcess)
            
            exe_name = process_name.value.lower()
            
            # Check if it's one of the GameLoop executables
            gameloop_exes = ['AndroidEmulator.exe', 'AndroidEmulatorEn.exe', 'AndroidEmulatorEx.exe']
            
            return exe_name in gameloop_exes
            
        except Exception as e:
            print(f"GameLoop detection error: {e}")
            return False
    
    def run(self):
        def on_click(x, y, button, pressed):
            # Only process right-click when GameLoop is active
            if not self.is_gameloop_active():
                return
                
            if button == Button.right:
                if pressed:
                    self.right_click_time = time.time()
                    self.right_click_pressed = True
                else:
                    self.right_click_pressed = False
                    hold_duration = (time.time() - self.right_click_time) * 1000
                    if hold_duration < 300:
                        self.scope_toggled = not self.scope_toggled
        
        mouse_listener = MouseListener(on_click=on_click)
        mouse_listener.start()
        
        while self.running:
            try:
                # Check if GameLoop window is active
                gameloop_active = self.is_gameloop_active()
                
                if not gameloop_active:
                    # Release O if GameLoop is not active
                    if self.o_held:
                        keyboard.release('o')
                        self.o_held = False
                    self.status_update.emit(self.enabled, self.scope_toggled)
                    time.sleep(0.05)
                    continue
                
                # GameLoop is active, process macro
                if self.enabled:
                    e_pressed = keyboard.is_pressed('e')
                    q_pressed = keyboard.is_pressed('q')
                    
                    scope_active = self.scope_toggled or self.right_click_pressed
                    should_hold = (e_pressed or q_pressed) and not scope_active
                    
                    if should_hold and not self.o_held:
                        keyboard.press('o')
                        self.o_held = True
                    elif not should_hold and self.o_held:
                        keyboard.release('o')
                        self.o_held = False
                        
                    self.status_update.emit(True, scope_active)
                else:
                    if self.o_held:
                        keyboard.release('o')
                        self.o_held = False
                    self.status_update.emit(False, self.scope_toggled)
                    
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Macro thread error: {e}")
                if self.o_held:
                    try:
                        keyboard.release('o')
                    except:
                        pass
                    self.o_held = False
                time.sleep(0.1)
    
    def stop(self):
        self.running = False
        if self.o_held:
            try:
                keyboard.release('o')
            except:
                pass

class ClickableLabel(QLabel):
    """Custom clickable label for links"""
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
        self.load_settings()
        
        self.macro_thread = MacroThread()
        self.macro_thread.status_update.connect(self.update_overlay_status)
        self.macro_thread.start()
        
        self.init_ui()
        self.setup_tray()
        self.setup_overlay()
        
        keyboard.add_hotkey('f8', self.toggle_macro)
        
        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self.watchdog_check)
        self.watchdog_timer.start(2000)
        
        self.set_window_icon()
        
    def set_window_icon(self):
        """Set window icon"""
        if os.path.exists("icon.ico"):
            icon = QIcon("icon.ico")
            self.setWindowIcon(icon)
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
                    self.is_first_run = False
            else:
                self.overlay_x = 1600
                self.overlay_y = 50
                self.overlay_bg = True
                self.start_minimized = False
                self.is_first_run = True
        except:
            self.overlay_x = 1600
            self.overlay_y = 50
            self.overlay_bg = True
            self.start_minimized = False
            self.is_first_run = True
    
    def save_settings(self):
        settings = {
            'overlay_x': self.overlay_x,
            'overlay_y': self.overlay_y,
            'overlay_bg': self.overlay_bg,
            'start_minimized': self.start_minimized
        }
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f)
    
    def init_ui(self):
        self.setWindowTitle("Peak & Aim Assistant v1.0")
        self.setFixedSize(400, 500)
        
        # Main palette
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 10)
        
        # Red title bar area
        title_widget = QWidget()
        title_widget.setStyleSheet("background-color: #CC0000; padding: 10px;")
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        # Title with icon
        title_h_layout = QHBoxLayout()
        
        if os.path.exists("icon.ico"):
            logo_label = QLabel()
            logo_pixmap = QPixmap("icon.ico")
            logo_label.setPixmap(logo_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            title_h_layout.addWidget(logo_label)
        
        title = QLabel("Peak & Aim Assistant")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        title_h_layout.addWidget(title)
        title_h_layout.addStretch()
        
        title_layout.addLayout(title_h_layout)
        
        # Creator name
        creator = QLabel("Created by MAAKTHUNERYT")
        creator.setFont(QFont("Segoe UI", 9))
        creator.setStyleSheet("color: white; background: transparent;")
        title_layout.addWidget(creator)
        
        title_widget.setLayout(title_layout)
        layout.addWidget(title_widget)
        
        # Content area
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 10)
        
        content_layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
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
        content_layout.addLayout(status_layout)
        
        content_layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # Toggle button
        self.toggle_btn = QPushButton("Toggle Macro (F8)")
        self.toggle_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.toggle_btn.setFixedHeight(40)
        self.toggle_btn.clicked.connect(self.toggle_macro)
        content_layout.addWidget(self.toggle_btn)
        
        # Overlay position
        pos_label = QLabel("Overlay Position:")
        pos_label.setStyleSheet("color: #AAAAAA;")
        content_layout.addWidget(pos_label)
        
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
        content_layout.addLayout(pos_layout)
        
        # Checkboxes
        self.bg_check = QCheckBox("Show Background (Semi-transparent)")
        self.bg_check.setStyleSheet("color: white;")
        self.bg_check.setChecked(self.overlay_bg)
        self.bg_check.stateChanged.connect(self.toggle_background)
        content_layout.addWidget(self.bg_check)
        
        self.minimize_check = QCheckBox("Start Minimized to Tray")
        self.minimize_check.setStyleSheet("color: white;")
        self.minimize_check.setChecked(self.start_minimized)
        self.minimize_check.stateChanged.connect(self.toggle_minimize)
        content_layout.addWidget(self.minimize_check)
        
        tip_label = QLabel("Tip: Only works when GameLoop is active")
        tip_label.setStyleSheet("color: #FF8800; font-size: 8pt;")
        content_layout.addWidget(tip_label)
        
        content_layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # Hotkeys section
        hotkeys_label = QLabel("Hotkeys:")
        hotkeys_label.setStyleSheet("color: white; font-weight: bold;")
        content_layout.addWidget(hotkeys_label)
        
        hotkey1 = QLabel("F8 - Toggle Macro ON/OFF")
        hotkey1.setStyleSheet("color: #CCCCCC;")
        content_layout.addWidget(hotkey1)
        
        hotkey2 = QLabel("Q/E - Peak with Auto-Aim")
        hotkey2.setStyleSheet("color: #CCCCCC;")
        content_layout.addWidget(hotkey2)
        
        content_layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # Social links with icons
        youtube_layout = QHBoxLayout()
        youtube_layout.setSpacing(8)
        
        if os.path.exists("youtube.ico"):
            yt_icon = QLabel()
            yt_pixmap = QPixmap("youtube.ico")
            yt_icon.setPixmap(yt_pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            youtube_layout.addWidget(yt_icon)
        
        yt_link = ClickableLabel("youtube.com/@MAAKTHUNDER", "https://www.youtube.com/@MAAKTHUNDER")
        yt_link.setStyleSheet("color: #FF0000; text-decoration: underline;")
        youtube_layout.addWidget(yt_link)
        youtube_layout.addStretch()
        content_layout.addLayout(youtube_layout)
        
        tiktok_layout = QHBoxLayout()
        tiktok_layout.setSpacing(8)
        
        if os.path.exists("tiktok.ico"):
            tt_icon = QLabel()
            tt_pixmap = QPixmap("tiktok.ico")
            tt_icon.setPixmap(tt_pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            tiktok_layout.addWidget(tt_icon)
        
        tt_link = ClickableLabel("tiktok.com/@maakthunder", "https://www.tiktok.com/@maakthunder")
        tt_link.setStyleSheet("color: #00F5FF; text-decoration: underline;")
        tiktok_layout.addWidget(tt_link)
        tiktok_layout.addStretch()
        content_layout.addLayout(tiktok_layout)
        
        content_layout.addWidget(QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", self))
        
        # Footer
        footer = QLabel("Made for GameLoop | v1.0")
        footer.setStyleSheet("color: #888888;")
        footer.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(footer)
        
        content_widget.setLayout(content_layout)
        layout.addWidget(content_widget)
        
        central_widget.setLayout(layout)
        
        if self.is_first_run or not self.start_minimized:
            self.show()
        else:
            self.hide()
    
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Peak & Aim Assistant - MAAKTHUNERYT")
        
        if os.path.exists("icon.ico"):
            icon = QIcon("icon.ico")
            self.tray_icon.setIcon(icon)
        else:
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(0, 255, 0))
            self.tray_icon.setIcon(QIcon(pixmap))
        
        tray_menu = QMenu()
        
        show_action = QAction("Show GUI", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        toggle_action = QAction("Toggle Macro (F8)", self)
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
        if not self.macro_thread.enabled and self.macro_thread.o_held:
            try:
                keyboard.release('o')
                self.macro_thread.o_held = False
            except:
                pass
    
    def closeEvent(self, event):
        event.ignore()
        self.hide()
    
    def quit_app(self):
        self.macro_thread.stop()
        self.macro_thread.wait()
        QApplication.quit()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
