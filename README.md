<div align="center">
  <img src="clients/frontend/icons/readme_logo.svg" alt="Mizban">
</div>

<p align="center">
  <em>
    Mizban is a lightweight, LAN-based file sharing tool that lets you easily share files between devices on the same network.
  </em>
</p>

---

## Features

- **Simple LAN file sharing** via a browser (no internet required)
- **Windows desktop app** and **Linux CLI**
- **Zero configuration** — just run it
- **QR code access** for quick connection from phones and other devices

---

## Screenshots

<div align="center">
  <img src="clients/frontend/imgs/terminal.webp" alt="Terminal" height="300"/>
  <img src="clients/frontend/imgs/mobile-ui.webp" alt="Mobile UI" height="300"/>
  <img src="clients/frontend/imgs/web-ui.png" alt="Web UI" height="300"/>
</div>

---

## Installation

### Windows

1. Download the installer from the  
   👉 [Latest Releases](https://github.com/aminupy/mizban/releases/latest)
2. Run the installer and follow the steps.

> **Note**: On first launch, allow Mizban through the Windows Firewall so it can access your local network.

---

### Linux

Mizban CLI can be installed using the official install script:
```bash
curl -fsSL https://raw.githubusercontent.com/aminupy/mizban/main/install.sh | sh
````

After installation, you can:

* launch **Mizban CLI** from your application menu, or
* run it directly in the terminal:

```bash
mizban
```

> **Note**: Make sure `~/.local/bin` is in your `PATH` (this is the default on most modern distributions).

---

## Usage

1. Start Mizban.
2. A folder named **`MizbanShared`** will be created on your **Desktop**.
3. The terminal will show a **QR code** and a local URL.
4. Open the URL (or scan the QR code) on any device connected to the same network.
5. Upload or download files directly from the browser.

> Mizban works entirely over your local network and does **not** require an internet connection.

---

## Roadmap

Planned improvements:
* Optional access protection
* Clipboard sharing across devices

---

## Contributing

Contributions are welcome ❤️

* Fork the repository
* Create a feature branch
* Submit a pull request

Bug reports and feature requests can be opened on
👉 [https://github.com/aminupy/mizban/issues](https://github.com/aminupy/mizban/issues)

---

## License

Mizban is released under the **MIT License**.
See [LICENSE](https://github.com/aminupy/mizban/blob/main/LICENSE) for details.
