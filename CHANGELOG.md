# Changelog

All notable changes to Peak & Aim Assistant will be documented in this file.

## [2.0.0] - 02-20-2024

### Added
- 🎤 Offline voice control using Vosk AI
- 🎯 90% confidence threshold for voice commands
- 📊 Confidence percentage display (e.g., "→ ON (95%)")
- 🌍 Multi-language safe recognition
- 🔵 New blue UI design (#0099CC)
- ⚡ Debounce protection (0.5s between commands)
- 📝 Voice commands: "on", "off", "active", "inactive", "turn on", "turn off"
- 🎙️ Microphone selection in settings
- 🔊 Grammar-restricted recognition (5 words only)

### Changed
- Settings dialog expanded to 480x400
- Buttons redesigned with blue color scheme
- Voice status shows in main window
- Updated to v2.0 branding

### Fixed
- False voice triggers from non-English speech
- Voice recognition now requires 90%+ confidence
- Removed "toggle" command due to bugs

### Technical
- Voice Engine: Vosk (offline)
- Model: vosk-model-small-en-us-0.15 (~50MB)
- No internet required for voice
- Response time: 0.1-0.3 seconds

---

## [1.0.0-voice] - 02-19-2024

### Added
- 🎤 Voice control using Windows Speech Recognition
- 🎚️ Adjustable sensitivity slider (0-4000)
- 🎙️ Microphone selection dropdown
- 📝 Voice commands: "on", "off", "active", "inactive", "turn on", "turn off", "toggle"
- 🔊 Voice status display in main window
- ⚙️ Voice settings in Settings dialog

### Technical
- Voice Engine: Windows Speech Recognition (Google API)
- Internet required
- Dynamic/static energy threshold options

---

## [1.0.0-basic] - 02-18-2024

### Initial Release
- ⌨️ F8 hotkey toggle (customizable)
- 🎯 Q/E peak with auto-aim
- 🖱️ Right-click scope detection (toggle or hold)
- ⏱️ Auto scope reset after 30s inactivity
- 📊 Real-time overlay status display
- 🎨 Customizable overlay position
- 💾 Persistent settings (settings.json)
- 🎮 System tray integration
- ⚙️ Customizable aim button
- 🖥️ Start minimized option
- 🎨 Semi-transparent background option

### Features
- Macro hotkey customization (F1-F12, letters, numbers, etc.)
- Aim button customization
- Overlay position saving
- Clean UI with social links
- Single instance prevention

---

## Version Format

- **[2.0.0]** = Major release (new features)
- **[1.0.0-voice]** = Variant of v1.0
- **[1.0.0-basic]** = Variant of v1.0

Date format: MM-DD-YYYY
