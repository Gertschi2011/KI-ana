# 🖥️ KI_ana Desktop App

Native Desktop-Anwendung für KI_ana mit Tauri.

## Features

- ✅ Native Desktop App (Windows, macOS, Linux)
- ✅ System Tray Integration
- ✅ Auto-Start (optional)
- ✅ Native Notifications
- ✅ Dashboard Integration
- ✅ Lightweight (~10MB)

## Development

### Prerequisites

- Rust (https://rustup.rs/)
- Node.js 16+
- KI_ana Backend running

### Install Dependencies

```bash
cd desktop
npm install
```

### Run Development

```bash
# Start KI_ana backend first
cd ..
source .venv/bin/activate
uvicorn netapi.app:app --host 0.0.0.0 --port 8000

# In another terminal, start desktop app
cd desktop
npm run dev
```

### Build

```bash
npm run build
```

Binaries will be in `src-tauri/target/release/`.

## Installation

### Linux

```bash
sudo dpkg -i kiana-desktop_2.0.0_amd64.deb
```

### macOS

```bash
open kiana-desktop_2.0.0_x64.dmg
```

### Windows

```bash
kiana-desktop_2.0.0_x64_en-US.msi
```

## Usage

1. Start KI_ana Desktop App
2. Backend starts automatically (or connect to existing)
3. Dashboard opens in app window
4. Minimize to system tray

## System Tray

- Left Click: Show/Hide window
- Right Click: Menu
  - Show: Show window
  - Hide: Hide to tray
  - Quit: Exit app

## Auto-Start

### Linux (systemd)

```bash
mkdir -p ~/.config/systemd/user/
cat > ~/.config/systemd/user/kiana-desktop.service << EOF
[Unit]
Description=KI_ana Desktop App
After=graphical-session.target

[Service]
ExecStart=/usr/bin/kiana-desktop
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user enable kiana-desktop
systemctl --user start kiana-desktop
```

### macOS

```bash
# Add to Login Items in System Preferences
```

### Windows

```
Add shortcut to:
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

## Configuration

Desktop app uses same configuration as backend (`.env`).

## Troubleshooting

### App won't start

- Check if backend is running
- Check port 8000 is available
- Check logs: `~/.kiana/logs/desktop.log`

### System tray icon missing

- Restart app
- Check desktop environment supports system tray

## Building from Source

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install dependencies
cd desktop
npm install

# Build
npm run build
```

## License

MIT
