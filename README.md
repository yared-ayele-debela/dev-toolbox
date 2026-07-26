# 🧰 Dev-Toolbox

[![Platform](https://img.shields.io/badge/Platform-Ubuntu%20Linux%20%7C%20Debian-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-2021%20Edition-DEA584?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8%2B-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Tauri](https://img.shields.io/badge/Tauri-v2.0-24C8D8?logo=tauri&logoColor=white)](https://tauri.app)
[![GTK3](https://img.shields.io/badge/GTK-3.0-4B8BBE?logo=gnome&logoColor=white)](https://www.gtk.org/)
[![SQLite](https://img.shields.io/badge/SQLite-FTS5-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Dev-Toolbox** is a curated monorepo consolidating standalone developer utilities, background daemons, and desktop productivity tools built specifically for modern Linux desktop environments. From real-time kernel-driven filesystem automation and privacy-conscious clipboard recall to high-security local encryption, instant keyboard application launching, and native document reading, this collection provides an integrated suite of lightweight, high-performance tools designed to elevate engineering daily workflows.

---

## 📦 Consolidated Tools

| Tool | One-Line Description | Tech Stack | Subfolder Link |
| :--- | :--- | :--- | :--- |
| **ClipMgr** | Privacy-first clipboard manager with secret detection, SQLite FTS5 search, and a GTK3 popup | Python 3.9+, GTK 3, SQLite (FTS5), RapidFuzz, systemd | [clipboard-manager](./clipboard-manager) |
| **File Auto-Organizer** | Real-time background daemon automatically sorting downloads and files using inotify events | Python 3.10+, Watchdog, PyYAML, systemd | [auto-file-organizer](./auto-file-organizer) |
| **AeroPDF** | Keyboard-driven desktop PDF & Markdown reader with virtualized canvas rendering and split preview | Tauri v2, Rust, React 19, TypeScript, Vite, Tailwind CSS | [pdf-reader](./pdf-reader) |
| **Personal Vault** | Authenticated CLI encryption utility packaging files and directories into secure `.vlt` containers | Python 3, Argon2id, AES-256-GCM, Cryptography | [personal-vault](./personal-vault) |
| **QuickLaunch** | Lightning-fast floating launcher and command palette with live fuzzy search and frecency ranking | Python 3.10+, GTK 3, RapidFuzz, Watchdog, systemd | [quick-launch](./quick-launch) |

---

## 📂 Repository Structure

```text
dev-toolbox/
├── auto-file-organizer/      # Inotify-based file watcher and automated sorter daemon
├── clipboard-manager/        # Event-driven clipboard monitor with entropy & secret filtering
├── pdf-reader/               # Modern Tauri v2 + React 19 PDF and Markdown desktop reader
├── personal-vault/           # AES-256-GCM + Argon2id CLI archive encryption utility
├── quick-launch/             # Keyboard-centric Alfred/Raycast alternative for Linux
├── .gitignore                # Global ignore rules for Python, Node, Rust, and OS files
├── LICENSE                   # MIT License
└── README.md                 # Monorepo documentation and portfolio overview
```

---

## ⚡ Getting Started

Each utility is fully modular and self-contained within its own subfolder. To install, configure, or run any tool, navigate to its respective directory and consult its dedicated `README.md`:

```bash
# Example: Setting up ClipMgr
cd clipboard-manager
./install.sh

# Example: Setting up File Auto-Organizer
cd ../auto-file-organizer
./install.sh

# Example: Running AeroPDF in development mode
cd ../pdf-reader
pnpm install && pnpm tauri dev

# Example: Using Personal Vault CLI
cd ../personal-vault
./install.sh
vault --help

# Example: Setting up QuickLaunch
cd ../quick-launch
./install.sh
```

---

## 📄 License

This repository and all included tools are released under the [MIT License](./LICENSE).
